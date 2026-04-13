"""Recording workflow controller.

Manages the full lifecycle:
  idle → countdown → recording → review → (save | discard) → idle

Exposed to QML as `recordingController`.

Warm-up strategy
────────────────
The camera pipeline (ffmpeg → GStreamer/UDP) needs ~2-4 s to stabilise
before delivering clean, artefact-free frames.  To hide this we start the
camera at the *beginning* of the countdown rather than at its end:

  T=0  beginRecording() — camera starts, control preview source set
          (GStreamer starts initialising behind the countdown overlay)
  T=2  countdown reaches _MIRROR_REVEAL_AT — mirror preview revealed
          (mirror GStreamer has _MIRROR_REVEAL_AT seconds to warm up)
  T=5  countdown reaches 0 — recording officially starts; both pipelines
          have been running for 3–5 s and are now delivering clean frames
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from app.models.entities import PreparedRecording
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.recording_service import RecordingService

LOGGER = logging.getLogger(__name__)

# Total countdown seconds.  Camera starts at T=0 so it has the full
# countdown period to warm up.
_WARMUP_SECONDS = 5

# When the countdown reaches this value (counting down from _WARMUP_SECONDS),
# tell the mirror to show the live preview so its GStreamer pipeline also
# gets time to warm up before recording officially starts.
_MIRROR_REVEAL_AT = 3


class RecordingController(QObject):
    changed = Signal()
    _bg_stop_done = Signal()  # fired from background thread when stop + prepare completes

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
        self._warmup_mirror_url = ""   # mirror stream URL stored during warm-up
        self._error = ""
        self._backend_label = camera_service.current_backend_label()
        self._prepared: PreparedRecording | None = None

        # Background stop state — written by bg thread, read on main thread
        self._bg_result: PreparedRecording | None = None
        self._bg_error: str = ""
        self._bg_stop_done.connect(self._on_bg_stop_done)

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
        """Start the pre-recording countdown.

        The camera pipeline is started immediately so both GStreamer pipelines
        (control + mirror) have the full countdown period to warm up.  This
        eliminates pixelation/blocking artefacts at the start of recording.
        """
        if self._busy or self._recording or self._prepared:
            return
        self._clear_error()
        self._busy = True
        self._countdown = _WARMUP_SECONDS
        self._emit()

        # Start the camera NOW (recording to file) so the ffmpeg→GStreamer
        # UDP pipeline is already stable when the countdown ends.
        try:
            preview = self._camera.start_recording()
            self._preview_source = preview.control_preview_url
            self._warmup_mirror_url = preview.mirror_preview_url
            self._backend_label = preview.backend
        except Exception as exc:  # noqa: BLE001
            self._busy = False
            self._countdown = 0
            self._warmup_mirror_url = ""
            self._set_error(str(exc))
            self._app.showError(str(exc))
            self._emit()
            return

        self._emit()
        self._cd_timer.start()

    @Slot()
    def stopRecording(self) -> None:
        """Stop recording; the blocking camera-stop + ffmpeg remux runs in a
        background thread so the Qt event loop (and UI) stays responsive."""
        if not self._recording:
            return
        # Stop the elapsed timer here (main thread) before spawning the bg
        # thread, so _tick_elapsed can't fire while the camera is shutting down
        # and trigger a false "camera died" error.
        self._el_timer.stop()
        self._busy = True
        self._emit()

        def _bg() -> None:
            error = ""
            result = None
            try:
                capture = self._camera.stop(discard=False)
                if capture is None:
                    error = "Recording stopped but no file was produced."
                else:
                    result = self._recording_svc.prepare_review(
                        capture, trim_start=float(_WARMUP_SECONDS)
                    )
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
            self._bg_result = result
            self._bg_error = error
            self._bg_stop_done.emit()

        threading.Thread(target=_bg, daemon=True).start()

    @Slot()
    def _on_bg_stop_done(self) -> None:
        """Runs on the main thread after the background stop + prepare completes."""
        self._mirror.show_idle_black()
        self._recording = False
        self._preview_source = ""

        error = self._bg_error
        result = self._bg_result
        self._bg_result = None
        self._bg_error = ""

        if error:
            self._set_error(error)
            self._app.showError(error)
        else:
            self._prepared = result
            if result is not None:
                self._review_source = result.file_path.resolve().as_uri()
            self._app.showStatus("Recording complete — review and save or discard.")

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
        self._cd_timer.stop()
        self._el_timer.stop()
        # Stop the camera whether we are in warm-up or active-recording state.
        if self._camera.is_active():
            self._camera.stop(discard=True)
        self._mirror.show_idle_black()
        if self._prepared:
            self._recording_svc.discard_prepared(self._prepared)
        self._reset_state()
        self._app.showStatus("Recording discarded.")
        self._emit()

    # ------------------------------------------------------------------
    # Used by AppController to gate navigation
    # ------------------------------------------------------------------

    def navigation_locked(self) -> bool:
        return self._recording or self._prepared is not None or self._countdown > 0

    # ------------------------------------------------------------------
    # Timer callbacks
    # ------------------------------------------------------------------

    def _tick_countdown(self) -> None:
        # Detect camera crash during warm-up before countdown ends.
        if self._preview_source and not self._camera.is_alive():
            LOGGER.warning("Camera process died during countdown warm-up")
            self._cd_timer.stop()
            self._preview_source = ""
            self._warmup_mirror_url = ""
            self._mirror.show_idle_black()
            self._busy = False
            self._countdown = 0
            msg = (
                "Camera stopped during countdown. "
                "Check: 1) CSI cable is seated, 2) Camera enabled in raspi-config → "
                "Interface Options, 3) Reboot after enabling. "
                "Or switch to USB backend in Settings."
            )
            self._set_error(msg)
            self._app.showError(msg)
            self._emit()
            return

        if self._countdown <= 1:
            self._cd_timer.stop()
            self._countdown = 0
            self._emit()
            self._start_now()
        else:
            self._countdown -= 1
            # Reveal the mirror preview early so its GStreamer pipeline also
            # has time to warm up (_MIRROR_REVEAL_AT seconds remain).
            if self._countdown == _MIRROR_REVEAL_AT and self._warmup_mirror_url:
                self._mirror.show_live_preview(self._warmup_mirror_url)
            self._emit()

    def _start_now(self) -> None:
        # The camera was already started in beginRecording() for the warm-up.
        # All we need to do here is transition to the official recording state.
        self._recording = True
        self._busy = False
        self._elapsed = 0
        # _preview_source is already set; mirror is already showing live preview.
        self._el_timer.start()
        self._app.showStatus("Recording…")
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
                "Check: 1) CSI cable is seated, 2) Camera enabled in raspi-config → Interface Options, "
                "3) Reboot after enabling. Or switch to USB backend in Settings."
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
        self._warmup_mirror_url = ""
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
