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

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    @staticmethod
    def allocate_udp_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _start_pipe_logger(self, label: str, pipe) -> None:
        """Drain a subprocess pipe in a background thread, writing to the logger."""
        if pipe is None:
            return

        def _drain():
            try:
                for raw_line in pipe:
                    line = raw_line.decode(errors="replace").rstrip() if isinstance(raw_line, bytes) else raw_line.rstrip()
                    if line:
                        self._logger.debug("[%s] %s", label, line)
            except Exception:  # noqa: BLE001
                pass

        thread = threading.Thread(target=_drain, daemon=True)
        thread.start()
