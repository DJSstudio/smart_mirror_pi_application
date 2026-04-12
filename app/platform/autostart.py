"""systemd autostart integration helpers."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)
_SERVICE_NAME = "smart-mirror"


def install_systemd_service(repo_root: Path, user: str) -> bool:
    """Install and enable the systemd user service for autostart."""
    src = repo_root / "systemd" / f"{_SERVICE_NAME}.service"
    if not src.exists():
        LOGGER.error("Service unit not found: %s", src)
        return False

    dst_dir = Path.home() / ".config" / "systemd" / "user"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name

    shutil.copy2(src, dst)
    LOGGER.info("Installed service unit to %s", dst)

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", f"{_SERVICE_NAME}.service"], check=True)
        LOGGER.info("Service enabled and started")
        return True
    except subprocess.CalledProcessError as exc:
        LOGGER.error("Failed to enable service: %s", exc)
        return False


def service_status() -> str:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", f"{_SERVICE_NAME}.service"],
            capture_output=True, text=True,
        )
        return result.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"
