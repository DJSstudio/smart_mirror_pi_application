"""Local HTTP share server.

Serves a mobile-friendly gallery page and time-limited video-download
links.  Runs in a daemon thread so it never blocks the Qt event loop.

Routes
──────
  GET  /                           → HTML gallery (session recordings, open)
  GET  /api/videos                 → JSON list of videos (open)
  GET  /download/<video_id>        → Stream the full video file (open)
  GET  /session/<token>            → Device-verification page then gallery (session owner only)
  GET  /api/session/videos         → Verify device; return gallery JSON
  GET  /export/<token>             → Device-verification page (must match session owner)
  GET  /api/export/verify          → Verify device_id; issue one-time dl_token
  GET  /export/dl/<dl_token>       → One-time 60-second stream (post-verification)
  GET  /qr/activate?token=<raw>    → QR login page (shows Resume/Fresh choice if known device)
  GET  /api/qr/confirm             → Phone confirms scan; returns needs_choice flag
  GET  /api/qr/choice              → Phone submits Resume or Start-Fresh choice

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
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

_EXPORT_TTL  = 600   # seconds (10 min) — export QR link validity
_SESSION_TTL = 1800  # seconds (30 min) — session gallery access token
_LOGIN_TTL   = 300   # seconds  (5 min) — QR login token (auto-regenerated)
_DL_TTL      = 60    # seconds (60 s)   — one-time download token after verification

# Rate limiting — applied to sensitive API endpoints only.
# Each IP gets a bucket of _RL_BURST tokens; one token is consumed per request.
# Tokens refill at 1/second up to the burst limit.
_RL_BURST    = 10    # max requests allowed in a burst
_RL_RATE     = 1.0   # tokens refilled per second


@dataclass
class _RateBucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(
            _RL_BURST,
            self.tokens + (now - self.last_refill) * _RL_RATE,
        )
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


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

        # Export tokens: token → (video_id, expiry, required_device_id)
        # required_device_id="" means any device may download (anonymous session).
        self._tokens: dict[str, tuple[str, float, str]] = {}

        # One-time 60-second download tokens issued after device verification.
        self._dl_tokens: dict[str, tuple[str, float]] = {}

        # Session gallery tokens: token → (expiry, required_device_id)
        # required_device_id="" means any device may view (anonymous session).
        self._session_tokens: dict[str, tuple[float, str]] = {}

        # Login tokens: token_hash → (status, expiry, device_id | None, action | None)
        #   status : "pending" | "pending_choice" | "activated"
        #   action : None | "resume" | "new"
        self._login_tokens: dict[str, tuple[str, float, str | None, str | None]] = {}

        # Optional callback: fn(device_id) → (has_previous, session_name, video_count)
        # Registered by LoginController; called from HTTP handler threads (thread-safe:
        # SQLite WAL + check_same_thread=False).
        self._device_checker: Callable[[str], tuple[bool, str, int]] | None = None

        # Per-IP rate-limit buckets for sensitive API endpoints.
        self._rl_buckets: dict[str, _RateBucket] = {}
        self._rl_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> int:
        """Start the server and return the port it is listening on."""
        if self._server is not None:
            return self._port
        handler = self._make_handler()
        # allow_reuse_address lets us rebind the fixed port immediately after
        # a crash or unclean shutdown without waiting for the OS TIME_WAIT.
        ThreadingHTTPServer.allow_reuse_address = True
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

    def set_device_checker(
        self,
        fn: Callable[[str], tuple[bool, str, int]],
    ) -> None:
        """Register a callback: fn(device_id) → (has_previous, session_name, video_count).

        Called from HTTP handler threads when a phone confirms a QR scan.
        Must be thread-safe (SQLite WAL mode is fine for read queries).
        """
        self._device_checker = fn

    # ------------------------------------------------------------------
    # Export tokens
    # ------------------------------------------------------------------

    def create_token(self, video_id: str, required_device_id: str = "") -> str:
        """Create a 10-minute download token for *video_id*.

        *required_device_id=""* means any device may download (anonymous
        session).  Otherwise only the matching device_id is allowed.
        """
        self._purge_expired()
        token = secrets.token_urlsafe(16)
        with self._lock:
            self._tokens[token] = (video_id, time.time() + _EXPORT_TTL, required_device_id)
        LOGGER.debug("Export token created for video %s", video_id)
        return token

    def resolve_token(self, token: str) -> str | None:
        """Return video_id for a valid unexpired token (no device check)."""
        with self._lock:
            entry = self._tokens.get(token)
        if entry is None:
            return None
        video_id, expiry, _ = entry
        if time.time() > expiry:
            with self._lock:
                self._tokens.pop(token, None)
            return None
        return video_id

    def verify_export_token(
        self, token: str, device_id: str
    ) -> tuple[bool, str | None]:
        """Check that *device_id* is authorised to download the token's video.

        Returns *(ok, video_id)*.  The export token is not consumed here so
        the device can retry if the download fails; the one-time *dl_token*
        issued by the HTTP handler provides single-use enforcement.
        """
        with self._lock:
            entry = self._tokens.get(token)
        if entry is None:
            return False, None
        video_id, expiry, required_did = entry
        if time.time() > expiry:
            with self._lock:
                self._tokens.pop(token, None)
            return False, None
        if required_did and device_id != required_did:
            LOGGER.warning(
                "Export auth failure: required device %s, got %s",
                required_did[:8],
                device_id[:8] if device_id else "(none)",
            )
            return False, None
        return True, video_id

    def create_dl_token(self, video_id: str) -> str:
        """Issue a one-time 60-second download token after device verification."""
        token = secrets.token_urlsafe(16)
        with self._lock:
            self._dl_tokens[token] = (video_id, time.time() + _DL_TTL)
        return token

    def resolve_dl_token(self, token: str) -> str | None:
        """Consume a one-time download token; returns video_id or None."""
        with self._lock:
            entry = self._dl_tokens.pop(token, None)
        if entry is None:
            return None
        video_id, expiry = entry
        if time.time() > expiry:
            return None
        return video_id

    def token_remaining(self, token: str) -> int:
        """Remaining seconds for a token (0 if expired/unknown)."""
        with self._lock:
            entry = self._tokens.get(token)
        if entry is None:
            return 0
        _, expiry, _ = entry
        return max(0, int(expiry - time.time()))

    # ------------------------------------------------------------------
    # Session gallery tokens  (View on Phone)
    # ------------------------------------------------------------------

    def create_session_token(self, required_device_id: str = "") -> str:
        """Create a 30-minute gallery-access token.

        *required_device_id=""* means any device may browse (anonymous
        session).  Otherwise only the matching device_id is allowed.
        """
        self._purge_expired()
        token = secrets.token_urlsafe(16)
        with self._lock:
            self._session_tokens[token] = (time.time() + _SESSION_TTL, required_device_id)
        LOGGER.debug("Session gallery token created")
        return token

    def _check_session_token(self, token: str, device_id: str) -> bool:
        """Return True if *device_id* is authorised for this session token."""
        with self._lock:
            entry = self._session_tokens.get(token)
        if entry is None:
            return False
        expiry, required_did = entry
        if time.time() > expiry:
            with self._lock:
                self._session_tokens.pop(token, None)
            return False
        if required_did and device_id != required_did:
            LOGGER.warning(
                "Session gallery auth failure: required device %s, got %s",
                required_did[:8],
                device_id[:8] if device_id else "(none)",
            )
            return False
        return True

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
            self._login_tokens[token_hash] = ("pending", expiry, None, None)
        LOGGER.debug("Login token created (hash prefix: %s)", token_hash[:8])
        return raw, token_hash

    def handle_qr_confirm(
        self, raw_token: str, device_id: str
    ) -> tuple[bool, bool, str, int]:
        """Process a QR confirmation from the phone browser.

        Returns *(ok, needs_choice, session_name, video_count)*.

        * ok=False          — invalid or expired token
        * needs_choice=True — device has a *different* previous session;
                              the phone should present Resume / Start-Fresh
        * needs_choice=False — new device (or same session re-scan); activate
                               immediately
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._lock:
            entry = self._login_tokens.get(token_hash)
        if entry is None:
            return False, False, "", 0
        status, expiry, _, _ = entry
        if status != "pending":
            return False, False, "", 0
        if time.time() > expiry:
            with self._lock:
                self._login_tokens.pop(token_hash, None)
            return False, False, "", 0

        has_previous, session_name, video_count = False, "", 0
        if self._device_checker:
            try:
                has_previous, session_name, video_count = self._device_checker(device_id)
            except Exception:  # noqa: BLE001
                pass

        if has_previous:
            with self._lock:
                self._login_tokens[token_hash] = ("pending_choice", expiry, device_id, None)
            LOGGER.info(
                "QR: device %s has previous session — awaiting choice",
                device_id[:8],
            )
            return True, True, session_name, video_count
        else:
            with self._lock:
                self._login_tokens[token_hash] = ("activated", expiry, device_id, None)
            LOGGER.info("QR: device %s activated (new/same session)", device_id[:8])
            return True, False, "", 0

    def confirm_choice(self, raw_token: str, action: str) -> bool:
        """Set the user's Resume / Start-Fresh choice and activate the token.

        Called after the phone user taps one of the choice buttons.
        Returns True if the token was valid and is now activated.
        """
        if action not in ("resume", "new"):
            return False
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._lock:
            entry = self._login_tokens.get(token_hash)
        if entry is None:
            return False
        status, expiry, device_id, _ = entry
        if status != "pending_choice":
            return False
        if time.time() > expiry:
            with self._lock:
                self._login_tokens.pop(token_hash, None)
            return False
        with self._lock:
            self._login_tokens[token_hash] = ("activated", expiry, device_id, action)
        LOGGER.info(
            "QR: device %s chose action=%s",
            (device_id or "?")[:8], action,
        )
        return True

    def check_login_status(
        self, token_hash: str
    ) -> tuple[str, str | None, str | None]:
        """Return *(status, device_id, action)* for a login token.

        status: ``'pending'``, ``'pending_choice'``, ``'activated'``, or
                ``'expired'``.
        action: ``None``, ``'resume'``, or ``'new'``.
        """
        with self._lock:
            entry = self._login_tokens.get(token_hash)
        if entry is None:
            return "expired", None, None
        status, expiry, device_id, action = entry
        if time.time() > expiry:
            with self._lock:
                self._login_tokens.pop(token_hash, None)
            return "expired", None, None
        return status, device_id, action

    def invalidate_login_token(self, token_hash: str) -> None:
        """Remove a login token (e.g. after successful login or skip)."""
        with self._lock:
            self._login_tokens.pop(token_hash, None)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _check_rate_limit(self, ip: str) -> bool:
        """Return True if this *ip* is within the rate limit, False if throttled."""
        with self._rl_lock:
            if ip not in self._rl_buckets:
                self._rl_buckets[ip] = _RateBucket(tokens=float(_RL_BURST))
            return self._rl_buckets[ip].allow()

    def _purge_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [t for t, entry in self._tokens.items() if now > entry[1]]
            for t in expired:
                del self._tokens[t]
            expired_dl = [t for t, (_, exp) in self._dl_tokens.items() if now > exp]
            for t in expired_dl:
                del self._dl_tokens[t]
            expired_sess = [t for t, (exp, _) in self._session_tokens.items() if now > exp]
            for t in expired_sess:
                del self._session_tokens[t]

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

            # Sensitive API paths that consume a rate-limit token.
            _RATE_LIMITED = frozenset({
                "/api/qr/confirm",
                "/api/qr/choice",
                "/api/export/verify",
                "/api/session/videos",
            })

            def do_GET(self):  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                qs = urllib.parse.parse_qs(parsed.query)

                # Apply rate limiting to sensitive endpoints.
                if path in self._RATE_LIMITED:
                    ip = self.client_address[0]
                    if not server._check_rate_limit(ip):
                        self._err(429, "Too many requests — please wait and try again.")
                        return

                try:
                    if path in ("/", "/gallery"):
                        self._gallery()
                    elif path == "/api/videos":
                        self._api_videos()
                    elif path.startswith("/download/"):
                        self._download(path[len("/download/"):])
                    elif path.startswith("/export/dl/"):
                        self._export_dl(path[len("/export/dl/"):])
                    elif path.startswith("/export/"):
                        self._export_page(path[len("/export/"):])
                    elif path == "/api/session/videos":
                        self._session_videos(
                            qs.get("token", [""])[0],
                            qs.get("device_id", [""])[0],
                        )
                    elif path.startswith("/session/"):
                        self._session_page(path[len("/session/"):])
                    elif path == "/api/export/verify":
                        self._export_verify(
                            qs.get("token", [""])[0],
                            qs.get("device_id", [""])[0],
                        )
                    elif path == "/qr/activate":
                        self._qr_activate_page(qs.get("token", [""])[0])
                    elif path == "/api/qr/confirm":
                        self._qr_confirm(
                            qs.get("token", [""])[0],
                            qs.get("device_id", [""])[0],
                        )
                    elif path == "/api/qr/choice":
                        self._qr_choice(
                            qs.get("token", [""])[0],
                            qs.get("action", [""])[0],
                        )
                    else:
                        self._err(404, "Not found")
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Share server error: %s", exc)
                    self._err(500, "Internal error")

            # ── Gallery pages ────────────────────────────────────────────

            def _gallery(self):
                session_name, videos = server._get_snapshot()
                host = self.headers.get("Host", f"localhost:{server.port}")
                items = ""
                for v in videos:
                    dl = f"http://{host}/download/{v.id}"
                    items += (
                        f'<div class="card">'
                        f'<div class="icon">&#x25b6;</div>'
                        f'<div class="info">'
                        f'<div class="title">{_esc(v.title)}</div>'
                        f'<div class="meta">{_esc(v.duration_label)}'
                        f' &middot; {_esc(v.created_label)}</div>'
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

            # ── Export ───────────────────────────────────────────────────

            def _export_page(self, token: str):
                """HTML page that verifies device identity before download."""
                html = _EXPORT_HTML.replace("__TOKEN__", _esc(token))
                self._html(html)

            def _export_verify(self, token: str, device_id: str):
                """Verify device_id; on success issue a one-time dl_token."""
                if not token:
                    self._json({"ok": False, "error": "Missing token"})
                    return
                ok, video_id = server.verify_export_token(token, device_id)
                if not ok:
                    self._json({
                        "ok": False,
                        "error": (
                            "This link has expired, or you must use the same "
                            "device that started the session to download."
                        ),
                    })
                    return
                dl_token = server.create_dl_token(video_id)
                host = self.headers.get("Host", f"localhost:{server.port}")
                dl_url = f"http://{host}/export/dl/{dl_token}"
                self._json({"ok": True, "download_url": dl_url})

            def _export_dl(self, dl_token: str):
                """Stream the video using a one-time 60-second download token."""
                video_id = server.resolve_dl_token(dl_token)
                if video_id is None:
                    self._err(410, "Download link expired or already used")
                    return
                self._download(video_id)

            # ── Session Gallery ──────────────────────────────────────────

            def _session_page(self, token: str):
                """HTML page that verifies device identity then shows the gallery."""
                html = _SESSION_HTML.replace("__TOKEN__", _esc(token))
                self._html(html)

            def _session_videos(self, token: str, device_id: str):
                """Verify device, return session gallery JSON."""
                if not token:
                    self._json({"ok": False, "error": "Missing token"})
                    return
                if not server._check_session_token(token, device_id):
                    self._json({
                        "ok": False,
                        "error": (
                            "This link has expired, or you must use the same "
                            "device that started the session to view recordings."
                        ),
                    })
                    return
                session_name, videos = server._get_snapshot()
                host = self.headers.get("Host", f"localhost:{server.port}")
                self._json({
                    "ok": True,
                    "session_name": session_name,
                    "videos": [
                        {
                            "id": v.id,
                            "title": v.title,
                            "duration": v.duration_label,
                            "created": v.created_label,
                            "download_url": f"http://{host}/download/{v.id}",
                        }
                        for v in videos
                    ],
                })

            # ── QR Login ─────────────────────────────────────────────────

            def _qr_activate_page(self, token: str):
                """HTML page served when a phone opens /qr/activate?token=<raw>."""
                html = _LOGIN_HTML.replace("__TOKEN__", _esc(token))
                self._html(html)

            def _qr_confirm(self, token: str, device_id: str):
                """Phone browser confirms scan; returns needs_choice flag."""
                if not token or not device_id:
                    self._json({"ok": False, "error": "Missing token or device_id"})
                    return
                ok, needs_choice, session_name, video_count = server.handle_qr_confirm(
                    token, device_id
                )
                if not ok:
                    self._json({"ok": False, "error": "Invalid or expired QR code"})
                    return
                if needs_choice:
                    self._json({
                        "ok": True,
                        "needs_choice": True,
                        "session_name": session_name,
                        "video_count": video_count,
                    })
                else:
                    self._json({"ok": True, "needs_choice": False})

            def _qr_choice(self, token: str, action: str):
                """Phone submits Resume or Start-Fresh choice."""
                if not token or action not in ("resume", "new"):
                    self._json({"ok": False, "error": "Invalid request"})
                    return
                if server.confirm_choice(token, action):
                    self._json({"ok": True})
                else:
                    self._json({
                        "ok": False,
                        "error": "QR code expired. Please rescan the mirror.",
                    })

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
# Session gallery HTML — served when a phone opens /session/<token>
# ---------------------------------------------------------------------------

_SESSION_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Mirror &mdash; Gallery</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#f5f0ec;color:#3c3530;padding-bottom:40px}
#verify-card{display:flex;align-items:center;justify-content:center;
             min-height:100vh;padding:24px;background:#1a1614}
.vcard{background:#2a2420;border-radius:20px;padding:36px 28px;
       max-width:340px;width:100%;text-align:center}
.vicon{font-size:52px;margin-bottom:16px}
.status{font-size:15px;padding:16px;border-radius:12px;background:#3a3028;
        color:#d0c8c0;transition:background .3s,color .3s}
.err{background:#3a2020!important;color:#e87070!important}
#gallery{display:none}
header{background:#2e2925;color:#f0ebe5;padding:20px}
header h1{font-size:20px;font-weight:600;margin-bottom:4px}
header p{font-size:13px;color:#a09590}
.list{padding:16px;display:flex;flex-direction:column;gap:12px}
.card{background:#fff;border-radius:14px;padding:16px;
      display:flex;align-items:center;gap:14px;
      box-shadow:0 1px 3px rgba(0,0,0,.08)}
.cicon{width:44px;height:44px;border-radius:10px;background:#e8e0da;
       display:flex;align-items:center;justify-content:center;
       font-size:20px;flex-shrink:0}
.info{flex:1;min-width:0}
.title{font-size:15px;font-weight:600;margin-bottom:3px}
.meta{font-size:12px;color:#9d9590}
.dl{background:#3c3530;color:#fff;padding:10px 16px;border-radius:10px;
    text-decoration:none;font-size:14px;font-weight:600;flex-shrink:0}
.empty{text-align:center;color:#9d9590;padding:40px 20px;font-size:15px}
</style>
</head>
<body>
<div id="verify-card">
  <div class="vcard">
    <div class="vicon">&#x1f4f9;</div>
    <div class="status" id="st">Verifying access&hellip;</div>
  </div>
</div>
<div id="gallery"></div>
<script>
(function(){
var token='__TOKEN__';
var did=localStorage.getItem('mirror_device_id')||'';
var st=document.getElementById('st');
var verifyCard=document.getElementById('verify-card');
var galleryDiv=document.getElementById('gallery');

function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

fetch('/api/session/videos?token='+encodeURIComponent(token)+'&device_id='+encodeURIComponent(did))
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok){
      verifyCard.style.display='none';
      var items='';
      if(!d.videos||!d.videos.length){
        items='<p class="empty">No recordings yet.</p>';
      }else{
        d.videos.forEach(function(v){
          items+='<div class="card">'
            +'<div class="cicon">&#x25b6;</div>'
            +'<div class="info">'
            +'<div class="title">'+esc(v.title)+'</div>'
            +'<div class="meta">'+esc(v.duration)+' &middot; '+esc(v.created)+'</div>'
            +'</div>'
            +'<a href="'+esc(v.download_url)+'" class="dl" download>&#x2B07;</a>'
            +'</div>';
        });
      }
      galleryDiv.innerHTML=
        '<header><h1>'+esc(d.session_name||'Smart Mirror')+'</h1>'
        +'<p>Smart Mirror recordings &mdash; tap &#x2B07; to save to your phone</p></header>'
        +'<div class="list">'+items+'</div>';
      galleryDiv.style.display='block';
    }else{
      st.className='status err';
      st.textContent=d.error||'Not authorized or link expired.';
    }
  })
  .catch(function(e){
    st.className='status err';
    st.textContent='Could not reach mirror: '+e.message;
  });
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# QR login HTML — served when a phone opens /qr/activate?token=<raw>
# ---------------------------------------------------------------------------

_LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Mirror &mdash; Start Session</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#1a1614;color:#f0ebe5;display:flex;align-items:center;
     justify-content:center;min-height:100vh;padding:24px;text-align:center}
.card{background:#2a2420;border-radius:20px;padding:36px 28px;max-width:340px;width:100%}
.icon{font-size:52px;margin-bottom:16px}
h1{font-size:22px;font-weight:600;margin-bottom:8px}
.sub{font-size:14px;color:#9d9590;margin-bottom:20px;line-height:1.5}
.status{font-size:15px;padding:16px;border-radius:12px;background:#3a3028;
        color:#d0c8c0;transition:background .3s,color .3s;margin-bottom:0}
.ok{background:#1e3020!important;color:#7de870!important}
.err{background:#3a2020!important;color:#e87070!important}
.btn-row{display:flex;flex-direction:column;gap:10px;margin-top:16px}
.btn{display:block;width:100%;padding:16px;border-radius:14px;border:none;
     font-size:15px;font-weight:600;cursor:pointer;text-align:center;
     line-height:1.3;transition:opacity .15s}
.btn:active{opacity:.75}
.btn-resume{background:#2e6e3d;color:#e8fce0}
.btn-fresh{background:#6e2e2e;color:#fce8e8}
</style>
</head>
<body>
<div class="card">
  <div class="icon">&#x1fa9e;</div>
  <h1>Smart Mirror</h1>
  <p class="sub" id="sub">Connecting to your session&hellip;</p>
  <div class="status" id="st">Please wait&hellip;</div>
  <div class="btn-row" id="btns" style="display:none"></div>
</div>
<script>
(function(){
function uuid4(){
  return([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g,function(c){
    return(c^crypto.getRandomValues(new Uint8Array(1))[0]&15>>c/4).toString(16);
  });
}
var token='__TOKEN__';
var did=localStorage.getItem('mirror_device_id');
if(!did){did=uuid4();localStorage.setItem('mirror_device_id',did);}
var st=document.getElementById('st');
var sub=document.getElementById('sub');
var btns=document.getElementById('btns');

function showOk(msg){
  st.className='status ok';st.textContent=msg;btns.style.display='none';
}
function showErr(msg){
  st.className='status err';st.textContent=msg;btns.style.display='none';
}

function sendChoice(action){
  btns.style.display='none';
  st.className='status';st.textContent='Please wait\u2026';
  fetch('/api/qr/choice?token='+encodeURIComponent(token)+'&action='+action)
    .then(function(r){return r.json();})
    .then(function(d){
      if(d.ok){
        showOk('\u2713 Mirror is ready \u2014 you can put your phone away.');
      }else{
        showErr('Error: '+(d.error||'Unknown error. Try scanning again.'));
      }
    })
    .catch(function(e){showErr('Could not reach mirror: '+e.message);});
}

function showChoice(sn,vc){
  sub.textContent='Someone else has been using this mirror since your last visit.';
  st.className='status';
  st.textContent='What would you like to do?';

  var rb=document.createElement('button');
  rb.className='btn btn-resume';
  rb.textContent='Resume \u201c'+sn+'\u201d'+(vc>0?' \u2014 '+vc+' video'+(vc===1?'':'s'):'');
  rb.onclick=function(){sendChoice('resume');};

  var nb=document.createElement('button');
  nb.className='btn btn-fresh';
  nb.textContent='Start a Fresh Session';
  nb.onclick=function(){sendChoice('new');};

  btns.innerHTML='';
  btns.appendChild(rb);
  btns.appendChild(nb);
  btns.style.display='flex';
}

fetch('/api/qr/confirm?token='+encodeURIComponent(token)+'&device_id='+encodeURIComponent(did))
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok){
      if(d.needs_choice){
        showChoice(d.session_name||'Previous Session', d.video_count||0);
      }else{
        showOk('\u2713 Mirror is ready \u2014 you can put your phone away.');
      }
    }else{
      showErr('Error: '+(d.error||'Unknown error. Try scanning again.'));
    }
  })
  .catch(function(e){showErr('Could not reach mirror: '+e.message);});
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Export HTML — served when a phone opens /export/<token>
# ---------------------------------------------------------------------------

_EXPORT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Mirror &mdash; Download</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#1a1614;color:#f0ebe5;display:flex;align-items:center;
     justify-content:center;min-height:100vh;padding:24px;text-align:center}
.card{background:#2a2420;border-radius:20px;padding:36px 28px;max-width:340px;width:100%}
.icon{font-size:52px;margin-bottom:16px}
h1{font-size:22px;font-weight:600;margin-bottom:8px}
.sub{font-size:14px;color:#9d9590;margin-bottom:20px;line-height:1.5}
.status{font-size:15px;padding:16px;border-radius:12px;background:#3a3028;
        color:#d0c8c0;transition:background .3s,color .3s}
.ok{background:#1e3020!important;color:#7de870!important}
.err{background:#3a2020!important;color:#e87070!important}
.dl-btn{display:block;margin-top:16px;padding:18px;border-radius:14px;
        background:#2e6e3d;color:#e8fce0;text-decoration:none;
        font-size:16px;font-weight:600}
</style>
</head>
<body>
<div class="card">
  <div class="icon">&#x1f4f9;</div>
  <h1>Download Video</h1>
  <p class="sub">Verifying your access&hellip;</p>
  <div class="status" id="st">Please wait&hellip;</div>
  <a id="dl" style="display:none" class="dl-btn">&#x2B07; Download Video</a>
</div>
<script>
(function(){
var token='__TOKEN__';
var did=localStorage.getItem('mirror_device_id')||'';
var st=document.getElementById('st');
var dl=document.getElementById('dl');

fetch('/api/export/verify?token='+encodeURIComponent(token)+'&device_id='+encodeURIComponent(did))
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok){
      st.className='status ok';
      st.textContent='Verified \u2014 tap below to save the video to your phone.';
      dl.href=d.download_url;
      dl.style.display='block';
    }else{
      st.className='status err';
      st.textContent=d.error||'Not authorized or link expired.';
    }
  })
  .catch(function(e){
    st.className='status err';
    st.textContent='Could not reach mirror: '+e.message;
  });
})();
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
<title>{name} &mdash; Smart Mirror</title>
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
  <p>Smart Mirror recordings &mdash; tap Download to save to your phone</p>
</header>
<div class="list">
{items}
</div>
</body>
</html>
"""
