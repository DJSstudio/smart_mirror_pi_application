"""Screen descriptor utilities."""
from __future__ import annotations

from PySide6.QtGui import QScreen


def screen_to_descriptor(screen: QScreen, index: int, primary: QScreen | None) -> dict[str, object]:
    geom = screen.geometry()
    return {
        "index": index,
        "name": screen.name(),
        "width": geom.width(),
        "height": geom.height(),
        "isPrimary": screen is primary,
        "label": (
            f"Screen {index}: {screen.name()} "
            f"({geom.width()}×{geom.height()})"
            f"{' [primary]' if screen is primary else ''}"
        ),
    }


def screen_area(screen: QScreen) -> int:
    geom = screen.geometry()
    return geom.width() * geom.height()
