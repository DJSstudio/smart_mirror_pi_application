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
    QThread,
    QTimer,
    Property,
    Signal,
    Slot,
    QUrl,
)
from PySide6.QtMultimedia import (
    QCamera,
    QCameraFormat,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
    QVideoSink,
)

LOGGER = logging.getLogger(__name__)


class QtCameraSession(QObject):
    """Single shared capture session, lifetime-managed by main.py."""

    changed = Signal()

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

        Returns the path that the recording will be written to (Qt may add a
        container extension; we use the path as-is).
        """
        self.start_preview(device_hint, width, height, fps)

        self._recorder = QMediaRecorder(self)
        self._capture.setRecorder(self._recorder)

        fmt = QMediaFormat()
        fmt.setFileFormat(QMediaFormat.FileFormat.MPEG4)
        fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
        self._recorder.setMediaFormat(fmt)
        self._recorder.setQuality(QMediaRecorder.Quality.HighQuality)
        self._recorder.setVideoBitRate(bitrate)
        self._recorder.setOutputLocation(QUrl.fromLocalFile(str(output_path)))

        self._recording_path = output_path
        self._recorder.record()
        LOGGER.info("QMediaRecorder: recording to %s", output_path)
        return output_path

    def stop(self) -> Path | None:
        """Stop recording and release the camera. Thread-safe.

        recording_controller calls this from a background thread.  Qt media
        objects (QMediaRecorder, QCamera, QEventLoop) only work on their
        owning thread (the main thread here), so when we're called off-main
        we marshal the work via QTimer.singleShot(0, ...) and block on a
        threading.Event for the result.
        """
        if QThread.currentThread() is self.thread():
            return self._stop_on_main_thread()

        # Off main thread — schedule the real work and wait
        done = threading.Event()
        result_box: list[Path | None] = [None]

        def _runner() -> None:
            try:
                result_box[0] = self._stop_on_main_thread()
            finally:
                done.set()

        QTimer.singleShot(0, _runner)
        if not done.wait(timeout=15):
            LOGGER.warning("QtCameraSession.stop() timed out waiting for main thread")
        return result_box[0]

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
        """Pick the camera format closest to the requested resolution+fps."""
        formats = device.videoFormats()
        if not formats:
            return

        target_pixels = width * height

        def score(fmt: QCameraFormat) -> tuple[int, int]:
            res = fmt.resolution()
            pixel_diff = abs(res.width() * res.height() - target_pixels)
            fps_diff = abs(fmt.maxFrameRate() - fps)
            return (pixel_diff, int(fps_diff * 100))

        best = min(formats, key=score)
        camera.setCameraFormat(best)
        LOGGER.info(
            "QCamera format: %dx%d @ %.0ffps (requested %dx%d @ %dfps)",
            best.resolution().width(), best.resolution().height(),
            best.maxFrameRate(), width, height, fps,
        )
