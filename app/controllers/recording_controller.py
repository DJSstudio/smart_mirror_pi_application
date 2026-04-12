"""Recording workflow controller.

Manages the full lifecycle:
  idle → countdown → recording → review → (save | discard) → idle

Exposed to QML as `recordingController`.
"""
from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from app.models.entities import PreparedRecording
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.recording_service import RecordingService

LOGGER = logging.getLogger(__name__)


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
        self._camera = camera_service
        self._recording_svc = recording_service
        self._mirror = mirror_display
        self._app = app_controller
        self._session_ctrl = session_controller
        self._gallery_ctrl = gallery_controller

        # Countdown timer (fires every second)
        self._cd_timer = QTimer(self)
        self._cd_timer.setInterval(1000)
        self._cd_timer.timeout.connect(self._tick_countdown)

        # Elapsed timer (fires every second while recording)
        self._el_timer = QTimer(self)
        self._el_timer.setInterval(1000)
        self._el_timer.timeout.connect(self._tick_elapsed)

        # State
        self._busy = False
        self._recording = False
        self._countdown = 0
        self._elapsed = 0
        self._preview_source = ""
        self._review_source = ""
        self._error = ""
        self._backend_label = camera_service.current_backend_label()
        self._prepared: PreparedRecording | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @Property(bool, notify=changed)
    def isBusy(self) -> bool:
        return self._busy

    @Property(bool, notify=changed)
    def isRecording(self) -> bool:
        return self._recording

    @Property(bool, notify=changed)
    def hasReview(self) -> bool:
        return self._prepared is not None

    @Property(int, notify=changed)
    def countdown(self) -> int:
        return self._countdown

    @Property(str, notify=changed)
    def elapsedText(self) -> str:
        m, s = divmod(self._elapsed, 60)
        return f"{m:02d}:{s:02d}"

    @Property(str, notify=changed)
    def previewSource(self) -> str:
        return self._preview_source

    @Property(str, notify=changed)
    def reviewSource(self) -> str:
        return self._review_source

    @Property(str, notify=changed)
    def errorMessage(self) -> str:
        return self._error

    @Property(str, notify=changed)
    def backendLabel(self) -> str:
        return self._backend_label

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def beginRecording(self) -> None:
        """Start the pre-recording countdown."""
        if self._busy or self._recording or self._prepared:
            return
        self._clear_error()
        self._busy = True
        self._countdown = 3
        self._emit()
        self._cd_timer.start()

    @Slot()
    def stopRecording(self) -> None:
        """Stop recording and prepare the clip for review."""
        if not self._recording:
            return
        self._busy = True
        self._emit()
        try:
            capture = self._camera.stop(discard=False)
            self._el_timer.stop()
            self._mirror.show_idle_black()
            self._recording = False
            self._preview_source = ""
            if capture is None:
                raise RuntimeError("Recording stopped but no file was produced.")
            self._prepared = self._recording_svc.prepare_review(capture)
            self._review_source = self._prepared.file_path.resolve().as_uri()
            self._app.showStatus("Recording complete — review and save or discard.")
        except Exception as exc:  # noqa: BLE001
            self._set_error(str(exc))
            self._app.showError(str(exc))
        finally:
            self._busy = False
            self._emit()

    @Slot()
    def saveRecording(self) -> None:
        """Persist the reviewed clip to the gallery."""
        if self._prepared is None or self._busy:
            return
        self._busy = True
        self._emit()
        try:
            video = self._recording_svc.save_prepared(self._prepared)
            self._prepared = None
            self._review_source = ""
            self._app.showStatus(f"Saved — {video.title}")
            self._gallery_ctrl.refresh()
            self._session_ctrl.refresh()
            self._app.showGallery()
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"Failed to save recording: {exc}")
            self._app.showError(self._error)
        finally:
            self._busy = False
            self._emit()

    @Slot()
    def discardRecording(self) -> None:
        """Cancel recording or discard a reviewed clip."""
        if self._recording:
            self._camera.stop(discard=True)
            self._el_timer.stop()
            self._mirror.show_idle_black()
        if self._prepared:
            self._recording_svc.discard_prepared(self._prepared)
        self._cd_timer.stop()
        self._el_timer.stop()
        self._reset_state()
        self._app.showStatus("Recording discarded.")

    # ------------------------------------------------------------------
    # Used by AppController to gate navigation
    # ------------------------------------------------------------------

    def navigation_locked(self) -> bool:
        return self._recording or self._prepared is not None or self._countdown > 0

    # ------------------------------------------------------------------
    # Timer callbacks
    # ------------------------------------------------------------------

    def _tick_countdown(self) -> None:
        if self._countdown <= 1:
            self._cd_timer.stop()
            self._countdown = 0
            self._emit()
            self._start_now()
        else:
            self._countdown -= 1
            self._emit()

    def _start_now(self) -> None:
        try:
            preview = self._camera.start_recording()
            self._recording = True
            self._busy = False
            self._elapsed = 0
            self._preview_source = preview.control_preview_url
            self._backend_label = preview.backend
            self._mirror.show_live_preview(preview.mirror_preview_url)
            self._el_timer.start()
            self._app.showStatus("Recording…")
        except Exception as exc:  # noqa: BLE001
            self._busy = False
            self._recording = False
            self._preview_source = ""
            self._set_error(str(exc))
            self._app.showError(str(exc))
        finally:
            self._emit()

    def _tick_elapsed(self) -> None:
        self._elapsed += 1
        # Detect if the camera process crashed mid-recording
        if not self._camera.is_alive():
            LOGGER.warning("Camera process died during recording after %ds", self._elapsed)
            self._el_timer.stop()
            self._mirror.show_idle_black()
            self._recording = False
            self._preview_source = ""
            self._busy = False
            msg = (
                "Camera stopped unexpectedly. "
                "Check that the camera is connected and enabled (raspi-config → Interface Options → Camera)."
            )
            self._set_error(msg)
            self._app.showError(msg)
        self._emit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_state(self) -> None:
        self._busy = False
        self._recording = False
        self._countdown = 0
        self._elapsed = 0
        self._preview_source = ""
        self._review_source = ""
        self._prepared = None
        self._clear_error()

    def _set_error(self, msg: str) -> None:
        self._error = msg
        self._emit()

    def _clear_error(self) -> None:
        if self._error:
            self._error = ""
            self._emit()

    def _emit(self) -> None:
        self.changed.emit()
