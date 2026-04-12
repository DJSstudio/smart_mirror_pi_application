from __future__ import annotations

import logging
from pathlib import Path

from app.config.paths import AppPaths


def configure_logging(paths: AppPaths, level_name: str = "INFO") -> Path:
    level = getattr(logging, level_name.upper(), logging.INFO)
    log_path = paths.logs_dir / "smart_mirror.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("PySide6").setLevel(logging.WARNING)
    return log_path
