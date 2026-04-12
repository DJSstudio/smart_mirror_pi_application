"""Camera service — selects the right adapter and manages the active session."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config.paths import AppPaths
from app.models.entities import CameraPreview, CompletedCapture
from app.platform.raspberry_pi_camera_adapter import RaspberryPiCameraAdapter
from app.platform.usb_camera_adapter import UsbCameraAdapter
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class CameraService:
    def __init__(self, paths: AppPaths, settings: SettingsService) -> None:
        self._paths = paths
        self._settings = settings
        self._pi = RaspberryPiCameraAdapter()
        self._usb = UsbCameraAdapter()
        self._active = None  # currently running adapter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_recording(self) -> CameraPreview:
        self._stop_any(discard=True)
        adapter = self._pick()
        self._active = adapter
        return adapter.start_recording(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device") or None,
        )

    def start_preview_only(self) -> CameraPreview:
        self._stop_any(discard=True)
        adapter = self._pick()
        self._active = adapter
        return adapter.start_preview(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device") or None,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        capture = self._stop_any(discard=discard)
        return capture

    def is_active(self) -> bool:
        return self._active is not None

    def is_alive(self) -> bool:
        """Return True if the active camera subprocess is still running."""
        if self._active is None:
            return False
        return self._active.is_alive()

    def available_backends(self) -> list[dict[str, object]]:
        return [
            {"key": "auto",         "label": "Auto detect",          "available": self._pi.is_available() or self._usb.is_available()},
            {"key": "raspberry_pi", "label": "Raspberry Pi camera",   "available": self._pi.is_available()},
            {"key": "usb",          "label": "USB webcam",            "available": self._usb.is_available()},
        ]

    def current_backend_label(self) -> str:
        adapter = self._active or self._pick(raise_on_missing=False)
        if adapter is None:
            return "No camera"
        return adapter.backend_name

    def dependencies_ok(self) -> dict[str, bool]:
        return {
            "rpicam-vid": shutil.which("rpicam-vid") is not None,
            "ffmpeg":     shutil.which("ffmpeg")     is not None,
            "ffprobe":    shutil.which("ffprobe")    is not None,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _stop_any(self, discard: bool) -> CompletedCapture | None:
        if self._active is None:
            return None
        result = self._active.stop(discard=discard)
        self._active = None
        return result

    def _pick(self, raise_on_missing: bool = True):
        pref = str(self._settings.get("camera_backend", "auto"))
        if pref == "raspberry_pi" and self._pi.is_available():
            return self._pi
        if pref == "usb" and self._usb.is_available():
            return self._usb
        # auto
        if self._pi.is_available():
            return self._pi
        if self._usb.is_available():
            return self._usb
        if raise_on_missing:
            raise RuntimeError(
                "No camera backend available. "
                "Connect a USB webcam or ensure rpicam-vid is installed."
            )
        return None
