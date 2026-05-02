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

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
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
        self._video_sink = QVideoSink(self)
        self._capture.setVideoSink(self._video_sink)
        self._camera: QCamera | None = None
        self._recorder: QMediaRecorder | None = None
        self._active = False
        self._recording_path: Path | None = None

    # ------------------------------------------------------------------
    # QML-readable
    # ------------------------------------------------------------------

    @Property(QVideoSink, notify=changed)
    def videoSink(self) -> QVideoSink:
        return self._video_sink

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
        """Stop recording (if any) and release the camera. Returns the file
        that was being recorded to, or None if preview-only.
        """
        recording_path = self._recording_path
        self._recording_path = None

        if self._recorder is not None:
            try:
                if self._recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState:
                    self._recorder.stop()
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("QMediaRecorder stop failed: %s", exc)
            self._capture.setRecorder(None)
            self._recorder.deleteLater()
            self._recorder = None

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

        return recording_path

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
