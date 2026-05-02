"""Abstract base for camera adapters."""
from __future__ import annotations

import logging
import socket
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from app.models.entities import CameraPreview, CompletedCapture


class BaseCameraAdapter(ABC):
    backend_name: str = "unknown"

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def start_recording(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
    ) -> CameraPreview: ...

    @abstractmethod
    def start_preview(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
    ) -> CameraPreview: ...

    @abstractmethod
    def stop(self, discard: bool = False) -> CompletedCapture | None: ...

    def is_alive(self) -> bool:
        """Return True if the camera subprocess is still running."""
        return False

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    @staticmethod
    def allocate_udp_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @staticmethod
    def detect_pi_model() -> str:
        """Return the Pi model string (e.g. 'Raspberry Pi 4 Model B Rev 1.4').

        Reads /proc/device-tree/model.  Returns empty string on non-Pi systems.
        Useful for adapting behavior between Pi 4 (hardware H.264 encoder/decoder)
        and Pi 5 (software-only H.264, faster CPU).
        """
        try:
            return Path("/proc/device-tree/model").read_text().rstrip("\x00").strip()
        except (OSError, FileNotFoundError):
            return ""

    def _start_pipe_logger(self, label: str, pipe) -> None:
        """Drain a subprocess pipe in a background thread, writing to the logger.

        Camera process errors are logged at WARNING so they appear in the console
        even at the default INFO log level — this is critical for diagnosing
        why rpicam-vid or ffmpeg fails.
        """
        if pipe is None:
            return

        _error_keywords = ("error", "fail", "cannot", "permission", "denied", "no such", "invalid")

        def _drain():
            try:
                for raw_line in pipe:
                    line = (
                        raw_line.decode(errors="replace").rstrip()
                        if isinstance(raw_line, bytes)
                        else raw_line.rstrip()
                    )
                    if not line:
                        continue
                    if any(k in line.lower() for k in _error_keywords):
                        self._logger.warning("[%s] %s", label, line)
                    else:
                        self._logger.info("[%s] %s", label, line)
            except Exception:  # noqa: BLE001
                pass

        thread = threading.Thread(target=_drain, daemon=True)
        thread.start()
