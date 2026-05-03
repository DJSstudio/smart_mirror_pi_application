"""USB camera adapter that combines ffmpeg recording with Qt's native
QCamera preview, multiplexed via a v4l2loopback device.

Architecture
────────────
  Real /dev/videoN (USB camera, owned by ffmpeg)
        │
   [ ffmpeg subprocess ]
        ├── encodes H.264 to file        (recording, proven path)
        └── pipes raw frames to /dev/video10  (v4l2loopback)
                                                     │
                                              [ QCamera in Qt main process ]
                                                     │
                                              QML VideoOutput on the mirror

Why this works where everything else failed:
  - One process owns the real camera (no sharing conflicts)
  - Recording uses the proven ffmpeg path
  - Preview uses the proven QCamera path (verified by scripts/test_qcamera.py)
  - No QMediaRecorder (broken on Pi), no UDP/MPEGTS (high latency), no
    encode-then-decode round trip
  - Latency is ~50-100ms (frame capture → loopback → QCamera render)

Requirements:
  - v4l2loopback kernel module loaded with video_nr=10 (install_deps.sh
    handles this).
  - ffmpeg (already required) and a USB camera capable of MJPEG output.
"""
from __future__ import annotations

import glob
import logging
import shutil
import signal
import subprocess
import time
from pathlib import Path

from app.models.entities import CameraPreview, CompletedCapture
from app.platform.base_camera_adapter import BaseCameraAdapter
from app.platform.usb_camera_adapter import _probe_best_format
from app.services.qt_camera_session import QtCameraSession

LOGGER = logging.getLogger(__name__)

LOOPBACK_DEVICE = "/dev/video10"


class V4L2LoopbackCameraAdapter(BaseCameraAdapter):
    backend_name = "usb_loopback"

    def __init__(self, qt_session: QtCameraSession) -> None:
        super().__init__()
        self._qt = qt_session
        self._proc: subprocess.Popen | None = None
        self._capture_path: Path | None = None
        self._source_device: str | None = None

    def is_available(self) -> bool:
        # Need the loopback device AND at least one real source camera
        if not Path(LOOPBACK_DEVICE).exists():
            return False
        return _resolve_source_device(None) is not None

    # ------------------------------------------------------------------

    def start_recording(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
    ) -> CameraPreview:
        return self._start(work_dir, width, height, fps, bitrate, device_hint, record=True)

    def start_preview(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
    ) -> CameraPreview:
        return self._start(work_dir, width, height, fps, bitrate, device_hint, record=False)

    def _start(
        self,
        work_dir: Path,
        width: int, height: int, fps: int, bitrate: int,
        device_hint: str | None,
        record: bool,
    ) -> CameraPreview:
        self.stop(discard=True)
        if not Path(LOOPBACK_DEVICE).exists():
            raise RuntimeError(
                f"v4l2loopback device {LOOPBACK_DEVICE} not present. "
                "Run scripts/install_deps.sh, or "
                "`sudo modprobe v4l2loopback video_nr=10 exclusive_caps=1`"
            )

        source = _resolve_source_device(device_hint)
        if source is None:
            raise RuntimeError(
                "No USB camera capture device found.  Plug in the camera and "
                "verify with `v4l2-ctl --list-devices`."
            )
        self._source_device = source

        # Probe the camera to find a (format, width, height) it actually
        # supports.  E.g. IMX335 has MJPEG @ 1080p but not @ 720p — naively
        # asking for 1280x720 MJPEG would fail.  This snaps to the closest
        # supported mode, preferring MJPEG.
        input_format, actual_w, actual_h = _probe_best_format(source, width, height, fps)
        LOGGER.info(
            "Camera %s: requested %dx%d → using format=%s actual=%dx%d",
            source, width, height, input_format or "(default)", actual_w, actual_h,
        )

        cap_path = work_dir / f"capture_{int(time.time() * 1000)}.mp4" if record else None
        cmd = _ffmpeg_cmd(
            source=source,
            loopback=LOOPBACK_DEVICE,
            width=actual_w, height=actual_h, fps=fps,
            bitrate=bitrate,
            input_format=input_format,
            capture_path=cap_path,
        )
        self._spawn(cmd)
        self._capture_path = cap_path

        # Give ffmpeg a moment to open the camera and start producing frames
        # to the loopback before we ask QCamera to open it.
        self._wait_for_loopback_active(timeout=3.0)

        # Now hook QCamera to the loopback for smooth preview
        try:
            self._qt.start_preview(
                device_hint=LOOPBACK_DEVICE,
                width=width, height=height, fps=fps,
            )
        except Exception as exc:
            LOGGER.error("QCamera failed to attach to loopback: %s", exc)
            self.stop(discard=True)
            raise

        return CameraPreview(
            control_preview_url="",
            mirror_preview_url="",  # mirror reads QCamera videoSink directly
            backend=self.backend_name,
            recording=record,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        # Stop QCamera first so it stops trying to read from the loopback
        try:
            self._qt.stop()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("QCamera stop failed (non-fatal): %s", exc)

        # Then stop ffmpeg — gracefully if we want the file, hard kill if not
        if self._proc and self._proc.poll() is None:
            if discard:
                self._proc.kill()
                self._proc.wait()
            else:
                try:
                    self._proc.send_signal(signal.SIGINT)
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                        self._proc.wait()
        self._proc = None

        cap_path = self._capture_path
        self._capture_path = None
        self._source_device = None

        if cap_path is None:
            return None
        if discard:
            cap_path.unlink(missing_ok=True)
            return None
        if not cap_path.exists():
            return None
        return CompletedCapture(
            file_path=cap_path,
            file_format="mp4",
            backend=self.backend_name,
        )

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------

    def _spawn(self, command: list[str]) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required for camera capture")
        LOGGER.info("Starting capture: %s", " ".join(command))
        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._start_pipe_logger("ffmpeg", self._proc.stderr)

    def _wait_for_loopback_active(self, timeout: float) -> None:
        """Block briefly until ffmpeg has started writing to /dev/video10.

        QCamera open will fail if the loopback has no producer yet.  We
        poll until the loopback reports a non-zero size of advertised
        formats, or the timeout elapses.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.is_alive():
                # ffmpeg died — surface the error to the caller
                raise RuntimeError("ffmpeg exited before producing frames")
            if _loopback_has_format(LOOPBACK_DEVICE):
                LOGGER.info("Loopback %s ready", LOOPBACK_DEVICE)
                return
            time.sleep(0.1)
        LOGGER.warning("Loopback did not become ready within %.1fs; trying anyway", timeout)


# ---------------------------------------------------------------------------
# ffmpeg command builder
# ---------------------------------------------------------------------------

def _ffmpeg_cmd(
    *,
    source: str,
    loopback: str,
    width: int, height: int, fps: int,
    bitrate: int,
    input_format: str,
    capture_path: Path | None,
) -> list[str]:
    """Build the dual-output ffmpeg command.

    Output 1 (loopback): passthrough copy of camera frames (no re-encode,
    low CPU).  QCamera on the loopback receives the same frames the sensor
    produced — MJPEG, YUYV, whatever the source supplied.
    Output 2 (file): re-encoded to H.264 in MP4 container.  Uses libx264
    ultrafast/zerolatency.
    """
    input_fmt_args = ["-input_format", input_format] if input_format else []
    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning",
        "-f", "v4l2",
        *input_fmt_args,
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-thread_queue_size", "4096",
        "-i", source,
        "-an",
        # Output 1: loopback (passthrough copy of input frames)
        "-map", "0:v", "-c:v", "copy",
        "-f", "v4l2", loopback,
    ]
    if capture_path is not None:
        cmd.extend([
            # Output 2: H.264 file
            "-map", "0:v",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", str(bitrate),
            "-pix_fmt", "yuv420p",
            "-g", str(max(fps // 2, 1)),
            "-movflags", "+faststart",
            "-f", "mp4",
            str(capture_path),
        ])
    return cmd


# ---------------------------------------------------------------------------
# Source camera detection
# ---------------------------------------------------------------------------

def _is_video_capture(device: str) -> bool:
    """Strict: only single-planar Video Capture devices (not multiplanar
    codec/ISP queues, not metadata siblings)."""
    if not shutil.which("v4l2-ctl"):
        return True
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device, "--list-formats"],
            capture_output=True, text=True, timeout=3,
        )
        text = result.stdout
        if "Multiplanar" in text:
            return False
        return (
            "Type: Video Capture" in text
            and any(line.strip().startswith("[") and "]:" in line
                    for line in text.splitlines())
        )
    except Exception:  # noqa: BLE001
        return True


def _resolve_source_device(hint: str | None) -> str | None:
    """Pick the real USB camera device, excluding the loopback itself."""
    if hint and Path(hint).exists() and hint != LOOPBACK_DEVICE:
        return hint

    candidates: list[str] = []
    if shutil.which("v4l2-ctl"):
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--list-devices"],
                capture_output=True, text=True, timeout=5,
            )
            include = False
            for raw in result.stdout.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.endswith(":"):
                    lower = line.lower()
                    include = (
                        "bcm2835" not in lower
                        and "isp" not in lower
                        and "codec" not in lower
                        and "loopback" not in lower
                        and "mirrorpreview" not in lower
                    )
                elif include and line.startswith("/dev/video"):
                    candidates.append(line)
        except Exception:  # noqa: BLE001
            pass

    if not candidates:
        candidates = sorted(glob.glob("/dev/video*"))

    # Filter out the loopback itself + non-capture nodes (multiplanar/metadata)
    for dev in sorted(set(candidates)):
        if dev == LOOPBACK_DEVICE:
            continue
        if _is_video_capture(dev):
            LOGGER.info("Source camera: %s", dev)
            return dev
        else:
            LOGGER.debug("Skipping %s (not a usable Video Capture device)", dev)
    return None


def _loopback_has_format(device: str) -> bool:
    """True if the loopback device currently has a format set (which means
    a producer is feeding it).  We use this as readiness signal."""
    if not shutil.which("v4l2-ctl"):
        return True
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device, "--get-fmt-video"],
            capture_output=True, text=True, timeout=2,
        )
        # Active loopback prints a width/height; idle one returns "Format Video Capture: ... Width/Height: 0/0"
        if "Width/Height" in result.stdout:
            return "0/0" not in result.stdout
        return False
    except Exception:  # noqa: BLE001
        return False
