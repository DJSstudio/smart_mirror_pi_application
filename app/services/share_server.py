"""Local HTTP share server.

Serves a mobile-friendly gallery page and time-limited video-download
links.  Runs in a daemon thread so it never blocks the Qt event loop.

Routes
──────
  GET  /                        → HTML gallery (session recordings)
  GET  /api/videos              → JSON list of videos
  GET  /download/<video_id>     → Stream the full video file
  GET  /export/<token>          → Time-limited download (10 min)

The server holds a snapshot of gallery data that the ExportController
refreshes from the Qt main thread whenever it changes.  A threading.Lock
keeps reads in the HTTP handler threads consistent.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_EXPORT_TTL = 600   # seconds (10 min)
_LOGIN_TTL  = 300   # seconds (5 min) — QR refreshes automatically after this


@dataclass
class _VideoSnapshot:
    id: str
    title: str
    file_path: str
    duration_label: str
    created_label: str


class ShareServer:
    """Lifecycle manager for the embedded HTTP share server."""

    def __init__(self, host: str = "0.0.0.0", port: int = 0) -> None:
        self._host = host
        self._port = port          # 0 = OS picks a free port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

        # Data cache — written only from Qt main thread, read from HTTP threads
        self._lock = threading.Lock()
        self._session_name = "Smart Mirror"
        self._videos: list[_VideoSnapshot] = []

        # Export tokens: hash → (video_id, expiry_epoch)
        self._tokens: dict[str, tuple[str, float]] = {}

        # Login tokens: hash → (status, expiry_epoch, device_id | None)
        # status: 'pending' | 'activated'
        self._login_tokens: dict[str, tuple[str, float, str | None]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> int:
        """Start the server and return the port it is listening on."""
        if self._server is not None:
            return self._port
        handler = self._make_handler()
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="ShareServer",
        )
        self._thread.start()
        LOGGER.info("Share server listening on port %d", self._port)
        return self._port

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        self._port = 0

    @property
    def port(self) -> int:
        return self._port

    # ------------------------------------------------------------------
    # Data updates (called from Qt main thread)
    # ------------------------------------------------------------------

    def update_gallery(
        self,
        session_name: str,
        videos: list[Any],   # list[VideoRecord] — avoid hard import
    ) -> None:
        """Refresh the cached gallery data served to phones."""
        snapshots = [
            _VideoSnapshot(
                id=v.id,
                title=v.title,
                file_path=v.file_path,
                duration_label=_fmt_dur(v.duration_seconds),
                created_label=v.created_label(),
            )
            for v in videos
        ]
        with self._lock:
            self._session_name = session_name
            self._videos = snapshots

    # ------------------------------------------------------------------
    # Export tokens
    # ------------------------------------------------------------------

    def create_token(self, video_id: str) -> str:
        """Create a 10-minute single-use download token for *video_id*."""
        self._purge_expired()
        token = secrets.token_urlsafe(16)
        with self._lock:
            self._tokens[token] = (video_id, time.time() + _EXPORT_TTL)
        LOGGER.debug("Export token created for video %s", video_id)
        return token

    def resolve_token(self, token: str) -> str | None:
        """Return video_id for a valid unexpired token, or None."""
        with self._lock:
            entry = self._tokens.get(token)
        if entry is None:
            return None
        video_id, expiry = entry
        if time.time() > expiry:
            with self._lock:
                self._tokens.pop(token, None)
            return None
        return video_id

    # ------------------------------------------------------------------
    # Login tokens  (QR-based session start / resume)
    # ------------------------------------------------------------------

    def create_login_token(self) -> tuple[str, str]:
        """Create a pending login token.

        Returns *(raw_token, token_hash)*.  The raw token is encoded in the
        QR URL; only the hash is stored in memory.
        """
        raw = secrets.token_urlsafe(24)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expiry = time.time() + _LOGIN_TTL
        with self._lock:
            self._login_tokens[token_hash] = ("pending", expiry, None)
        LOGGER.debug("Login token created (hash prefix: %s)", token_hash[:8])
        return raw, token_hash

    def check_login_status(self, token_hash: str) -> tuple[str, str | None]:
        """Return *(status, device_id)* for a login token.

        *status* is ``'pending'``, ``'activated'``, or ``'expired'``.
        """
        with self._lock:
            entry = self._login_tokens.get(token_hash)
        if entry is None:
            return "expired", None
        status, expiry, device_id = entry
        if time.time() > expiry:
            with self._lock:
                self._login_tokens.pop(token_hash, None)
            return "expired", None
        return status, device_id

    def activate_login_token(self, raw_token: str, device_id: str) -> bool:
        """Mark a login token as activated by *device_id*.

        *raw_token* is the plain-text value from the QR URL.  Returns
        ``True`` if the token was valid and is now activated.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._lock:
            entry = self._login_tokens.get(token_hash)
        if entry is None:
            return False
        _status, expiry, _did = entry
        if time.time() > expiry:
            with self._lock:
                self._login_tokens.pop(token_hash, None)
            return False
        with self._lock:
            self._login_tokens[token_hash] = ("activated", expiry, device_id)
        LOGGER.info("Login token activated by device %s", device_id[:8])
        return True

    def invalidate_login_token(self, token_hash: str) -> None:
        """Remove a login token (e.g. after successful login or skip)."""
        with self._lock:
            self._login_tokens.pop(token_hash, None)

    def token_remaining(self, token: str) -> int:
        """Remaining seconds for a token (0 if expired/unknown)."""
        with self._lock:
            entry = self._tokens.get(token)
        if entry is None:
            return 0
        _, expiry = entry
        return max(0, int(expiry - time.time()))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _purge_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [t for t, (_, exp) in self._tokens.items() if now > exp]
            for t in expired:
                del self._tokens[t]

    def _get_snapshot(self) -> tuple[str, list[_VideoSnapshot]]:
        with self._lock:
            return self._session_name, list(self._videos)

    def _find_video(self, video_id: str) -> _VideoSnapshot | None:
        with self._lock:
            for v in self._videos:
                if v.id == video_id:
                    return v
        return None

    def _make_handler(self):
        server = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: N802
                LOGGER.debug("[share] " + fmt, *args)

            def do_GET(self):  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                qs = urllib.parse.parse_qs(parsed.query)
                try:
                    if path in ("/", "/gallery"):
                        self._gallery()
                    elif path == "/api/videos":
                        self._api_videos()
                    elif path.startswith("/download/"):
                        self._download(path[len("/download/"):])
                    elif path.startswith("/export/"):
                        self._export(path[len("/export/"):])
                    elif path == "/qr/activate":
                        self._qr_activate_page(qs.get("token", [""])[0])
                    elif path == "/api/qr/confirm":
                        self._qr_confirm(
                            qs.get("token", [""])[0],
                            qs.get("device_id", [""])[0],
                        )
                    else:
                        self._err(404, "Not found")
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Share server error: %s", exc)
                    self._err(500, "Internal error")

            # ── Pages ───────────────────────────────────────────────────

            def _gallery(self):
                session_name, videos = server._get_snapshot()
                host = self.headers.get("Host", f"localhost:{server.port}")
                items = ""
                for v in videos:
                    dl = f"http://{host}/download/{v.id}"
                    items += (
                        f'<div class="card">'
                        f'<div class="icon">▶</div>'
                        f'<div class="info">'
                        f'<div class="title">{_esc(v.title)}</div>'
                        f'<div class="meta">{_esc(v.duration_label)}'
                        f' · {_esc(v.created_label)}</div>'
                        f'</div>'
                        f'<a href="{dl}" class="dl" download>Download</a>'
                        f'</div>'
                    )
                if not items:
                    items = '<p class="empty">No recordings yet.</p>'
                html = _HTML.format(name=_esc(session_name), items=items)
                self._html(html)

            def _api_videos(self):
                session_name, videos = server._get_snapshot()
                host = self.headers.get("Host", f"localhost:{server.port}")
                self._json([
                    {
                        "id": v.id,
                        "title": v.title,
                        "duration": v.duration_label,
                        "created": v.created_label,
                        "download_url": f"http://{host}/download/{v.id}",
                    }
                    for v in videos
                ])

            def _download(self, video_id: str):
                snap = server._find_video(video_id)
                if snap is None:
                    self._err(404, "Video not found")
                    return
                self._stream(Path(snap.file_path), snap.title)

            def _export(self, token: str):
                video_id = server.resolve_token(token)
                if video_id is None:
                    self._err(410, "Link expired or invalid")
                    return
                self._download(video_id)

            def _qr_activate_page(self, token: str):
                """HTML page that auto-generates a device_id and confirms the scan."""
                html = _LOGIN_HTML.replace("__TOKEN__", _esc(token))
                self._html(html)

            def _qr_confirm(self, token: str, device_id: str):
                """JSON endpoint called by the phone browser after device_id generation."""
                if not token or not device_id:
                    self._json({"ok": False, "error": "Missing token or device_id"})
                    return
                if server.activate_login_token(token, device_id):
                    self._json({"ok": True})
                else:
                    self._json({"ok": False, "error": "Invalid or expired QR code"})

            # ── Helpers ──────────────────────────────────────────────────

            def _stream(self, path: Path, title: str):
                if not path.exists():
                    self._err(404, "File not found")
                    return
                size = path.stat().st_size
                ext = path.suffix.lower()
                mime = "video/mp4" if ext == ".mp4" else "video/octet-stream"
                safe = "".join(
                    c if c.isalnum() or c in " ._-" else "_" for c in title
                )
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(size))
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{safe}{ext}"',
                )
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                with open(path, "rb") as fh:
                    while chunk := fh.read(65536):
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break

            def _html(self, body: str):
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _json(self, obj):
                data = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _err(self, code: int, msg: str):
                data = msg.encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return _Handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_dur(secs: float | None) -> str:
    if not secs or secs <= 0:
        return "--:--"
    t = int(secs)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# QR login HTML — served when a phone opens /qr/activate?token=<raw>
# ---------------------------------------------------------------------------

_LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Mirror — Start Session</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#1a1614;color:#f0ebe5;display:flex;align-items:center;
     justify-content:center;min-height:100vh;padding:24px;text-align:center}
.card{background:#2a2420;border-radius:20px;padding:36px 28px;max-width:340px;width:100%}
.icon{font-size:52px;margin-bottom:16px}
h1{font-size:22px;font-weight:600;margin-bottom:8px}
.sub{font-size:14px;color:#9d9590;margin-bottom:28px;line-height:1.5}
.status{font-size:15px;padding:16px;border-radius:12px;background:#3a3028;
        color:#d0c8c0;transition:background .3s,color .3s}
.ok{background:#1e3020!important;color:#7de870!important}
.err{background:#3a2020!important;color:#e87070!important}
</style>
</head>
<body>
<div class="card">
  <div class="icon">🪞</div>
  <h1>Smart Mirror</h1>
  <p class="sub">Connecting to your session&hellip;</p>
  <div class="status" id="st">Please wait&hellip;</div>
</div>
<script>
function uuid4(){
  return([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g,function(c){
    return(c^crypto.getRandomValues(new Uint8Array(1))[0]&15>>c/4).toString(16);
  });
}
var token='__TOKEN__';
var did=localStorage.getItem('mirror_device_id');
if(!did){did=uuid4();localStorage.setItem('mirror_device_id',did);}
var st=document.getElementById('st');
fetch('/api/qr/confirm?token='+encodeURIComponent(token)+'&device_id='+encodeURIComponent(did))
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok){
      st.className='status ok';
      st.textContent='\u2713 Mirror is ready \u2014 you can put your phone away.';
    }else{
      st.className='status err';
      st.textContent='Error: '+(d.error||'Unknown error. Try scanning again.');
    }
  })
  .catch(function(e){
    st.className='status err';
    st.textContent='Could not reach mirror: '+e.message;
  });
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Mobile gallery HTML template
# ---------------------------------------------------------------------------

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Smart Mirror</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f5f0ec;color:#3c3530;padding-bottom:40px}}
header{{background:#2e2925;color:#f0ebe5;padding:20px}}
header h1{{font-size:20px;font-weight:600;margin-bottom:4px}}
header p{{font-size:13px;color:#a09590}}
.list{{padding:16px;display:flex;flex-direction:column;gap:12px}}
.card{{background:#fff;border-radius:14px;padding:16px;
       display:flex;align-items:center;gap:14px;
       box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.icon{{width:44px;height:44px;border-radius:10px;background:#e8e0da;
       display:flex;align-items:center;justify-content:center;
       font-size:20px;flex-shrink:0}}
.info{{flex:1;min-width:0}}
.title{{font-size:15px;font-weight:600;margin-bottom:3px}}
.meta{{font-size:12px;color:#9d9590}}
.dl{{background:#3c3530;color:#fff;padding:10px 16px;border-radius:10px;
     text-decoration:none;font-size:14px;font-weight:600;flex-shrink:0}}
.empty{{text-align:center;color:#9d9590;padding:40px 20px;font-size:15px}}
</style>
</head>
<body>
<header>
  <h1>{name}</h1>
  <p>Smart Mirror recordings — tap Download to save to your phone</p>
</header>
<div class="list">
{items}
</div>
</body>
</html>
"""
