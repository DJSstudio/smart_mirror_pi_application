"""QObject wrapping Qt's native camera capture pipeline.

This is the low-latency replacement for the ffmpeg-based USB camera path:
camera frames go directly from the sensor to the mirror's VideoOutput via
QMediaCaptureSession, with no H.264 encode-decode round-trip.  Recording
runs in parallel via QMediaRecorder using the same camera source.

Exposed to QML as `qtCamera` so MirrorWindow's live_preview component
can bind a VideoOutput to `qtCamera.videoSink`.
"""
from __future__ import annotations

import logging
from pathlib import Path

import threading

from PySide6.QtCore import (
    QEventLoop,
    QObject,
    QSize,
    QThread,
    QTimer,
    Property,
    Qt,
    Signal,
    Slot,
    QUrl,
)
from PySide6.QtMultimedia import (
    QCamera,
    QCameraFormat,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaRecorder,
    QVideoSink,
)

LOGGER = logging.getLogger(__name__)


class QtCameraSession(QObject):
    """Single shared capture session, lifetime-managed by main.py."""

    changed = Signal()
    # Internal: bg threads emit this to ask the main thread to run stop().
    # QueuedConnection guarantees delivery on the receiver's thread.
    _stopRequest = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._capture = QMediaCaptureSession(self)
        self._camera: QCamera | None = None
        self._recorder: QMediaRecorder | None = None
        self._active = False
        self._recording_path: Path | None = None
        # The QML VideoOutput passes us its native QVideoSink via attachSink().
        # We hold a reference so it survives across mode changes.
        self._attached_sink: QVideoSink | None = None
        # Cross-thread stop coordination
        self._stop_done = threading.Event()
        self._stop_result: Path | None = None
        self._stopRequest.connect(self._handle_stop_request, Qt.ConnectionType.QueuedConnection)

    # ------------------------------------------------------------------
    # QML-callable wiring
    # ------------------------------------------------------------------

    @Slot(QVideoSink)
    def attachSink(self, sink: QVideoSink) -> None:
        """QML calls this from a VideoOutput's Component.onCompleted to wire
        its native videoSink as the destination for camera frames.  The
        VideoOutput owns its sink — we just tell the capture session where
        to push frames.
        """
        self._attached_sink = sink
        if sink is not None:
            self._capture.setVideoSink(sink)
            LOGGER.info("QCamera: attached video sink from QML")
        else:
            self._capture.setVideoSink(None)

    @Slot()
    def detachSink(self) -> None:
        self._attached_sink = None
        self._capture.setVideoSink(None)

    @Property(bool, notify=changed)
    def active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Internal lifecycle (called from QtCameraAdapter, runs on Qt main thread)
    # ------------------------------------------------------------------

    def start_preview(self, device_hint: str | None, width: int, height: int, fps: int) -> None:
        """Open the camera and begin streaming to the videoSink. No recording."""
        self.stop()  # ensure clean state

        device = self._pick_device(device_hint)
        if device is None:
            raise RuntimeError("No video input device found by QMediaDevices")

        LOGGER.info(
            "QCamera: opening %s (target %dx%d@%dfps)",
            device.description(), width, height, fps,
        )

        self._camera = QCamera(device, self)
        self._apply_best_format(self._camera, device, width, height, fps)
        self._capture.setCamera(self._camera)
        self._camera.start()
        self._active = True
        self.changed.emit()

    def start_recording(
        self,
        device_hint: str | None,
        width: int, height: int, fps: int,
        bitrate: int,
        output_path: Path,
    ) -> Path:
        """Open the camera, attach a recorder, begin both preview and recording.

        Recorder is configured minimally: only output location and quality.
        Earlier explicit MPEG4 + H264 + bitrate triggered GStreamer pipeline
        assembly failures (filesink ASYNC READY PLAYING, videoConvert
        getPipeline failed) on the Pi 5 + IMX335 + PySide6 combination.
        Letting Qt pick defaults that match the camera's source format is
        more reliable.
        """
        self.start_preview(device_hint, width, height, fps)

        self._recorder = QMediaRecorder(self)
        self._capture.setRecorder(self._recorder)
        self._recorder.setQuality(QMediaRecorder.Quality.HighQuality)
        self._recorder.setOutputLocation(QUrl.fromLocalFile(str(output_path)))

        # Hook recorder error signal so we surface failures instead of
        # silently producing zero-byte files.
        self._recorder.errorOccurred.connect(self._on_recorder_error)

        self._recording_path = output_path
        self._recorder.record()
        LOGGER.info(
            "QMediaRecorder: recording to %s (state=%s)",
            output_path, self._recorder.recorderState().name,
        )
        return output_path

    @Slot(QMediaRecorder.Error, str)
    def _on_recorder_error(self, error, error_string: str) -> None:
        LOGGER.error("QMediaRecorder error: %s — %s", error.name, error_string)

    def stop(self) -> Path | None:
        """Stop recording and release the camera. Thread-safe.

        recording_controller calls this from a background thread.  Qt media
        objects only work on their owning thread, so off-main calls fire a
        queued signal that the main thread receives and acts on, while the
        bg thread blocks on a threading.Event for the result.
        """
        if QThread.currentThread() is self.thread():
            return self._stop_on_main_thread()

        # Off-main thread path — emit queued signal, wait for completion
        self._stop_done.clear()
        self._stop_result = None
        self._stopRequest.emit()
        if not self._stop_done.wait(timeout=15):
            LOGGER.warning("QtCameraSession.stop() timed out waiting for main thread")
        return self._stop_result

    @Slot()
    def _handle_stop_request(self) -> None:
        """Slot invoked on the main thread by the queued _stopRequest signal."""
        try:
            self._stop_result = self._stop_on_main_thread()
        finally:
            self._stop_done.set()

    def _stop_on_main_thread(self) -> Path | None:
        """Actual stop logic — must run on the main thread."""
        actual_path: Path | None = None

        if self._recorder is not None:
            recorder = self._recorder
            try:
                if recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState:
                    loop = QEventLoop()

                    def _on_state_changed(state):
                        if state == QMediaRecorder.RecorderState.StoppedState:
                            loop.quit()

                    recorder.recorderStateChanged.connect(_on_state_changed)
                    recorder.stop()
                    # Safety timeout — don't hang forever if signal never fires
                    QTimer.singleShot(5000, loop.quit)
                    loop.exec()
                    recorder.recorderStateChanged.disconnect(_on_state_changed)

                # Use actualLocation: Qt may have changed/normalized the path
                actual_url = recorder.actualLocation()
                if not actual_url.isEmpty():
                    local = actual_url.toLocalFile()
                    if local:
                        actual_path = Path(local)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("QMediaRecorder stop failed: %s", exc)

            # Fall back to the path we requested if actualLocation was empty
            if actual_path is None:
                actual_path = self._recording_path

            self._capture.setRecorder(None)
            recorder.deleteLater()
            self._recorder = None

        self._recording_path = None

        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("QCamera stop failed: %s", exc)
            self._capture.setCamera(None)
            self._camera.deleteLater()
            self._camera = None

        if self._active:
            self._active = False
            self.changed.emit()

        return actual_path

    @Slot(result=bool)
    def is_alive(self) -> bool:
        if not self._active or self._camera is None:
            return False
        return self._camera.isActive()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_device(hint: str | None):
        cameras = QMediaDevices.videoInputs()
        if not cameras:
            return None
        if hint:
            hint_b = hint.encode() if isinstance(hint, str) else hint
            for dev in cameras:
                if dev.id() == hint_b or hint in dev.description():
                    return dev
        return cameras[0]

    @staticmethod
    def _apply_best_format(camera: QCamera, device, width: int, height: int, fps: int) -> None:
        """Pick the best camera format for the requested resolution + fps.

        Strategy:
          1. Filter to formats matching the requested resolution exactly.
             If none match, fall back to the closest by pixel count.
          2. Among matching, prefer MJPEG (less USB bandwidth, hardware
             JPEG decode on Pi) over YUYV/YUV.
          3. Among ties, pick the format with the highest maxFrameRate
             that is <= the requested fps; if all are <= fps, just pick
             the highest available.

        This avoids the bug where Qt's first-listed format at a resolution
        is a low-fps mode and gets selected by accident.
        """
        formats = device.videoFormats()
        if not formats:
            LOGGER.warning("Camera %s reports no formats", device.description())
            return

        # Diagnostic: log every available format so we can debug selection
        for fmt in formats:
            LOGGER.info(
                "  available: %dx%d  fps=%.1f-%.1f  pixel=%s",
                fmt.resolution().width(), fmt.resolution().height(),
                fmt.minFrameRate(), fmt.maxFrameRate(),
                fmt.pixelFormat().name,
            )

        target = QSize(width, height)
        target_pixels = width * height
        matching = [f for f in formats if f.resolution() == target]
        candidates = matching if matching else formats

        def is_mjpeg(fmt: QCameraFormat) -> bool:
            name = fmt.pixelFormat().name.lower()
            return "jpeg" in name or "mjpeg" in name

        def score(fmt: QCameraFormat) -> tuple:
            res = fmt.resolution()
            res_diff = 0 if res == target else abs(res.width() * res.height() - target_pixels)
            mjpeg_pref = 0 if is_mjpeg(fmt) else 1
            # Prefer the highest fps that is <= requested.  If all formats
            # exceed requested, pick the lowest above (for compatibility).
            fmax = fmt.maxFrameRate()
            if fmax <= fps:
                fps_score = -fmax  # higher fmax wins (more negative sorts first)
            else:
                fps_score = fmax  # smaller exceedance wins
            return (res_diff, mjpeg_pref, fps_score)

        best = min(candidates, key=score)
        camera.setCameraFormat(best)
        LOGGER.info(
            "QCamera selected: %dx%d @ %.0ffps  pixel=%s  (requested %dx%d @ %dfps)",
            best.resolution().width(), best.resolution().height(),
            best.maxFrameRate(), best.pixelFormat().name,
            width, height, fps,
        )
