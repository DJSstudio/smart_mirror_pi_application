from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config.paths import AppPaths
from app.models.entities import CameraPreview, CompletedCapture
from app.platform.raspberry_pi_camera_adapter import RaspberryPiCameraAdapter
from app.platform.usb_camera_adapter import UsbCameraAdapter
from app.services.settings_service import SettingsService


class CameraService:
    def __init__(self, paths: AppPaths, settings: SettingsService) -> None:
        self._paths = paths
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._pi_adapter = RaspberryPiCameraAdapter()
        self._usb_adapter = UsbCameraAdapter()
        self._active_adapter = None

    def start_recording(self) -> CameraPreview:
        self.stop(discard=True)
        adapter = self._select_adapter()
        self._active_adapter = adapter
        return adapter.start_recording(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device"),
        )

    def start_preview_only(self) -> CameraPreview:
        self.stop(discard=True)
        adapter = self._select_adapter()
        self._active_adapter = adapter
        return adapter.start_preview(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device"),
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        if self._active_adapter is None:
            return None
        capture = self._active_adapter.stop(discard=discard)
        self._active_adapter = None
        return capture

    def available_backends(self) -> list[dict[str, object]]:
        return [
            {
                "key": "auto",
                "label": "Auto detect",
                "available": self._pi_adapter.is_available() or self._usb_adapter.is_available(),
            },
            {
                "key": "raspberry_pi",
                "label": "Raspberry Pi camera",
                "available": self._pi_adapter.is_available(),
            },
            {
                "key": "usb",
                "label": "USB webcam",
                "available": self._usb_adapter.is_available(),
            },
        ]

    def current_backend_label(self) -> str:
        adapter = self._active_adapter or self._select_adapter(raise_on_missing=False)
        if adapter is None:
            return "Unavailable"
        return adapter.backend_name

    def dependencies_summary(self) -> dict[str, bool]:
        return {
            "rpicam-vid": shutil.which("rpicam-vid") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None,
        }

    def _select_adapter(self, raise_on_missing: bool = True):
        preference = str(self._settings.get("camera_backend", "auto"))
        if preference == "raspberry_pi":
            if self._pi_adapter.is_available():
                return self._pi_adapter
        elif preference == "usb":
            if self._usb_adapter.is_available():
                return self._usb_adapter
        else:
            if self._pi_adapter.is_available():
                return self._pi_adapter
            if self._usb_adapter.is_available():
                return self._usb_adapter
        if not raise_on_missing:
            return None
        raise RuntimeError(
            "No supported camera backend is available. Install rpicam-vid or attach a /dev/video* webcam."
        )
