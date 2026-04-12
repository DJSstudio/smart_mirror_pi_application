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
        self._process: subprocess.Popen | None = None
        self._current_capture_path: Path | None = None
        self._current_format: str | None = None

    def is_available(self) -> bool:
        return bool(self._detect_video_devices())

    def start_recording(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None = None,
    ) -> CameraPreview:
        self.stop(discard=True)
        device = self._resolve_device(device_hint)
        control_port = self.allocate_udp_port()
        mirror_port = self.allocate_udp_port()
        capture_path = work_dir / f"capture_{control_port}.mp4"
        outputs = [
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{control_port}?pkt_size=1316",
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mirror_port}?pkt_size=1316",
            f"[f=mp4:movflags=+faststart:onfail=ignore]{capture_path}",
        ]
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "nobuffer",
            "-f",
            "v4l2",
            "-framerate",
            str(fps),
            "-video_size",
            f"{width}x{height}",
            "-i",
            device,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-b:v",
            str(bitrate),
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(max(fps, 10)),
            "-f",
            "tee",
            "|".join(outputs),
        ]
        self._spawn(command)
        self._current_capture_path = capture_path
        self._current_format = "mp4"
        return CameraPreview(
            control_preview_url=_udp_url(control_port),
            mirror_preview_url=_udp_url(mirror_port),
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
        device_hint: str | None = None,
    ) -> CameraPreview:
        del work_dir
        self.stop(discard=True)
        device = self._resolve_device(device_hint)
        control_port = self.allocate_udp_port()
        mirror_port = self.allocate_udp_port()
        outputs = [
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{control_port}?pkt_size=1316",
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mirror_port}?pkt_size=1316",
        ]
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "nobuffer",
            "-f",
            "v4l2",
            "-framerate",
            str(fps),
            "-video_size",
            f"{width}x{height}",
            "-i",
            device,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-b:v",
            str(bitrate),
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(max(fps, 10)),
            "-f",
            "tee",
            "|".join(outputs),
        ]
        self._spawn(command)
        self._current_capture_path = None
        self._current_format = None
        return CameraPreview(
            control_preview_url=_udp_url(control_port),
            mirror_preview_url=_udp_url(mirror_port),
            backend=self.backend_name,
            recording=False,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        if self._process and self._process.poll() is None:
            self._logger.info("Stopping USB camera ffmpeg pipeline")
            try:
                self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
        self._process = None

        capture_path = self._current_capture_path
        capture_format = self._current_format
        self._current_capture_path = None
        self._current_format = None
        if capture_path and discard:
            capture_path.unlink(missing_ok=True)
            return None
        if capture_path and capture_format:
            return CompletedCapture(
                file_path=capture_path,
                file_format=capture_format,
                backend=self.backend_name,
            )
        return None

    def _spawn(self, command: list[str]) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required for USB camera capture")
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._start_pipe_logger("ffmpeg", self._process.stderr)

    def _resolve_device(self, device_hint: str | None) -> str:
        if device_hint and Path(device_hint).exists():
            return device_hint
        devices = self._detect_video_devices()
        if not devices:
            raise RuntimeError("No USB camera device found under /dev/video*")
        return devices[0]

    @staticmethod
    def _detect_video_devices() -> list[str]:
        return sorted(glob.glob("/dev/video*"))


def _udp_url(port: int) -> str:
    return f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=5000000"
