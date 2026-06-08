"""QR login controller.

Manages the startup QR-scan flow:
  1. Generates a short-lived login token and QR code.
  2. Shows the QR on the mirror; shows the waiting page on the control window.
  3. Polls the share server every 2 seconds for a phone scan.
  4. If the device has a previous session the phone shows Resume / Start-Fresh
     options; the user's choice arrives via ``/api/qr/choice``.
  5. On activation: links device_id to a session (new or resumed),
     refreshes the session/gallery controllers, and navigates to the dashboard.
  6. If the token expires before scanning it regenerates the QR automatically.

Exposed to QML as ``loginController``.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from app.database.repositories import FootfallRepository
from app.models.entities import SessionRecord
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
        gallery_service: GalleryService,
        footfall_repo: FootfallRepository,
        session_ctrl,        # SessionController — refreshed after login
        gallery_ctrl,        # GalleryController — refreshed after login
        mirror_display: MirrorDisplayService,
        app_controller,
        temp_dir: Path,
    ) -> None:
        super().__init__()
        self._server = share_server
        self._session_svc = session_service
        self._gallery_svc = gallery_service
        self._footfall = footfall_repo
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

        # Register device-history callback so the share server can decide
        # whether to show the Resume / Start-Fresh choice on the phone.
        # Called from HTTP handler threads — safe because SQLite WAL +
        # check_same_thread=False are already configured.
        self._server.set_device_checker(self._check_device)

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
        """Called from QML 'Log Out' button — manual logout then show QR."""
        self._do_logout_and_show_qr(reason="manual")

    def autoLogout(self) -> None:
        """Called by the idle timer — auto-idle logout then show QR."""
        self._do_logout_and_show_qr(reason="auto_idle")

    def _do_logout_and_show_qr(self, reason: str) -> None:
        """Record the logout of any active session, then generate a fresh QR."""
        self._stop_poll()
        self._error = ""

        # Record logout of the currently active session (if any).
        # Only record logout for sessions that have a real user (device_id set).
        # Anonymous/placeholder sessions (created on startup before any scan)
        # are silently discarded — recording a logout for them pollutes footfall.
        active = self._session_svc.get_active_session()
        if active and active.device_id:
            self._footfall.record_logout(active.id, reason=reason)
            LOGGER.info(
                "Footfall: logout session=%s reason=%s", active.id[:8], reason
            )

        # Privacy: stop serving the previous session's recordings the moment we
        # return to the login screen — clears the cached gallery and invalidates
        # its session/export/download tokens so the next person on the LAN can't
        # reach them.
        self._server.clear_session_data()

        try:
            ip = get_local_ip()
            port = self._server.port
            self._server_url = f"{self._server.url_scheme}://{ip}:{port}"

            raw_token, token_hash = self._server.create_login_token()
            self._token_hash = token_hash

            url = f"{self._server_url}/qr/activate?token={raw_token}"
            # Use a timestamp-suffixed filename so the URI changes every
            # generation — Qt's Image won't reload if the source string is
            # identical, even with cache: false.
            qr_filename = f"login_qr_{int(time.time() * 1000)}.png"
            qr_path = generate_qr_png(url, self._temp_dir / qr_filename)
            self._qr_image_url = qr_path.as_uri()
            # Remove stale QR files to avoid temp dir accumulation.
            for old in self._temp_dir.glob("login_qr_*.png"):
                if old != qr_path:
                    try:
                        old.unlink()
                    except Exception:  # noqa: BLE001
                        pass

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

    def _check_device(self, device_id: str) -> tuple[bool, str, int]:
        """Callback invoked from the HTTP handler thread.

        Returns *(has_previous, session_name, video_count)*.

        Only returns has_previous=True when the device has a *different*
        session AND the current active session belongs to another known device
        (i.e. someone else has been using the mirror in between).

        Anonymous sessions created automatically by the app (e.g. on startup
        or after a crash) are treated as unclaimed placeholders — the device
        resumes silently without a choice dialog.
        """
        try:
            session = self._session_svc.get_device_session(device_id)
            if session is None:
                return False, "", 0
            current = self._session_svc.get_active_session()
            # Same session still active — just silently re-link.
            if current and session.id == current.id:
                return False, "", 0
            # Current session is anonymous (auto-created placeholder, e.g. after
            # a crash/restart) — resume the device's session silently, no dialog.
            if not current or not current.device_id:
                return False, "", 0
            # A *different* known device owns the active session — ask the user.
            count = self._gallery_svc.count_videos(session_id=session.id)
            return True, session.name, count
        except Exception:  # noqa: BLE001
            return False, "", 0

    def _poll(self) -> None:
        if not self._token_hash:
            return
        status, device_id, action = self._server.check_login_status(self._token_hash)
        if status == "activated" and device_id:
            self._stop_poll()
            self._on_activated(device_id, action)
        elif status == "expired":
            LOGGER.debug("Login QR expired — regenerating")
            self._do_logout_and_show_qr(reason="qr_refresh")
        elif status == "pending":
            # Proactively regenerate 30 s before expiry so the mirror never
            # shows a QR that is about to expire when the user walks up.
            remaining = self._server.login_token_remaining(self._token_hash)
            if remaining < 30:
                LOGGER.debug("Login QR expiring in %ds — proactive refresh", remaining)
                self._do_logout_and_show_qr(reason="qr_refresh")
        # "pending_choice": user is mid-choice on phone — do not interrupt

    def _on_activated(self, device_id: str, action: str | None) -> None:
        try:
            if action == "new":
                session = self._new_session_for_device(device_id)
                msg = f"New session started — {session.name}"
            elif action == "resume":
                # Try to resume by stored device_id first.
                existing = self._session_svc.get_device_session(device_id)
                if existing:
                    session, _ = self._session_svc.get_or_resume_for_device(device_id)
                else:
                    # device_id not in DB — the user's browser got a new ID
                    # (Pi IP changed, localStorage cleared, etc.).  They saw the
                    # active session in the choice dialog and explicitly chose Resume,
                    # so relink that session to the new device_id.
                    session = self._session_svc.relink_active_session(device_id)
                    if session is None:
                        session, _ = self._session_svc.get_or_resume_for_device(device_id)
                    LOGGER.info(
                        "Footfall: relinked session %s to new device_id %s",
                        session.id[:8], device_id[:8],
                    )
                msg = f"Welcome back — resumed {session.name}"
            else:
                # Same-session re-scan or no choice needed.
                session, was_resumed = self._session_svc.get_or_resume_for_device(device_id)
                msg = (
                    f"Welcome back — resuming {session.name}"
                    if was_resumed
                    else f"Session started — {session.name}"
                )

            # Record the login event — also closes any open arc for another session.
            self._footfall.record_login(session)
            LOGGER.info(
                "Footfall: login session=%s device=%s", session.id[:8], device_id[:8]
            )

            self._session_ctrl.refresh()
            self._gallery_ctrl.refresh()
            self._app.showStatus(msg)
            # showDashboard calls close_active() which clears the mirror QR.
            self._app.showDashboard()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Login activation failed: %s", exc)
            self._error = str(exc)
            self.changed.emit()

    def _new_session_for_device(self, device_id: str) -> SessionRecord:
        """Close the device's previous session and start a brand-new one.

        Videos from the old session are kept — they remain accessible in the
        gallery.  The user can delete them manually if they want to.
        """
        prev = self._session_svc.get_device_session(device_id)
        if prev:
            LOGGER.info(
                "Start Fresh: closing session %s, videos are kept in gallery",
                prev.id[:8],
            )
        return self._session_svc.new_session_for_device(device_id)

    def _stop_poll(self) -> None:
        if self._poll_timer.isActive():
            self._poll_timer.stop()
