from __future__ import annotations

from PySide6.QtGui import QScreen


def screen_to_descriptor(screen: QScreen, index: int, primary: QScreen | None) -> dict[str, object]:
    geometry = screen.geometry()
    return {
        "index": index,
        "name": screen.name(),
        "width": geometry.width(),
        "height": geometry.height(),
        "primary": screen == primary,
        "label": (
            f"{index}: {screen.name()} "
            f"({geometry.width()}x{geometry.height()})"
            f"{' primary' if screen == primary else ''}"
        ),
    }


def screen_area(screen: QScreen) -> int:
    geometry = screen.geometry()
    return int(geometry.width() * geometry.height())
