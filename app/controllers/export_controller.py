"""Export controller — QR-based video sharing.

Exposed to QML as `exportController`.

Two workflows
─────────────
1. Session Hub QR  (show_session_qr)
   Mirror displays a QR that phones scan to open the mobile gallery page
   (http://<Pi-IP>:<port>/).  All recordings in the session are listed
   with one-tap download links.

2. Export QR  (export_video)
   Mirror and control both show a QR pointing to a time-limited
   single-video download link (valid 10 minutes).  The link is served
   directly from the embedded HTTP server — no cloud needed.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from app.services.gallery_service import GalleryService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.network_service import get_local_ip
from app.services.qr_service import generate_qr_png
from app.services.session_service import SessionService
from app.services.share_server import ShareServer

LOGGER = logging.getLogger(__name__)

_EXPORT_TTL = 600   # seconds


class ExportController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        gallery_service: GalleryService,
        session_service: SessionService,
        mirror_display: MirrorDisplayService,
        share_server: ShareServer,
        temp_dir: Path,
        app_controller,
    ) -> None:
        super().__init__()
        self._gallery = gallery_service
        self._session = session_service
        self._mirror = mirror_display
        self._server = share_server
        self._temp_dir = temp_dir
        self._app = app_controller

        # QR display state
        self._mode = ""             # "session" | "export" | ""
        self._qr_image_url = ""     # file:// URL of the generated PNG
        self._export_url = ""       # the http:// URL encoded in the QR
        self._server_url = ""       # base URL of the share server
        self._token = ""            # active export token
        self._remaining = 0         # countdown seconds
        self._error = ""

        # Countdown timer for export link expiry
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # QML properties
    # ------------------------------------------------------------------

    @Property(str, notify=changed)
    def mode(self) -> str:
        """'session' | 'export' | '' (inactive)."""
        return self._mode

    @Property(bool, notify=changed)
    def isActive(self) -> bool:
        return bool(self._mode)

    @Property(str, notify=changed)
    def qrImageUrl(self) -> str:
        return self._qr_image_url

    @Property(str, notify=changed)
    def exportUrl(self) -> str:
        return self._export_url

    @Property(str, notify=changed)
    def serverUrl(self) -> str:
        return self._server_url

    @Property(int, notify=changed)
    def remainingSeconds(self) -> int:
        return self._remaining

    @Property(str, notify=changed)
    def remainingText(self) -> str:
        m, s = divmod(self._remaining, 60)
        return f"{m:02d}:{s:02d}"

    @Property(str, notify=changed)
    def errorMessage(self) -> str:
        return self._error

    # ------------------------------------------------------------------
    # Slots (callable from QML)
    # ------------------------------------------------------------------

    @Slot()
    def showSessionQr(self) -> None:
        """Show the session-hub QR on the mirror (gallery page, device-gated)."""
        self._stop_countdown()
        self._error = ""
        try:
            self._refresh_server_data()
            session = self._session.get_active_session()
            owner_device_id = session.device_id if session else ""
            token = self._server.create_session_token(owner_device_id)
            url = f"{self._server_url}/session/{token}"
            qr_path = self._gen_qr(url, "session_qr.png")
            self._mode = "session"
            self._export_url = url
            self._qr_image_url = qr_path.as_uri()
            # Navigate first so close_active() runs before we set the mirror.
            self._app.showExport()
            self._mirror.show_qr(qr_path.as_uri(), "Scan to view & download recordings")
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("showSessionQr failed: %s", exc)
            self._error = str(exc)
        self.changed.emit()

    @Slot(str)
    def exportVideo(self, video_id: str) -> None:
        """Generate a 10-minute download QR for a specific video."""
        self._stop_countdown()
        self._error = ""
        try:
            self._refresh_server_data()
            video = self._gallery.get_video(video_id)
            if video is None:
                raise RuntimeError("Video not found.")
            session = self._session.get_active_session()
            owner_device_id = session.device_id if session else ""
            self._token = self._server.create_token(video_id, owner_device_id)
            url = f"{self._server_url}/export/{self._token}"
            qr_path = self._gen_qr(url, "export_qr.png")
            self._mode = "export"
            self._export_url = url
            self._qr_image_url = qr_path.as_uri()
            self._remaining = _EXPORT_TTL
            # Navigate first so close_active() runs before we set the mirror.
            self._app.showExport()
            self._mirror.show_qr(qr_path.as_uri(), f"Scan to download  ·  {video.title}")
            self._countdown.start()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("exportVideo failed: %s", exc)
            self._error = str(exc)
        self.changed.emit()

    @Slot()
    def close(self) -> None:
        """Dismiss the export screen and restore the mirror."""
        self._stop_countdown()
        self._mode = ""
        self._qr_image_url = ""
        self._export_url = ""
        self._token = ""
        self._remaining = 0
        self._error = ""
        self._mirror.show_idle_black()
        self._app.showDashboard()
        self.changed.emit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _refresh_server_data(self) -> None:
        """Push current session + gallery snapshot to the HTTP server."""
        session = self._session.get_active_session()
        session_name = session.name if session else "Smart Mirror"
        session_id = session.id if session else None
        videos = self._gallery.list_videos(session_id=session_id)
        self._server.update_gallery(session_name, videos)
        ip = get_local_ip()
        port = self._server.port
        self._server_url = f"http://{ip}:{port}"

    def _gen_qr(self, url: str, filename: str) -> Path:
        path = self._temp_dir / filename
        return generate_qr_png(url, path)

    def _stop_countdown(self) -> None:
        if self._countdown.isActive():
            self._countdown.stop()

    def _tick(self) -> None:
        self._remaining = max(0, self._remaining - 1)
        if self._remaining == 0:
            self._countdown.stop()
            self._app.showStatus("Export link expired.")
        self.changed.emit()
