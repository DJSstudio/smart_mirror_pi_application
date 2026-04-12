from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path

from app.models.entities import CameraPreview, CompletedCapture
from app.platform.base_camera_adapter import BaseCameraAdapter


class RaspberryPiCameraAdapter(BaseCameraAdapter):
    backend_name = "raspberry_pi"

    def __init__(self) -> None:
        super().__init__()
        self._rpicam_process: subprocess.Popen | None = None
        self._ffmpeg_process: subprocess.Popen | None = None
        self._current_capture_path: Path | None = None
        self._current_format: str | None = None

    def is_available(self) -> bool:
        return shutil.which("rpicam-vid") is not None

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
        del device_hint
        self.stop(discard=True)
        control_port = self.allocate_udp_port()
        mirror_port = self.allocate_udp_port()
        capture_path = work_dir / f"capture_{os.getpid()}_{control_port}.h264"
        outputs = [
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{control_port}?pkt_size=1316",
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mirror_port}?pkt_size=1316",
            f"[f=h264:onfail=ignore]{capture_path}",
        ]
        self._spawn_pipeline(
            rpicam_args=[
                "rpicam-vid",
                "--nopreview",
                "--timeout",
                "0",
                "--width",
                str(width),
                "--height",
                str(height),
                "--framerate",
                str(fps),
                "--codec",
                "h264",
                "--inline",
                "--bitrate",
                str(bitrate),
                "-o",
                "-",
            ],
            ffmpeg_args=[
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-f",
                "h264",
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                "copy",
                "-map",
                "0:v:0",
                "-f",
                "tee",
                "|".join(outputs),
            ],
        )
        self._current_capture_path = capture_path
        self._current_format = "h264"
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
        del work_dir, device_hint
        self.stop(discard=True)
        control_port = self.allocate_udp_port()
        mirror_port = self.allocate_udp_port()
        outputs = [
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{control_port}?pkt_size=1316",
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mirror_port}?pkt_size=1316",
        ]
        self._spawn_pipeline(
            rpicam_args=[
                "rpicam-vid",
                "--nopreview",
                "--timeout",
                "0",
                "--width",
                str(width),
                "--height",
                str(height),
                "--framerate",
                str(fps),
                "--codec",
                "h264",
                "--inline",
                "--bitrate",
                str(bitrate),
                "-o",
                "-",
            ],
            ffmpeg_args=[
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-f",
                "h264",
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                "copy",
                "-map",
                "0:v:0",
                "-f",
                "tee",
                "|".join(outputs),
            ],
        )
        self._current_capture_path = None
        self._current_format = None
        return CameraPreview(
            control_preview_url=_udp_url(control_port),
            mirror_preview_url=_udp_url(mirror_port),
            backend=self.backend_name,
            recording=False,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        if self._rpicam_process:
            self._stop_process(self._rpicam_process, "rpicam-vid")
            self._rpicam_process = None
        if self._ffmpeg_process:
            self._stop_process(self._ffmpeg_process, "ffmpeg")
            self._ffmpeg_process = None

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

    def _spawn_pipeline(self, *, rpicam_args: list[str], ffmpeg_args: list[str]) -> None:
        self._logger.info("Starting Raspberry Pi camera pipeline")
        self._rpicam_process = subprocess.Popen(
            rpicam_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert self._rpicam_process.stdout is not None
        self._ffmpeg_process = subprocess.Popen(
            ffmpeg_args,
            stdin=self._rpicam_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._rpicam_process.stdout.close()
        self._start_pipe_logger("rpicam", self._rpicam_process.stderr)
        self._start_pipe_logger("ffmpeg", self._ffmpeg_process.stderr)

    def _stop_process(self, process: subprocess.Popen, label: str) -> None:
        if process.poll() is not None:
            return
        self._logger.info("Stopping %s", label)
        try:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


def _udp_url(port: int) -> str:
    return f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=5000000"
