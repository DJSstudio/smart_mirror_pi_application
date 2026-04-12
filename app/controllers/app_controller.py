from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.playback_service import PlaybackService


class AppController(QObject):
    currentPageChanged = Signal()
    statusMessageChanged = Signal()
    errorMessageChanged = Signal()

    def __init__(self, playback_service: PlaybackService) -> None:
        super().__init__()
        self._playback_service = playback_service
        self._current_page = "dashboard"
        self._status_message = "Ready"
        self._error_message = ""
        self._recording_controller = None

    def attach_recording_controller(self, controller) -> None:
        self._recording_controller = controller

    @Property(str, notify=currentPageChanged)
    def currentPage(self) -> str:
        return self._current_page

    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=errorMessageChanged)
    def errorMessage(self) -> str:
        return self._error_message

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

    def show_player_page(self) -> None:
        self._navigate("player", close_media=False)

    def show_compare_page(self) -> None:
        self._navigate("compare", close_media=False)

    def show_live_compare_page(self) -> None:
        self._navigate("live_compare", close_media=False)

    @Slot(str)
    def showStatus(self, message: str) -> None:
        self._status_message = message
        self.statusMessageChanged.emit()

    @Slot(str)
    def showError(self, message: str) -> None:
        self._error_message = message
        self.errorMessageChanged.emit()

    @Slot()
    def clearError(self) -> None:
        self._error_message = ""
        self.errorMessageChanged.emit()

    def _navigate(self, page: str, *, close_media: bool) -> None:
        if (
            self._recording_controller is not None
            and getattr(self._recording_controller, "navigation_locked")()
            and page != self._current_page
        ):
            self.showError("Finish or discard the current recording before leaving this screen.")
            return
        if close_media:
            self._playback_service.close_active()
        if self._current_page != page:
            self._current_page = page
            self.currentPageChanged.emit()
