"""Persistent settings service backed by a JSON file."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    # Camera
    "camera_backend": "auto",   # "auto" | "raspberry_pi" | "usb"
    "camera_device": "",        # explicit /dev/videoN path (empty = auto)
    "camera_width": 3840,       # 4K UHD (Pi 5 encodes H.264 in software — 4K is
    "camera_height": 2160,      # heavy; expect ~15fps, 30 may drop frames)
    "camera_fps": 30,
    "camera_bitrate": 15_000_000,
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
    # Camera flip
    "camera_mirror_flip": False,
    # Network — fixed port keeps the device cookie consistent across restarts
    "share_server_port": 8765,
    # Opt-in self-signed HTTPS for the share server.  Off by default: walk-up
    # phones get a one-time certificate warning.  Prefer WPA3 at the router for
    # on-the-wire confidentiality without that warning.
    "share_server_tls": False,
    # Idle auto-logout
    "idle_timeout_seconds": 300,
    "idle_warning_seconds": 60,
    # Auto-cleanup: delete video data for sessions inactive longer than this
    "session_cleanup_hours": 1,
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

    @property
    def _bak_path(self) -> Path:
        return self._path.with_name(self._path.name + ".bak")

    @property
    def _tmp_path(self) -> Path:
        return self._path.with_name(self._path.name + ".tmp")

    def _load(self) -> None:
        # Try the main file, then the last-good backup, before falling back to
        # defaults.  Atomic _save means the main file is never half-written,
        # but the .bak is cheap insurance against SD-card bit-rot.
        for candidate in (self._path, self._bak_path):
            if not candidate.exists():
                continue
            try:
                loaded = json.loads(candidate.read_text())
                self._data.update(loaded)
                if candidate is not self._path:
                    LOGGER.warning(
                        "settings.json unreadable — recovered config from %s",
                        candidate.name,
                    )
                return
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Could not load settings from %s: %s", candidate, exc)
        # Nothing loadable — keep the defaults already in self._data.

    def _save(self) -> None:
        # Atomic write: temp file in the same dir → flush+fsync → os.replace.
        # os.replace is atomic on the same filesystem, so a power-cut on the Pi
        # can never leave a half-written settings.json — which _load would then
        # reject, silently reverting EVERY setting to defaults (wrong screens,
        # wrong camera, and a changed share_server_port that breaks session
        # persistence).
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps(self._data, indent=2)
            with open(self._tmp_path, "w", encoding="utf-8") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            # Snapshot the current good file as .bak before swapping it out.
            if self._path.exists():
                try:
                    import shutil  # noqa: PLC0415
                    shutil.copy2(self._path, self._bak_path)
                except OSError as exc:
                    LOGGER.debug("Could not refresh settings backup: %s", exc)
            os.replace(self._tmp_path, self._path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not save settings to %s: %s", self._path, exc)
