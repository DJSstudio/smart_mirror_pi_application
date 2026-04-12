"""QR login controller.

Manages the startup QR-scan flow:
  1. Generates a short-lived login token and QR code.
  2. Shows the QR on the mirror; shows the waiting page on the control window.
  3. Polls the share server every 2 seconds for a phone scan.
  4. On scan: links the phone's device_id to a session (new or resumed),
     refreshes the session/gallery controllers, and navigates to the dashboard.
  5. If the token expires before scanning it regenerates the QR automatically.

Exposed to QML as ``loginController``.
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

_POLL_INTERVAL_MS = 2_000   # 2 seconds


class LoginController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        share_server: ShareServer,
        session_service: SessionService,
        session_ctrl,        # SessionController — refreshed after login
        gallery_ctrl,        # GalleryController — refreshed after login
        mirror_display: MirrorDisplayService,
        app_controller,
        temp_dir: Path,
    ) -> None:
        super().__init__()
        self._server = share_server
        self._session_svc = session_service
        self._session_ctrl = session_ctrl
        self._gallery_ctrl = gallery_ctrl
        self._mirror = mirror_display
        self._app = app_controller
        self._temp_dir = temp_dir

        self._qr_image_url = ""
        self._server_url = ""
        self._token_hash = ""
        self._error = ""

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

    # ------------------------------------------------------------------
    # QML properties
    # ------------------------------------------------------------------

    @Property(str, notify=changed)
    def qrImageUrl(self) -> str:
        return self._qr_image_url

    @Property(str, notify=changed)
    def serverUrl(self) -> str:
        return self._server_url

    @Property(bool, notify=changed)
    def isPending(self) -> bool:
        return self._poll_timer.isActive()

    @Property(str, notify=changed)
    def errorMessage(self) -> str:
        return self._error

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def startLogin(self) -> None:
        """Generate a fresh QR login token and begin polling."""
        self._stop_poll()
        self._error = ""
        try:
            ip = get_local_ip()
            port = self._server.port
            self._server_url = f"http://{ip}:{port}"

            raw_token, token_hash = self._server.create_login_token()
            self._token_hash = token_hash

            url = f"{self._server_url}/qr/activate?token={raw_token}"
            qr_path = generate_qr_png(url, self._temp_dir / "login_qr.png")
            self._qr_image_url = qr_path.as_uri()

            # Navigate first so any previous media is cleared, then set mirror.
            self._app.showLogin()
            self._mirror.show_qr(
                qr_path.as_uri(),
                "Scan with your phone to start",
            )
            self._poll_timer.start()
            LOGGER.info("Login QR generated: %s", url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("startLogin failed: %s", exc)
            self._error = str(exc)
        self.changed.emit()

    @Slot()
    def skipLogin(self) -> None:
        """Proceed without scanning — uses the auto-created anonymous session."""
        self._stop_poll()
        if self._token_hash:
            self._server.invalidate_login_token(self._token_hash)
            self._token_hash = ""
        self._app.showDashboard()
        self.changed.emit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        if not self._token_hash:
            return
        status, device_id = self._server.check_login_status(self._token_hash)
        if status == "activated" and device_id:
            self._stop_poll()
            self._on_activated(device_id)
        elif status == "expired":
            LOGGER.debug("Login QR expired — regenerating")
            self.startLogin()

    def _on_activated(self, device_id: str) -> None:
        try:
            session, was_resumed = self._session_svc.get_or_resume_for_device(device_id)
            LOGGER.info(
                "Login: device=%s  session=%s  resumed=%s",
                device_id[:8], session.id[:8], was_resumed,
            )
            # Refresh controllers to pick up the (possibly switched) session.
            self._session_ctrl.refresh()
            self._gallery_ctrl.refresh()

            if was_resumed:
                self._app.showStatus(f"Welcome back — resuming {session.name}")
            else:
                self._app.showStatus(f"Session started — {session.name}")

            # showDashboard calls close_active() which clears the mirror QR.
            self._app.showDashboard()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Login activation failed: %s", exc)
            self._error = str(exc)
            self.changed.emit()

    def _stop_poll(self) -> None:
        if self._poll_timer.isActive():
            self._poll_timer.stop()
