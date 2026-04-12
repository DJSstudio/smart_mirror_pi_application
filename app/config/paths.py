from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    repo_root: Path
    state_root: Path
    config_root: Path
    logs_dir: Path
    data_dir: Path
    videos_dir: Path
    thumbnails_dir: Path
    temp_dir: Path
    database_path: Path
    default_config_path: Path
    user_config_path: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        repo_root = Path(__file__).resolve().parents[2]
        state_root = Path(
            os.environ.get(
                "SMART_MIRROR_HOME",
                Path.home() / ".local" / "share" / "smart-mirror-pi",
            )
        )
        config_root = Path(
            os.environ.get(
                "SMART_MIRROR_CONFIG_HOME",
                Path.home() / ".config" / "smart-mirror-pi",
            )
        )
        logs_dir = state_root / "logs"
        data_dir = state_root / "data"
        videos_dir = data_dir / "videos"
        thumbnails_dir = data_dir / "thumbnails"
        temp_dir = state_root / "tmp"
        database_path = data_dir / "smart_mirror.sqlite3"
        default_config_path = repo_root / "config" / "smart_mirror.json"
        user_config_path = config_root / "config.json"
        return cls(
            repo_root=repo_root,
            state_root=state_root,
            config_root=config_root,
            logs_dir=logs_dir,
            data_dir=data_dir,
            videos_dir=videos_dir,
            thumbnails_dir=thumbnails_dir,
            temp_dir=temp_dir,
            database_path=database_path,
            default_config_path=default_config_path,
            user_config_path=user_config_path,
        )

    def ensure_directories(self) -> None:
        for path in (
            self.state_root,
            self.config_root,
            self.logs_dir,
            self.data_dir,
            self.videos_dir,
            self.thumbnails_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
