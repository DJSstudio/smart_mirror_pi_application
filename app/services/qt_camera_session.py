"""Qt native camera capture, with ffmpeg-pipe recording.

Architecture (the one proven by scripts/test_qcamera.py):
  Qt opens the USB camera via QCamera + QMediaCaptureSession.  Frames
  flow into a QVideoSink which the QML VideoOutput renders directly
  (smooth, real-time preview — verified on Pi 4 + IMX335 + Pi 5).

Recording avoids QMediaRecorder (broken pipeline assembly on Pi 4/5 + PySide6).
Instead, we subscribe to ``videoFrameChanged`` on the same QVideoSink the QML
VideoOutput is using, and pipe every frame's raw bytes into an ffmpeg
subprocess that encodes H.264 to the output file.

This sidesteps both broken paths we hit:
  - QMediaRecorder / GStreamer filesink failures
  - v4l2loopback / Qt enumeration not seeing /dev/video10
"""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QSize,
    QThread,
    QTimer,
    Property,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import (
    QCamera,
    QCameraFormat,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoFrame,
    QVideoFrameFormat,
    QVideoSink,
)

LOGGER = logging.getLogger(__name__)


class QtCameraSession(QObject):
    """Single shared capture session, lifetime-managed by main.py."""

    changed = Signal()
    # Off-main thread → main thread stop coordination
    _stopRequest = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._capture = QMediaCaptureSession(self)
        self._camera: QCamera | None = None
        self._active = False
        self._cached_devices: list = []

        # Two sinks: an internal one used while QML hasn't attached yet
        # (so recording can start immediately when the camera starts), and
        # the QML VideoOutput's sink once it attaches (for visible preview).
        # videoFrameChanged is connected to _on_video_frame on whichever
        # sink the captureSession is currently using.
        self._internal_sink = QVideoSink(self)
        self._internal_sink.videoFrameChanged.connect(self._on_video_frame)
        self._attached_sink: QVideoSink | None = None
        self._active_sink: QVideoSink = self._internal_sink

        # Recording state
        self._recording_path: Path | None = None
        self._recording_target_fps: int = 30
        self._actual_fps: float = 30.0   # set when QCamera negotiates a format
        self._ffmpeg: subprocess.Popen | None = None
        self._first_frame_seen: bool = False
        self._frame_count: int = 0

        # Cross-thread stop coordination
        self._stop_done = threading.Event()
        self._stop_result: Path | None = None
        self._stopRequest.connect(self._handle_stop_request, Qt.ConnectionType.QueuedConnection)

    # ------------------------------------------------------------------
    # Setup helpers — called from main.py at startup
    # ------------------------------------------------------------------

    def prime_devices(self) -> int:
        """Enumerate cameras at startup and cache the result.  Run AFTER
        QGuiApplication exists.  Returns the number of cameras found.
        """
        self._cached_devices = list(QMediaDevices.videoInputs())
        for dev in self._cached_devices:
            try:
                dev_id = dev.id().data().decode(errors="replace")
            except Exception:  # noqa: BLE001
                dev_id = str(dev.id())
            LOGGER.info("Primed camera: id=%s description=%s",
                        dev_id, dev.description())
        return len(self._cached_devices)

    # ------------------------------------------------------------------
    # QML wiring — VideoOutput passes its videoSink to us
    # ------------------------------------------------------------------

    @Slot(QVideoSink)
    def attachSink(self, sink: QVideoSink) -> None:
        """QML's VideoOutput.Component.onCompleted calls this with its own
        videoSink.  We swap the capture session from the internal sink to
        the QML sink so QML can render the preview, while continuing to
        receive frames for recording via the swapped-in sink's signal.
        """
        if sink is None:
            self.detachSink()
            return
        # Disconnect frame handler from currently-active sink
        try:
            self._active_sink.videoFrameChanged.disconnect(self._on_video_frame)
        except (TypeError, RuntimeError):
            pass
        # Connect to QML's sink and route capture there
        sink.videoFrameChanged.connect(self._on_video_frame)
        self._capture.setVideoSink(sink)
        self._attached_sink = sink
        self._active_sink = sink
        LOGGER.info("QCamera: attached video sink from QML")

    @Slot()
    def detachSink(self) -> None:
        """QML's VideoOutput.Component.onDestruction calls this when the
        live_preview component unloads.  Revert to the internal sink so
        recording continues uninterrupted (e.g. user navigates away mid-
        recording) until stop() is called.
        """
        if self._attached_sink is None:
            return
        try:
            self._attached_sink.videoFrameChanged.disconnect(self._on_video_frame)
        except (TypeError, RuntimeError):
            pass
        self._attached_sink = None
        self._capture.setVideoSink(self._internal_sink)
        self._internal_sink.videoFrameChanged.connect(self._on_video_frame)
        self._active_sink = self._internal_sink

    @Property(bool, notify=changed)
    def active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Camera lifecycle
    # ------------------------------------------------------------------

    def start_preview(self, device_hint: str | None,
                      width: int, height: int, fps: int) -> None:
        """Open the camera and stream frames into the active sink.  No recording.

        Uses the internal QVideoSink by default so frames are received
        immediately (and recording can begin right away).  When QML later
        calls attachSink(), the active sink is swapped to QML's VideoOutput
        sink for visible preview without interrupting frame flow.
        """
        self.stop()  # clean state

        device = self._pick_device(device_hint)
        if device is None:
            raise RuntimeError("No video input device found by QMediaDevices")

        LOGGER.info("QCamera: opening %s (target %dx%d@%dfps)",
                    device.description(), width, height, fps)

        self._camera = QCamera(device, self)
        self._actual_fps = self._apply_best_format(self._camera, device, width, height, fps)
        self._capture.setCamera(self._camera)
        # Default to internal sink — frames start flowing immediately
        self._capture.setVideoSink(self._internal_sink)
        self._active_sink = self._internal_sink
        self._camera.start()
        self._active = True
        self.changed.emit()

    def start_recording(self, device_hint: str | None,
                        width: int, height: int, fps: int,
                        bitrate: int, output_path: Path) -> Path:
        """Open the camera AND begin piping frames to an ffmpeg subprocess
        that encodes H.264 to ``output_path``.  ffmpeg is spawned lazily on
        the first frame received (so we know the actual pixel format).
        """
        self.start_preview(device_hint, width, height, fps)
        self._recording_path = output_path
        self._recording_target_fps = fps
        self._first_frame_seen = False
        self._frame_count = 0
        # ffmpeg subprocess is started in _on_video_frame on first frame
        LOGGER.info("Recording will start to %s (ffmpeg spawned on first frame)",
                    output_path)
        return output_path

    # ------------------------------------------------------------------
    # Frame handler — runs on Qt main thread (signal from QVideoSink)
    # ------------------------------------------------------------------

    @Slot(QVideoFrame)
    def _on_video_frame(self, frame: QVideoFrame) -> None:
        if self._recording_path is None:
            return  # not recording — frames flow only to the QML sink for preview
        if not frame.isValid():
            return

        # Lazy-spawn ffmpeg now that we know the actual frame format
        if self._ffmpeg is None:
            try:
                self._spawn_ffmpeg(frame)
            except Exception as exc:  # noqa: BLE001
                LOGGER.error("Failed to spawn ffmpeg: %s", exc)
                self._recording_path = None  # disable recording
                return

        # Map frame, copy bytes, write to ffmpeg
        if not frame.map(QVideoFrame.MapMode.ReadOnly):
            return
        try:
            stdin = self._ffmpeg.stdin if self._ffmpeg else None
            if stdin is None:
                return
            try:
                # Single-plane formats (YUYV, JPEG, RGB32): plane 0 is everything
                # Multi-plane formats (NV12, YUV420P): write planes in order
                planes = frame.planeCount()
                for p in range(planes):
                    bits = frame.bits(p)
                    if bits is None:
                        continue
                    nbytes = frame.mappedBytes(p)
                    # bits is a memoryview-like; slice to actual mapped size
                    stdin.write(bytes(bits[:nbytes]))
                self._frame_count += 1
            except (BrokenPipeError, OSError) as exc:
                LOGGER.warning("ffmpeg pipe closed: %s (after %d frames)",
                               exc, self._frame_count)
                # ffmpeg crashed — disable recording but don't crash app
                self._recording_path = None
        finally:
            frame.unmap()

    def _spawn_ffmpeg(self, frame: QVideoFrame) -> None:
        """Build an ffmpeg command tailored to the actual frame format and
        start it.  Called once on first frame received during recording.

        The framerate passed to ffmpeg is the *actual* fps the camera is
        delivering (negotiated by _apply_best_format), NOT the requested
        fps from settings.  Mismatching causes the file's duration metadata
        to be wrong (e.g., declaring 60fps when actual is 10fps stamps the
        file as 6× shorter than it really is, breaking trim_mp4 downstream).
        """
        fmt = frame.pixelFormat()
        w = frame.width()
        h = frame.height()
        # Use the actual negotiated fps so file metadata matches frame timing.
        # Round to nearest integer because ffmpeg -framerate prefers integers
        # for stable timestamping; non-integer fps values like 29.97 work
        # but integer is safer.
        fps = max(1, int(round(self._actual_fps)))
        out_path = self._recording_path

        cmd: list[str]
        if fmt == QVideoFrameFormat.PixelFormat.Format_Jpeg:
            # Camera is producing MJPEG frames — feed them directly to
            # ffmpeg's mjpeg demuxer.  Tiny pipe bandwidth (compressed).
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-f", "image2pipe", "-vcodec", "mjpeg",
                "-framerate", str(fps),
                "-i", "pipe:0",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", str(out_path),
            ]
            LOGGER.info("Recorder: MJPEG passthrough → libx264, %dx%d @ %dfps (actual)",
                        w, h, fps)
        else:
            # Raw frames — map Qt's pixel format name to an ffmpeg pixel format
            ff_pix = _qt_pix_to_ffmpeg(fmt)
            if ff_pix is None:
                raise RuntimeError(
                    f"Unsupported QVideoFrame pixel format for recording: {fmt.name}"
                )
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-f", "rawvideo",
                "-pixel_format", ff_pix,
                "-video_size", f"{w}x{h}",
                "-framerate", str(fps),
                "-i", "pipe:0",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", str(out_path),
            ]
            LOGGER.info("Recorder: raw %s → libx264, %dx%d @ %dfps (actual)",
                        ff_pix, w, h, fps)

        self._ffmpeg = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0,  # unbuffered — write each frame immediately
        )
        # Drain ffmpeg stderr to logger
        threading.Thread(
            target=_drain_pipe,
            args=(self._ffmpeg.stderr, LOGGER, "ffmpeg"),
            daemon=True,
        ).start()
        self._first_frame_seen = True
        LOGGER.info("Recorder ffmpeg started (pid=%d)", self._ffmpeg.pid)

    # ------------------------------------------------------------------
    # Stop — thread-safe (recording_controller calls from bg thread)
    # ------------------------------------------------------------------

    def stop(self) -> Path | None:
        if QThread.currentThread() is self.thread():
            return self._stop_on_main_thread()
        # Off-main thread → marshal via queued signal
        self._stop_done.clear()
        self._stop_result = None
        self._stopRequest.emit()
        if not self._stop_done.wait(timeout=15):
            LOGGER.warning("QtCameraSession.stop() timed out waiting for main thread")
        return self._stop_result

    @Slot()
    def _handle_stop_request(self) -> None:
        try:
            self._stop_result = self._stop_on_main_thread()
        finally:
            self._stop_done.set()

    def _stop_on_main_thread(self) -> Path | None:
        recorded_path = self._recording_path
        self._recording_path = None  # signal frame handler to stop writing

        # Close ffmpeg cleanly so the MP4 trailer is written
        if self._ffmpeg is not None:
            ffm = self._ffmpeg
            self._ffmpeg = None
            try:
                if ffm.stdin and not ffm.stdin.closed:
                    try:
                        ffm.stdin.close()  # EOF → ffmpeg flushes and exits
                    except Exception:  # noqa: BLE001
                        pass
                ffm.wait(timeout=10)
            except subprocess.TimeoutExpired:
                LOGGER.warning("ffmpeg didn't exit cleanly, killing")
                ffm.kill()
                try:
                    ffm.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            LOGGER.info("Recorder ffmpeg exited (frames written: %d)",
                        self._frame_count)
        self._frame_count = 0
        self._first_frame_seen = False

        # Stop QCamera
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

        if recorded_path is not None and recorded_path.exists() and recorded_path.stat().st_size > 0:
            return recorded_path
        return None

    @Slot(result=bool)
    def is_alive(self) -> bool:
        if not self._active or self._camera is None:
            return False
        return self._camera.isActive()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_device(self, hint: str | None):
        """Find a camera matching the hint, preferring the cache populated
        at startup (before anything could lock devices)."""
        cameras = list(self._cached_devices) or list(QMediaDevices.videoInputs())
        if not cameras:
            return None
        if hint:
            hint_b = hint.encode() if isinstance(hint, str) else hint
            for dev in cameras:
                if dev.id() == hint_b or hint in dev.description():
                    return dev
            LOGGER.warning("Camera hint %r not matched — falling back to first device", hint)
        return cameras[0]

    @staticmethod
    def _apply_best_format(camera: QCamera, device, width: int, height: int, fps: int) -> float:
        """Pick the best camera format: matching resolution → MJPEG preferred
        → highest fps ≤ requested.  Returns the actual fps the camera will
        deliver (which may be lower than requested).
        """
        formats = device.videoFormats()
        if not formats:
            LOGGER.warning("Camera %s reports no formats", device.description())
            return float(fps)

        for fmt in formats:
            LOGGER.info("  available: %dx%d  fps=%.1f-%.1f  pixel=%s",
                        fmt.resolution().width(), fmt.resolution().height(),
                        fmt.minFrameRate(), fmt.maxFrameRate(),
                        fmt.pixelFormat().name)

        target = QSize(width, height)
        target_pixels = width * height
        matching = [f for f in formats if f.resolution() == target]
        candidates = matching if matching else formats

        def is_mjpeg(fmt: QCameraFormat) -> bool:
            name = fmt.pixelFormat().name.lower()
            return "jpeg" in name

        def score(fmt: QCameraFormat) -> tuple:
            res = fmt.resolution()
            res_diff = 0 if res == target else abs(res.width() * res.height() - target_pixels)
            mjpeg_pref = 0 if is_mjpeg(fmt) else 1
            fmax = fmt.maxFrameRate()
            fps_score = -fmax if fmax <= fps else fmax
            return (res_diff, mjpeg_pref, fps_score)

        best = min(candidates, key=score)
        camera.setCameraFormat(best)
        actual_fps = best.maxFrameRate()
        LOGGER.info("QCamera selected: %dx%d @ %.0ffps  pixel=%s  (requested %dx%d @ %dfps)",
                    best.resolution().width(), best.resolution().height(),
                    actual_fps, best.pixelFormat().name,
                    width, height, fps)
        return float(actual_fps)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _qt_pix_to_ffmpeg(fmt) -> str | None:
    """Map common QVideoFrameFormat.PixelFormat values to ffmpeg pixel
    format strings used with -f rawvideo -pixel_format ..."""
    pf = QVideoFrameFormat.PixelFormat
    table = {
        pf.Format_YUYV:    "yuyv422",
        pf.Format_UYVY:    "uyvy422",
        pf.Format_NV12:    "nv12",
        pf.Format_NV21:    "nv21",
        pf.Format_YUV420P: "yuv420p",
        pf.Format_YV12:    "yuv420p",   # YV12 is YUV420P with U/V swapped; close enough for libx264
        pf.Format_BGRA8888: "bgra",
        pf.Format_BGRX8888: "bgra",
        pf.Format_ARGB8888: "argb",
        pf.Format_XRGB8888: "argb",
        pf.Format_RGBA8888: "rgba",
        pf.Format_RGBX8888: "rgba",
    }
    return table.get(fmt)


def _drain_pipe(pipe, logger, label: str) -> None:
    """Forward subprocess stderr lines to the logger so we see ffmpeg errors."""
    try:
        for raw in pipe:
            line = raw.decode(errors="replace").rstrip() if isinstance(raw, bytes) else raw.rstrip()
            if not line:
                continue
            lower = line.lower()
            if "error" in lower or "fail" in lower or "fatal" in lower:
                logger.warning("[%s] %s", label, line)
            else:
                logger.info("[%s] %s", label, line)
    except Exception:  # noqa: BLE001
        pass
