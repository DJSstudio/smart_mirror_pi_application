"""Application path resolution."""
from __future__ import annotations

from pathlib import Path


class AppPaths:
    """All filesystem paths the application uses."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.data_dir = repo_root / "data"
        self.videos_dir = self.data_dir / "videos"
        self.thumbnails_dir = self.data_dir / "thumbnails"
        self.temp_dir = self.data_dir / "temp"
        self.logs_dir = self.data_dir / "logs"
        self.database_path = self.data_dir / "smart_mirror.db"
        self.config_path = repo_root / "config" / "settings.json"

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.videos_dir,
            self.thumbnails_dir,
            self.temp_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def discover() -> "AppPaths":
        """Locate the repository root relative to this file."""
        here = Path(__file__).resolve()
        # Go up: paths.py → config → app → repo_root
        return AppPaths(here.parent.parent.parent)
