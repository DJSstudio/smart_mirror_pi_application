from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AutostartAssets:
    service_unit: Path
    setup_script: Path


def resolve_autostart_assets(repo_root: Path) -> AutostartAssets:
    return AutostartAssets(
        service_unit=repo_root / "systemd" / "smart-mirror.service",
        setup_script=repo_root / "scripts" / "setup_autostart.sh",
    )
