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

        # token → (video_id, expiry_epoch)
        self._tokens: dict[str, tuple[str, float]] = {}

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
                try:
                    if path in ("/", "/gallery"):
                        self._gallery()
                    elif path == "/api/videos":
                        self._api_videos()
                    elif path.startswith("/download/"):
                        self._download(path[len("/download/"):])
                    elif path.startswith("/export/"):
                        self._export(path[len("/export/"):])
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
