from __future__ import annotations

import logging
import socket
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from app.models.entities import CameraPreview, CompletedCapture


class BaseCameraAdapter(ABC):
    backend_name = "base"

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def stop(self, discard: bool = False) -> CompletedCapture | None:
        raise NotImplementedError

    @staticmethod
    def allocate_udp_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _start_pipe_logger(self, name: str, stream) -> None:
        def _reader() -> None:
            if stream is None:
                return
            while True:
                line = stream.readline()
                if not line:
                    break
                try:
                    message = line.decode("utf-8", errors="replace").strip()
                except AttributeError:
                    message = str(line).strip()
                if message:
                    self._logger.debug("%s | %s", name, message)

        threading.Thread(target=_reader, daemon=True).start()
