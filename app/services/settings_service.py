"""Persistent settings service backed by a JSON file."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    # Camera
    "camera_backend": "auto",   # "auto" | "raspberry_pi" | "usb"
    "camera_device": "",        # explicit /dev/videoN path (empty = auto)
    "camera_width": 1280,
    "camera_height": 720,
    "camera_fps": 30,
    "camera_bitrate": 8_000_000,
    # Recording
    "countdown_seconds": 3,
    # Mirror
    "mirror_orientation_degrees": 0,  # 0 | 90 | 180 | 270
    "compare_fill_crop": True,
    # Screens
    "control_screen_index": 0,
    "mirror_screen_index": 1,
    # Logging
    "log_level": "INFO",
    # Network — fixed port keeps localStorage device_id consistent across restarts
    "share_server_port": 8765,
    # Idle auto-logout
    "idle_timeout_seconds": 300,
    "idle_warning_seconds": 60,
}


class SettingsService:
    def __init__(self, paths) -> None:
        self._path: Path = paths.config_path
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else _DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def all_settings(self) -> dict[str, Any]:
        return dict(self._data)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            loaded = json.loads(self._path.read_text())
            self._data.update(loaded)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not load settings from %s: %s", self._path, exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not save settings to %s: %s", self._path, exc)
