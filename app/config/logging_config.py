"""Logging setup."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def configure_logging(paths, level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_file = paths.logs_dir / "smart_mirror.log"

    root = logging.getLogger()
    root.setLevel(numeric_level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(numeric_level)
    console.setFormatter(fmt)
    root.addHandler(console)

    try:
        rotating = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=3
        )
        rotating.setLevel(numeric_level)
        rotating.setFormatter(fmt)
        root.addHandler(rotating)
    except OSError:
        pass

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
