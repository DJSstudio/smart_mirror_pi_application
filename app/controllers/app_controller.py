"""Top-level application controller.

Manages page navigation and top-level status/error messaging.
Exposed to QML as `appController`.
"""
from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Property, Signal, Slot

LOGGER = logging.getLogger(__name__)

_VALID_PAGES = frozenset({
    "login", "dashboard", "recording", "gallery",
    "player", "compare", "live_compare", "settings", "export",
})


class AppController(QObject):
    currentPageChanged = Signal()
    statusMessageChanged = Signal()
    errorMessageChanged = Signal()

    def __init__(self, playback_service) -> None:
        super().__init__()
        self._playback = playback_service
        self._page = "dashboard"
        self._status = ""
        self._error = ""
        self._recording_ctrl = None  # set via attach_recording_controller

    def attach_recording_controller(self, ctrl) -> None:
        self._recording_ctrl = ctrl

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @Property(str, notify=currentPageChanged)
    def currentPage(self) -> str:
        return self._page

    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status

    @Property(str, notify=errorMessageChanged)
    def errorMessage(self) -> str:
        return self._error

    # ------------------------------------------------------------------
    # Navigation slots (callable from QML)
    # ------------------------------------------------------------------

    @Slot()
    def showLogin(self) -> None:
        # Do NOT close media — the login controller manages mirror state.
        self._navigate("login", close_media=False)

    @Slot()
    def showDashboard(self) -> None:
        self._navigate("dashboard", close_media=True)

    @Slot()
    def showRecording(self) -> None:
        self._navigate("recording", close_media=True)

    @Slot()
    def showGallery(self) -> None:
        self._navigate("gallery", close_media=True)

    @Slot()
    def showSettings(self) -> None:
        self._navigate("settings", close_media=True)

    # Called by other controllers (not from QML directly)
    def show_player(self) -> None:
        self._navigate("player", close_media=False)

    def show_compare(self) -> None:
        self._navigate("compare", close_media=False)

    def show_live_compare(self) -> None:
        self._navigate("live_compare", close_media=False)

    def showExport(self) -> None:
        self._navigate("export", close_media=True)

    # ------------------------------------------------------------------
    # Status / error
    # ------------------------------------------------------------------

    @Slot(str)
    def showStatus(self, message: str) -> None:
        self._status = message
        self.statusMessageChanged.emit()

    @Slot(str)
    def showError(self, message: str) -> None:
        self._error = message
        self.errorMessageChanged.emit()

    @Slot()
    def clearError(self) -> None:
        self._error = ""
        self.errorMessageChanged.emit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _navigate(self, page: str, *, close_media: bool) -> None:
        if page == self._page:
            return
        if self._recording_ctrl and self._recording_ctrl.navigation_locked():
            self.showError(
                "Finish or discard the current recording before leaving this screen."
            )
            return
        if close_media:
            self._playback.close_active()
        self._page = page
        self.currentPageChanged.emit()
        # Clear any stale error banner now that we've moved to a fresh screen —
        # otherwise a transient error stays pinned across every page until the
        # customer taps the tiny dismiss button (unattended kiosk → never).
        if self._error:
            self._error = ""
            self.errorMessageChanged.emit()
        LOGGER.debug("Navigated to page: %s", page)
