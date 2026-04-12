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

    def _spawn(self, command: list[str]) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required for USB camera capture")
        self._proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._start_pipe_logger("ffmpeg", self._proc.stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_devices() -> list[str]:
    return sorted(glob.glob("/dev/video*"))


def _resolve_device(hint: str | None) -> str:
    if hint and Path(hint).exists():
        return hint
    devices = _detect_devices()
    if not devices:
        raise RuntimeError("No USB camera device found under /dev/video*")
    return devices[0]


def _ffmpeg_cmd(device: str, width: int, height: int, fps: int, bitrate: int, tee: str) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning",
        "-fflags", "nobuffer",
        "-f", "v4l2",
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
        "-f", "tee", tee,
    ]


def _udp(port: int) -> str:
    return f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=5000000"
