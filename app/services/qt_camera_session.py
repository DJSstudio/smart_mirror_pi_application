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
import queue
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import (
    QObject,
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
        # videoFrameChanged is connected to _on_video_frame ONLY while
        # recording is active — preview-only mode skips the per-frame
        # Python callback entirely (eliminates 30 GIL acquisitions/sec
        # for the preview-only common case).
        self._internal_sink = QVideoSink(self)
        self._attached_sink: QVideoSink | None = None
        self._active_sink: QVideoSink = self._internal_sink
        self._frame_handler_connected: bool = False

        # Recording settings
        self._mirror_flip: bool = False
        self._mirror_orientation_degrees: int = 0
        self._recording_path: Path | None = None
        self._recording_target_fps: int = 30
        self._actual_fps: float = 30.0   # camera-advertised max
        self._ffmpeg: subprocess.Popen | None = None
        self._first_frame_seen: bool = False
        self._frame_count: int = 0
        # Wall-clock timestamps so we can fix up the file's timing if the
        # camera delivers fewer frames per second than its declared max.
        self._recording_start_wallclock: float = 0.0
        self._last_frame_wallclock: float = 0.0

        # M1: dedicated writer thread keeps ffmpeg pipe writes off the GUI thread
        self._write_queue: queue.Queue = queue.Queue(maxsize=8)
        self._writer_thread: threading.Thread | None = None

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

    def _connect_frame_handler(self) -> None:
        """Subscribe _on_video_frame to the active sink's videoFrameChanged.
        Called only when recording starts so preview-only mode pays no
        per-frame Python callback cost."""
        if self._frame_handler_connected:
            return
        try:
            self._active_sink.videoFrameChanged.connect(self._on_video_frame)
            self._frame_handler_connected = True
        except (TypeError, RuntimeError) as exc:
            LOGGER.warning("Failed to connect frame handler: %s", exc)

    def _disconnect_frame_handler(self) -> None:
        """Disconnect from whichever sink we're currently subscribed on."""
        if not self._frame_handler_connected:
            return
        try:
            self._active_sink.videoFrameChanged.disconnect(self._on_video_frame)
        except (TypeError, RuntimeError):
            pass
        self._frame_handler_connected = False

    @Slot(QVideoSink)
    def attachSink(self, sink: QVideoSink) -> None:
        """QML's VideoOutput.Component.onCompleted calls this with its own
        videoSink.  We swap the capture session from the internal sink to
        the QML sink so QML can render the preview.  If recording is
        active, the frame handler is re-subscribed to the new sink so
        ffmpeg-pipe writes continue uninterrupted.
        """
        if sink is None:
            self.detachSink()
            return
        was_recording = self._frame_handler_connected
        self._disconnect_frame_handler()
        self._capture.setVideoSink(sink)
        self._attached_sink = sink
        self._active_sink = sink
        if was_recording:
            self._connect_frame_handler()
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
        was_recording = self._frame_handler_connected
        self._disconnect_frame_handler()
        self._attached_sink = None
        self._capture.setVideoSink(self._internal_sink)
        self._active_sink = self._internal_sink
        if was_recording:
            self._connect_frame_handler()

    @Property(bool, notify=changed)
    def active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Camera lifecycle
    # ------------------------------------------------------------------

    def start_preview(self, device_hint: str | None,
                      width: int, height: int, fps: int,
                      mirror_flip: bool = False,
                      mirror_orientation_degrees: int = 0) -> None:
        """Open the camera and stream frames into the active sink.  No recording.

        Mirrors scripts/test_qcamera.py exactly: pick the device, hand it
        to QCamera, attach to capture session, start.  No setCameraFormat
        call — that lets the camera use its preferred (default) format,
        which is typically the highest-quality MJPEG mode.  Forcing a
        specific resolution/fps via settings sometimes ended up picking
        a worse format (e.g., 720p YUYV @ 10fps when 1080p MJPEG @ 30fps
        was available as default).

        The width/height/fps args are kept in the signature for API
        compatibility but are now used only as diagnostic logging hints
        and as the recording-rate fallback.

        Uses the internal QVideoSink by default so frames are received
        immediately (and recording can begin right away).  When QML later
        calls attachSink(), the active sink is swapped to QML's VideoOutput
        sink for visible preview without interrupting frame flow.
        """
        self.stop()  # clean state

        device = self._pick_device(device_hint)
        if device is None:
            raise RuntimeError("No video input device found by QMediaDevices")

        LOGGER.info("QCamera: opening %s (settings hint %dx%d@%dfps; using camera default)",
                    device.description(), width, height, fps)

        # Diagnostic only: log the formats the camera offers so we can see
        # which one Qt picks as default.
        for fmt in device.videoFormats():
            LOGGER.info("  available: %dx%d  fps=%.1f-%.1f  pixel=%s",
                        fmt.resolution().width(), fmt.resolution().height(),
                        fmt.minFrameRate(), fmt.maxFrameRate(),
                        fmt.pixelFormat().name)

        self._mirror_flip = mirror_flip
        self._mirror_orientation_degrees = mirror_orientation_degrees
        self._camera = QCamera(device, self)
        # Pick the best format: MJPEG strongly preferred (Pi can decode it
        # cheaply, raw YUYV is bandwidth/CPU-heavy), then closest resolution
        # to the user's settings, then highest fps.  This avoids Qt's
        # default which often picks the camera's full-sensor mode (e.g.
        # 1920x1080 MJPEG @ 30fps) — fine on Pi 5, too heavy for Pi 4 to
        # JPEG-decode + render to a 4K mirror in real-time.
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
                        bitrate: int, output_path: Path,
                        mirror_flip: bool = False,
                        mirror_orientation_degrees: int = 0) -> Path:
        """Open the camera AND begin piping frames to an ffmpeg subprocess
        that encodes H.264 to ``output_path``.  ffmpeg is spawned lazily on
        the first frame received (so we know the actual pixel format).
        """
        self.start_preview(device_hint, width, height, fps,
                          mirror_flip=mirror_flip,
                          mirror_orientation_degrees=mirror_orientation_degrees)
        self._recording_path = output_path
        self._recording_target_fps = fps
        self._first_frame_seen = False
        self._frame_count = 0
        # Connect the frame handler now that we want recording.  Preview-
        # only mode never has this connected → no per-frame Python callback.
        self._connect_frame_handler()
        LOGGER.info("Recording will start to %s (ffmpeg spawned on first frame)",
                    output_path)
        return output_path

    def begin_recording(self, output_path: Path) -> Path:
        """Begin recording on an ALREADY-RUNNING camera session.

        Used by Live Compare's Record button: the camera is already
        producing frames for preview, we just want to start writing them
        to a file.  ffmpeg is spawned lazily on the next frame received.
        """
        if not self._active:
            raise RuntimeError("Camera not running — start_preview first")
        self._recording_path = output_path
        self._frame_count = 0
        self._first_frame_seen = False
        # Connect the frame handler so frames start flowing to ffmpeg
        self._connect_frame_handler()
        LOGGER.info("Recording started on existing camera session → %s", output_path)
        return output_path

    def end_recording(self) -> Path | None:
        """Stop recording but keep the camera running.

        Used by Live Compare's Stop button.  Returns the path to the file
        that was being written, or None if nothing was recorded.
        """
        recorded = self._recording_path
        self._recording_path = None
        # Stop the per-frame Python callback to free up CPU for live preview
        self._disconnect_frame_handler()

        # Drain the writer thread before closing the pipe
        if self._writer_thread is not None:
            self._write_queue.put(None)  # sentinel
            self._writer_thread.join(timeout=5)
            self._writer_thread = None

        if self._ffmpeg is not None:
            ffm = self._ffmpeg
            self._ffmpeg = None
            try:
                if ffm.stdin and not ffm.stdin.closed:
                    try:
                        ffm.stdin.close()
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
            LOGGER.info("Live Compare recording ffmpeg exited (frames written: %d)",
                        self._frame_count)
        self._frame_count = 0
        if recorded is not None and recorded.exists() and recorded.stat().st_size > 0:
            return recorded
        return None

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

        # Copy frame bytes on main thread — QVideoFrame map/unmap must happen here.
        # Single-plane formats (YUYV, JPEG): plane 0 is the whole frame.
        # Multi-plane formats (NV12, YUV420P): write planes in order.
        if not frame.map(QVideoFrame.MapMode.ReadOnly):
            return
        try:
            planes = frame.planeCount()
            chunks: list[bytes] = []
            for p in range(planes):
                bits = frame.bits(p)
                if bits is None:
                    continue
                nbytes = frame.mappedBytes(p)
                chunks.append(bytes(bits[:nbytes]))
        finally:
            frame.unmap()

        if not chunks:
            return

        # Enqueue for the writer thread — non-blocking: drop the frame if the
        # queue is full (ffmpeg behind) rather than blocking the GUI thread.
        try:
            self._write_queue.put_nowait(chunks)
            self._last_frame_wallclock = time.monotonic()
        except queue.Full:
            LOGGER.debug("Frame dropped: ffmpeg writer thread is behind")

    def _spawn_ffmpeg(self, frame: QVideoFrame) -> None:
        """Build an ffmpeg command tailored to the actual frame format and
        start it.  Called once on first frame received during recording.

        Timing strategy: -use_wallclock_as_timestamps 1 makes ffmpeg stamp
        each input frame with the wall-clock time it was READ from stdin.
        This way the output file's timing matches the camera's ACTUAL
        delivery rate (which is usually lower than its advertised max due
        to lighting / USB / CPU jitter) without us having to know or
        hardcode the fps in advance.  The -framerate hint is still given
        as a fallback / probe value but timestamps come from wallclock.
        """
        fmt = frame.pixelFormat()
        w = frame.width()
        h = frame.height()
        # -framerate is still required for raw demuxers as a probe; wallclock
        # timestamps override it for actual frame timing.
        fps_hint = max(1, int(round(self._actual_fps)))
        out_path = self._recording_path

        cmd: list[str]
        if self._mirror_flip:
            # 90°/270° rotations swap the viewer's perceived axes: what looks
            # like left↔right to the viewer is actually top↔bottom in the raw
            # image, so use vflip.  0°/180° keep the axes aligned → hflip.
            flip_filter = "vflip" if self._mirror_orientation_degrees in (90, 270) else "hflip"
            vf = ["-vf", flip_filter]
        else:
            vf = []

        if fmt == QVideoFrameFormat.PixelFormat.Format_Jpeg:
            # MJPEG passthrough — tiny pipe bandwidth (compressed).
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-use_wallclock_as_timestamps", "1",
                "-fflags", "+genpts",
                "-f", "image2pipe", "-vcodec", "mjpeg",
                "-framerate", str(fps_hint),
                "-i", "pipe:0",
                "-vsync", "vfr",
                *vf,
                "-c:v", "libx264", "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", str(out_path),
            ]
            LOGGER.info("Recorder: MJPEG → libx264 (wallclock-paced), %dx%d hint=%dfps%s",
                        w, h, fps_hint, " [hflip]" if self._mirror_flip else "")
        else:
            # Raw frames
            ff_pix = _qt_pix_to_ffmpeg(fmt)
            if ff_pix is None:
                raise RuntimeError(
                    f"Unsupported QVideoFrame pixel format for recording: {fmt.name}"
                )
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-use_wallclock_as_timestamps", "1",
                "-fflags", "+genpts",
                "-f", "rawvideo",
                "-pixel_format", ff_pix,
                "-video_size", f"{w}x{h}",
                "-framerate", str(fps_hint),
                "-i", "pipe:0",
                "-vsync", "vfr",
                *vf,
                "-c:v", "libx264", "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", str(out_path),
            ]
            LOGGER.info("Recorder: raw %s → libx264 (wallclock-paced), %dx%d hint=%dfps%s",
                        ff_pix, w, h, fps_hint, " [hflip]" if self._mirror_flip else "")

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
        # Fresh queue + writer thread for this recording session
        self._write_queue = queue.Queue(maxsize=8)
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="ffmpeg-writer",
            daemon=True,
        )
        self._writer_thread.start()
        self._first_frame_seen = True
        self._recording_start_wallclock = time.monotonic()
        self._last_frame_wallclock = self._recording_start_wallclock
        LOGGER.info("Recorder ffmpeg started (pid=%d)", self._ffmpeg.pid)

    def _writer_loop(self) -> None:
        """Drain the frame queue to ffmpeg stdin. Runs on a dedicated thread."""
        while True:
            item = self._write_queue.get()
            if item is None:  # sentinel — stop after draining
                break
            proc = self._ffmpeg
            if proc is None or proc.stdin is None:
                continue
            try:
                for chunk in item:
                    proc.stdin.write(chunk)
                self._frame_count += 1
            except (BrokenPipeError, OSError) as exc:
                LOGGER.warning("ffmpeg pipe closed in writer thread: %s (frames=%d)",
                               exc, self._frame_count)
                # Drain remaining items so stop() can proceed without blocking
                while not self._write_queue.empty():
                    try:
                        self._write_queue.get_nowait()
                    except queue.Empty:
                        break
                break

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
        # Tear down the per-frame callback before everything else
        self._disconnect_frame_handler()

        # Let the writer thread drain all queued frames before we close the pipe
        if self._writer_thread is not None:
            self._write_queue.put(None)  # sentinel
            self._writer_thread.join(timeout=5)
            self._writer_thread = None

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

    @staticmethod
    def _apply_best_format(camera: QCamera, device, width: int, height: int, fps: int) -> float:
        """Pick the best camera format.

        Scoring priority:
          1. MJPEG over raw (Pi-friendly: cheap to decode, low USB bandwidth)
          2. Matching ASPECT RATIO with the requested resolution
             (so a 16:9 request doesn't get a 4:3 mode that pillarboxes
             the mirror display)
          3. Closest to requested pixel count
          4. Highest fps among ties

        Returns the actual fps the camera will deliver.
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

        def is_mjpeg(fmt: QCameraFormat) -> bool:
            return "jpeg" in fmt.pixelFormat().name.lower()

        mjpeg_formats = [f for f in formats if is_mjpeg(f)]
        candidates = mjpeg_formats if mjpeg_formats else formats

        target_pixels = width * height
        target_aspect = width / max(1, height)

        def score(fmt: QCameraFormat) -> tuple:
            res = fmt.resolution()
            fmt_aspect = res.width() / max(1, res.height())
            # Bucket aspect mismatch: anything > 0.1 ratio difference is
            # "wrong aspect" (separates 4:3 ≈ 1.33 from 16:9 ≈ 1.78).
            aspect_off = 1 if abs(fmt_aspect - target_aspect) > 0.1 else 0
            pixel_diff = abs(res.width() * res.height() - target_pixels)
            return (aspect_off, pixel_diff, -fmt.maxFrameRate())

        best = min(candidates, key=score)
        camera.setCameraFormat(best)
        actual_fps = best.maxFrameRate()
        LOGGER.info(
            "QCamera selected: %dx%d @ %.0ffps  pixel=%s  (requested %dx%d @ %dfps, aspect %.2f)",
            best.resolution().width(), best.resolution().height(),
            actual_fps, best.pixelFormat().name,
            width, height, fps, target_aspect,
        )
        return float(actual_fps)

    @Slot(result=bool)
    def is_alive(self) -> bool:
        if not self._active or self._camera is None:
            return False
        # While recording, the QCamera can stay "active" even though the ffmpeg
        # writer process has died (disk full / OOM / killed).  isActive() alone
        # wouldn't notice, so the failure would only surface at Stop as a
        # truncated or empty clip.  Treat a dead writer as not-alive so the
        # recording controller's liveness poll aborts promptly and tells the
        # customer, rather than silently losing their recording.
        # (is_alive runs on the GUI thread, as does end_recording, so reading
        # self._ffmpeg here can't race the writer being torn down; snapshot the
        # reference anyway to avoid a None-deref if it flips between lines.)
        ffm = self._ffmpeg
        if ffm is not None and ffm.poll() is not None:
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
