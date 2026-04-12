"""USB/V4L2 webcam adapter using ffmpeg."""
from __future__ import annotations

import glob
import shutil
import signal
import subprocess
from pathlib import Path

from app.models.entities import CameraPreview, CompletedCapture
from app.platform.base_camera_adapter import BaseCameraAdapter


class UsbCameraAdapter(BaseCameraAdapter):
    backend_name = "usb"

    def __init__(self) -> None:
        super().__init__()
        self._proc: subprocess.Popen | None = None
        self._capture_path: Path | None = None
        self._capture_fmt: str | None = None

    def is_available(self) -> bool:
        return bool(_detect_devices())

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
        self.stop(discard=True)
        device = _resolve_device(device_hint)
        ctrl_port = self.allocate_udp_port()
        mir_port = self.allocate_udp_port()
        cap_path = work_dir / f"capture_{ctrl_port}.mp4"

        tee_targets = "|".join([
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{ctrl_port}?pkt_size=1316",
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mir_port}?pkt_size=1316",
            f"[f=mp4:movflags=+faststart:onfail=ignore]{cap_path}",
        ])
        self._spawn(_ffmpeg_cmd(device, width, height, fps, bitrate, tee_targets))
        self._capture_path = cap_path
        self._capture_fmt = "mp4"
        return CameraPreview(
            control_preview_url=_udp(ctrl_port),
            mirror_preview_url=_udp(mir_port),
            backend=self.backend_name,
            recording=True,
        )

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
        self.stop(discard=True)
        device = _resolve_device(device_hint)
        ctrl_port = self.allocate_udp_port()
        mir_port = self.allocate_udp_port()

        tee_targets = "|".join([
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{ctrl_port}?pkt_size=1316",
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mir_port}?pkt_size=1316",
        ])
        self._spawn(_ffmpeg_cmd(device, width, height, fps, bitrate, tee_targets))
        self._capture_path = None
        self._capture_fmt = None
        return CameraPreview(
            control_preview_url=_udp(ctrl_port),
            mirror_preview_url=_udp(mir_port),
            backend=self.backend_name,
            recording=False,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.send_signal(signal.SIGINT)
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        self._proc = None

        cap_path = self._capture_path
        cap_fmt = self._capture_fmt
        self._capture_path = None
        self._capture_fmt = None

        if cap_path and discard:
            cap_path.unlink(missing_ok=True)
            return None
        if cap_path and cap_fmt:
            return CompletedCapture(file_path=cap_path, file_format=cap_fmt, backend=self.backend_name)
        return None

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _spawn(self, command: list[str]) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required for USB camera capture")
        self._proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._start_pipe_logger("ffmpeg", self._proc.stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_devices() -> list[str]:
    """Return V4L2 capture device paths, filtering out codec/ISP nodes.

    On Raspberry Pi, /dev/video* includes bcm2835 codec and ISP devices that
    are not real cameras.  v4l2-ctl --list-devices groups devices by name, so
    we skip any group whose header contains 'bcm2835' or 'isp'.  Falls back to
    a plain glob when v4l2-ctl is not installed.
    """
    if shutil.which("v4l2-ctl"):
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--list-devices"],
                capture_output=True, text=True, timeout=5,
            )
            devices: list[str] = []
            include_block = False
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.endswith(":"):
                    # Device-group header — skip Pi codec/ISP nodes
                    lower = stripped.lower()
                    include_block = "bcm2835" not in lower and "isp" not in lower and "codec" not in lower
                elif include_block and stripped.startswith("/dev/video"):
                    devices.append(stripped)
            if devices:
                return sorted(set(devices))
        except Exception:  # noqa: BLE001
            pass
    return sorted(glob.glob("/dev/video*"))


def _resolve_device(hint: str | None) -> str:
    if hint and Path(hint).exists():
        return hint
    devices = _detect_devices()
    if not devices:
        raise RuntimeError("No USB camera device found under /dev/video*")
    return devices[0]


def _probe_best_format(device: str, width: int, height: int, fps: int) -> tuple[str, int, int]:
    """Return (input_format, actual_width, actual_height) for this camera.

    Parses `v4l2-ctl --list-formats-ext` to find the best input format that
    supports the requested resolution and fps.  Prefers MJPEG because raw
    YUYV at 1280×720 is limited to ~10 fps on USB 2.0 due to bandwidth.

    Falls back gracefully when v4l2-ctl is unavailable or the parse fails.
    """
    import re  # noqa: PLC0415

    if not shutil.which("v4l2-ctl"):
        return "", width, height

    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device, "--list-formats-ext"],
            capture_output=True, text=True, timeout=8,
        )
        output = result.stdout

        # Structure: sections delimited by "Index : N" lines, each section has
        # a "Pixel Format" line, then "Size: Discrete WxH" lines, then
        # "\tInterval: Discrete N/D (F.FF fps)" lines.
        #
        # We collect all (format, w, h, fps) tuples then score them.

        current_fmt = ""
        current_w = current_h = 0
        candidates: list[tuple[str, int, int, float]] = []

        for line in output.splitlines():
            stripped = line.strip()
            fmt_match = re.search(r"Pixel Format\s*:\s+'?(\w+)'?", stripped, re.IGNORECASE)
            if fmt_match:
                current_fmt = fmt_match.group(1).lower()
            size_match = re.search(r"Size:\s+Discrete\s+(\d+)x(\d+)", stripped, re.IGNORECASE)
            if size_match:
                current_w, current_h = int(size_match.group(1)), int(size_match.group(2))
            fps_match = re.search(r"\((\d+\.\d+|\d+)\s+fps\)", stripped, re.IGNORECASE)
            if fps_match and current_fmt:
                candidates.append((current_fmt, current_w, current_h, float(fps_match.group(1))))

        if not candidates:
            # Fallback: at least check if MJPEG is advertised
            if "mjpeg" in output.lower():
                return "mjpeg", width, height
            return "", width, height

        target_res = (width, height)

        def _score(c: tuple[str, int, int, float]) -> tuple[int, int, int]:
            fmt, w, h, cfps = c
            fmt_pref = 0 if fmt == "mjpeg" else 1       # prefer MJPEG
            res_exact = 0 if (w, h) == target_res else 1 # prefer exact resolution
            fps_diff = abs(cfps - fps)
            return (fmt_pref, res_exact, int(fps_diff * 100))

        best = min(candidates, key=_score)
        best_fmt, best_w, best_h, best_fps = best

        import logging  # noqa: PLC0415
        logging.getLogger(__name__).info(
            "Camera %s: using format=%s res=%dx%d (wanted %dx%d) best_fps=%.0f (wanted %d)",
            device, best_fmt, best_w, best_h, width, height, best_fps, fps,
        )

        # If the camera can't do the requested resolution at all, fall back to
        # the best resolution it does offer (sorted: closest total pixels).
        if (best_w, best_h) != target_res:
            logging.getLogger(__name__).warning(
                "Camera does not support %dx%d — falling back to %dx%d",
                width, height, best_w, best_h,
            )

        return best_fmt, best_w, best_h

    except Exception:  # noqa: BLE001
        return "", width, height


def _ffmpeg_cmd(device: str, width: int, height: int, fps: int, bitrate: int, tee: str) -> list[str]:
    input_fmt, actual_w, actual_h = _probe_best_format(device, width, height, fps)
    input_fmt_args = ["-input_format", input_fmt] if input_fmt else []
    return [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning",
        "-f", "v4l2",
        *input_fmt_args,
        "-framerate", str(fps),
        "-video_size", f"{actual_w}x{actual_h}",
        # Large input thread queue: the all-I-frame encoder (-g 1) can momentarily
        # stall consuming frames on a Pi.  Without buffering, V4L2 times out on
        # VIDIOC_DQBUF and kills the capture.  4096 frames of queue gives the
        # encoder ~135 s of slack at 30fps — plenty to absorb any encoder hiccup.
        "-thread_queue_size", "4096",
        "-i", device,
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", str(bitrate),
        "-pix_fmt", "yuv420p",
        # Force every frame to be an I-frame (gop=1).  With inter-frame
        # prediction (P/B frames), a single lost UDP packet corrupts every
        # dependent frame until the next keyframe — causing seconds of
        # mosaic artefacts.  With gop=1 every frame is self-contained, so
        # a dropped packet glitches exactly one frame (~33 ms) instead of
        # cascading.  Total bitrate stays the same; file size is unaffected
        # because -b:v still caps the throughput.
        "-g", "1",
        # Explicit stream mapping required by the tee muxer.
        "-map", "0:v:0",
        "-f", "tee", tee,
    ]


def _udp(port: int) -> str:
    # fifo_size: sender-side queue in bytes.  5 MB was the old value —
    # that let ffmpeg buffer ~5 s of video before dropping, adding visible
    # latency.  512 KB keeps the pipeline moving with only ~0.5 s headroom.
    return f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=524288"
