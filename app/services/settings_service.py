from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.config.paths import AppPaths


class SettingsService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths
        self._defaults = self._load_json(paths.default_config_path)
        self._overrides = self._load_json(paths.user_config_path)
        self._settings = _merge_dicts(deepcopy(self._defaults), self._overrides)

    def reload(self) -> None:
        self._overrides = self._load_json(self._paths.user_config_path)
        self._settings = _merge_dicts(deepcopy(self._defaults), self._overrides)

    @property
    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._settings)

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._overrides[key] = value
        self._settings[key] = value
        self.save()

    def update(self, values: dict[str, Any]) -> None:
        self._overrides.update(values)
        self._settings.update(values)
        self.save()

    def save(self) -> None:
        self._paths.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        self._paths.user_config_path.write_text(
            json.dumps(self._overrides, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))


def _merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_dicts(dict(base[key]), value)
        else:
            base[key] = value
    return base
