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


def _probe_input_format(device: str) -> str:
    """Return 'mjpeg' if the device supports MJPEG capture, otherwise ''."""
    if not shutil.which("v4l2-ctl"):
        return ""
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device, "--list-formats"],
            capture_output=True, text=True, timeout=5,
        )
        if "mjpeg" in result.stdout.lower():
            return "mjpeg"
    except Exception:  # noqa: BLE001
        pass
    return ""


def _ffmpeg_cmd(device: str, width: int, height: int, fps: int, bitrate: int, tee: str) -> list[str]:
    input_fmt = _probe_input_format(device)
    input_fmt_args = ["-input_format", input_fmt] if input_fmt else []
    return [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning",
        "-fflags", "nobuffer",
        "-f", "v4l2",
        *input_fmt_args,
        "-framerate", str(fps),
        "-video_size", f"{width}x{height}",
        "-i", device,
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", str(bitrate),
        "-pix_fmt", "yuv420p",
        "-g", str(max(fps, 10)),
        # Explicit stream mapping is required by the tee muxer to route the
        # video stream to every output target.
        "-map", "0:v:0",
        "-f", "tee", tee,
    ]


def _udp(port: int) -> str:
    return f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=5000000"
