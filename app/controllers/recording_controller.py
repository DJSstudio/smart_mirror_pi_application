from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from app.models.entities import PreparedRecording
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.recording_service import RecordingService


class RecordingController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        camera_service: CameraService,
        recording_service: RecordingService,
        mirror_display: MirrorDisplayService,
        app_controller,
        session_controller,
        gallery_controller,
    ) -> None:
        super().__init__()
        self._camera_service = camera_service
        self._recording_service = recording_service
        self._mirror_display = mirror_display
        self._app_controller = app_controller
        self._session_controller = session_controller
        self._gallery_controller = gallery_controller
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_timer.setInterval(1000)
        self._is_busy = False
        self._is_recording = False
        self._countdown = 0
        self._elapsed_seconds = 0
        self._start_time: datetime | None = None
        self._preview_source = ""
        self._review_source = ""
        self._error_message = ""
        self._backend_label = camera_service.current_backend_label()
        self._prepared: PreparedRecording | None = None

    @Property(bool, notify=changed)
    def isBusy(self) -> bool:
        return self._is_busy

    @Property(bool, notify=changed)
    def isRecording(self) -> bool:
        return self._is_recording

    @Property(bool, notify=changed)
    def hasReview(self) -> bool:
        return bool(self._prepared)

    @Property(int, notify=changed)
    def countdown(self) -> int:
        return self._countdown

    @Property(str, notify=changed)
    def elapsedText(self) -> str:
        minutes, seconds = divmod(self._elapsed_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    @Property(str, notify=changed)
    def previewSource(self) -> str:
        return self._preview_source

    @Property(str, notify=changed)
    def reviewSource(self) -> str:
        return self._review_source

    @Property(str, notify=changed)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(str, notify=changed)
    def backendLabel(self) -> str:
        return self._backend_label

    @Slot()
    def beginRecording(self) -> None:
        if self._is_busy or self._is_recording or self._prepared is not None:
            return
        self._clear_error()
        self._is_busy = True
        self._countdown = 3
        self.changed.emit()
        self._countdown_timer.start(1000)
        self._app_controller.showStatus("Starting recording countdown")

    @Slot()
    def stopRecording(self) -> None:
        if not self._is_recording:
            return
        self._is_busy = True
        self.changed.emit()
        try:
            capture = self._camera_service.stop(discard=False)
            self._elapsed_timer.stop()
            self._mirror_display.show_idle_black()
            self._is_recording = False
            self._preview_source = ""
            if capture is None:
                raise RuntimeError("Recording stopped but no file was produced.")
            prepared = self._recording_service.prepare_review(capture)
            self._prepared = prepared
            self._review_source = prepared.file_path.resolve().as_uri()
            self._app_controller.showStatus("Recording ready to review")
        except Exception as exc:  # noqa: BLE001
            self._set_error(str(exc))
            self._app_controller.showError(str(exc))
        finally:
            self._is_busy = False
            self.changed.emit()

    @Slot()
    def saveRecording(self) -> None:
        if self._prepared is None or self._is_busy:
            return
        self._is_busy = True
        self.changed.emit()
        try:
            video = self._recording_service.save_prepared(self._prepared)
            self._prepared = None
            self._review_source = ""
            self._app_controller.showStatus(f"Saved {video.title}")
            self._gallery_controller.refresh()
            self._session_controller.refresh()
            self._app_controller.showGallery()
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"Failed to save recording: {exc}")
            self._app_controller.showError(self._error_message)
        finally:
            self._is_busy = False
            self.changed.emit()

    @Slot()
    def discardRecording(self) -> None:
        if self._is_recording:
            self._camera_service.stop(discard=True)
            self._elapsed_timer.stop()
            self._mirror_display.show_idle_black()
        if self._prepared is not None:
            self._recording_service.discard_prepared(self._prepared)
        self._prepared = None
        self._is_recording = False
        self._is_busy = False
        self._countdown_timer.stop()
        self._elapsed_timer.stop()
        self._countdown = 0
        self._elapsed_seconds = 0
        self._preview_source = ""
        self._review_source = ""
        self._clear_error()
        self.changed.emit()
        self._app_controller.showStatus("Recording discarded")

    def navigation_locked(self) -> bool:
        return self._is_recording or self._prepared is not None or self._countdown > 0

    def _tick_countdown(self) -> None:
        if self._countdown <= 1:
            self._countdown_timer.stop()
            self._countdown = 0
            self._start_recording_now()
            return
        self._countdown -= 1
        self.changed.emit()

    def _start_recording_now(self) -> None:
        try:
            preview = self._camera_service.start_recording()
            self._is_recording = True
            self._is_busy = False
            self._elapsed_seconds = 0
            self._start_time = datetime.now()
            self._preview_source = preview.control_preview_url
            self._backend_label = preview.backend
            self._mirror_display.show_recording_preview(preview.mirror_preview_url)
            self._elapsed_timer.start()
            self._app_controller.showStatus("Recording in progress")
        except Exception as exc:  # noqa: BLE001
            self._is_busy = False
            self._is_recording = False
            self._preview_source = ""
            self._set_error(str(exc))
            self._app_controller.showError(str(exc))
        finally:
            self.changed.emit()

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        self.changed.emit()

    def _set_error(self, message: str) -> None:
        self._error_message = message
        self.changed.emit()

    def _clear_error(self) -> None:
        if self._error_message:
            self._error_message = ""
            self.changed.emit()
