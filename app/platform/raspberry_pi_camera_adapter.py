"""Raspberry Pi CSI camera adapter using rpicam-vid + ffmpeg tee."""
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
        self._rpicam_proc: subprocess.Popen | None = None
        self._ffmpeg_proc: subprocess.Popen | None = None
        self._capture_path: Path | None = None
        self._capture_fmt: str | None = None

    def is_available(self) -> bool:
        if not shutil.which("rpicam-vid"):
            return False
        # Verify a camera module is actually detected by libcamera.
        # rpicam-vid --list-cameras outputs "No cameras available" when none
        # are connected or the camera interface is disabled in firmware.
        try:
            result = subprocess.run(
                ["rpicam-vid", "--list-cameras"],
                capture_output=True, text=True, timeout=5,
            )
            combined = (result.stdout + result.stderr).lower()
            # Unknown flag means old rpicam build — fall back to binary check only
            if "unrecognised" in combined or "unknown option" in combined:
                return True
            if "no cameras" in combined or "0 : " not in combined:
                return False
            return True
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return True

    def start_recording(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
        mirror_flip: bool = False,
        mirror_orientation_degrees: int = 0,
    ) -> CameraPreview:
        self.stop(discard=True)
        mir_port = self.allocate_udp_port()
        cap_path = work_dir / f"capture_{os.getpid()}_{mir_port}.h264"

        tee_targets = "|".join([
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mir_port}?pkt_size=1316",
            f"[f=h264:onfail=ignore]{cap_path}",
        ])
        self._spawn(
            rpicam_args=_rpicam_cmd(width, height, fps, bitrate),
            ffmpeg_args=_ffmpeg_tee_cmd(tee_targets),
        )
        self._capture_path = cap_path
        self._capture_fmt = "h264"
        return CameraPreview(
            control_preview_url="",
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
        mirror_flip: bool = False,
        mirror_orientation_degrees: int = 0,
    ) -> CameraPreview:
        self.stop(discard=True)
        mir_port = self.allocate_udp_port()

        tee_targets = (
            f"[f=mpegts:onfail=ignore]udp://127.0.0.1:{mir_port}?pkt_size=1316"
        )
        self._spawn(
            rpicam_args=_rpicam_cmd(width, height, fps, bitrate),
            ffmpeg_args=_ffmpeg_tee_cmd(tee_targets),
        )
        self._capture_path = None
        self._capture_fmt = None
        return CameraPreview(
            control_preview_url="",
            mirror_preview_url=_udp(mir_port),
            backend=self.backend_name,
            recording=False,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        if discard:
            # File not needed — kill both processes immediately rather than
            # waiting for graceful finalization (can block up to 15 s on Pi).
            for proc in (self._rpicam_proc, self._ffmpeg_proc):
                if proc and proc.poll() is None:
                    proc.kill()
                    proc.wait()
        else:
            # Stop rpicam-vid first — closing its stdout pipe sends EOF to
            # ffmpeg, letting it flush and finalise the capture file cleanly.
            if self._rpicam_proc:
                _terminate(self._rpicam_proc, "rpicam-vid")
            # Wait for ffmpeg to finish writing; force-kill only if hung.
            if self._ffmpeg_proc:
                try:
                    self._ffmpeg_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    _terminate(self._ffmpeg_proc, "ffmpeg")
        self._rpicam_proc = None
        self._ffmpeg_proc = None

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
        return self._rpicam_proc is not None and self._rpicam_proc.poll() is None

    # ------------------------------------------------------------------

    def _spawn(self, *, rpicam_args: list[str], ffmpeg_args: list[str]) -> None:
        self._logger.info("Starting Raspberry Pi camera pipeline")
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required for Raspberry Pi camera capture")
        self._rpicam_proc = subprocess.Popen(rpicam_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rpicam_stdout = self._rpicam_proc.stdout
        assert rpicam_stdout is not None
        try:
            # ffmpeg stdout is unused (tee → file/UDP) → DEVNULL so it can't
            # fill and stall.  rpicam stdout stays a PIPE feeding ffmpeg stdin.
            self._ffmpeg_proc = subprocess.Popen(
                ffmpeg_args,
                stdin=rpicam_stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except Exception:
            # Don't leave rpicam-vid orphaned holding the CSI camera if the
            # ffmpeg spawn fails (e.g. ENOMEM under pressure).
            self._rpicam_proc.kill()
            self._rpicam_proc.wait()
            self._rpicam_proc = None
            raise
        rpicam_stdout.close()  # let ffmpeg own the pipe
        self._start_pipe_logger("rpicam", self._rpicam_proc.stderr)
        self._start_pipe_logger("ffmpeg", self._ffmpeg_proc.stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpicam_cmd(width: int, height: int, fps: int, bitrate: int) -> list[str]:
    return [
        "rpicam-vid",
        "--nopreview",
        # Use a 24-hour timeout instead of 0 to avoid version-specific
        # ambiguity: on some builds --timeout 0 exits immediately.
        "--timeout", "86400000",
        "--width", str(width),
        "--height", str(height),
        "--framerate", str(fps),
        "--codec", "h264",
        "--inline",   # embed SPS+PPS in every IDR frame (required for streaming)
        # Force every frame to be an IDR (intra=1).  This makes the UDP
        # preview stream fully intra-frame so a lost packet can never
        # corrupt more than a single frame — eliminating the cascading
        # mosaic artefacts seen during live preview.  Also avoids the
        # "black screen for a long time at start" wait while the decoder
        # looks for its first keyframe.
        "--intra", "1",
        "--bitrate", str(bitrate),
        "-o", "-",
    ]


def _ffmpeg_tee_cmd(targets: str) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-probesize", "32",
        "-analyzeduration", "0",
        "-f", "h264",
        "-i", "pipe:0",
        "-an", "-c:v", "copy",
        "-map", "0:v:0",
        # Minimize muxing latency: flush every packet, no mux buffering.
        "-flush_packets", "1",
        "-max_delay", "0",
        "-f", "tee", targets,
    ]


def _udp(port: int) -> str:
    # fifo_size: sender-side queue in bytes.  Smaller = lower worst-case
    # latency (frames are flushed sooner).  262144 (256 KB) gives ~0.15 s
    # of headroom at 12 Mbps — tight enough to keep latency low but enough
    # to absorb brief scheduling jitter on the Pi.
    return f"udp://127.0.0.1:{port}?overrun_nonfatal=1&fifo_size=262144"


def _terminate(proc: subprocess.Popen, label: str) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
