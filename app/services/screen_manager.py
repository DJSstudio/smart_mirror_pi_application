"""Screen detection and window placement."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication

from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScreenAssignment:
    control_screen: QScreen
    mirror_screen: QScreen
    single_screen_mode: bool


class ScreenManager:
    """Detects connected screens and assigns windows to them.

    Rules:
    • If two or more screens are present, screen index 0 → control,
      screen index 1 → mirror (overrideable via settings).
    • If only one screen is present, both windows share it
      (single_screen_mode = True).  The mirror window is placed in the
      bottom half of the screen so the control window remains usable.
    """

    def __init__(self, app: QGuiApplication, settings: SettingsService) -> None:
        self._app = app
        self._settings = settings
        self._control_window = None
        self._mirror_window = None

    def bind_windows(self, control_window, mirror_window) -> None:
        self._control_window = control_window
        self._mirror_window = mirror_window

    def apply_assignment(self) -> ScreenAssignment:
        screens = self._app.screens()
        if not screens:
            raise RuntimeError("No screens detected.")

        control_idx = int(self._settings.get("control_screen_index", 0))
        mirror_idx = int(self._settings.get("mirror_screen_index", 1))

        single = len(screens) == 1
        if single:
            control_screen = screens[0]
            mirror_screen = screens[0]
        else:
            control_screen = screens[min(control_idx, len(screens) - 1)]
            mirror_screen = screens[min(mirror_idx, len(screens) - 1)]

        LOGGER.info(
            "Screen assignment — control: %s  mirror: %s  single=%s",
            control_screen.name(), mirror_screen.name(), single,
        )

        if self._control_window is not None:
            ctrl_geom = control_screen.geometry()
            self._control_window.setGeometry(
                ctrl_geom.x(), ctrl_geom.y(),
                ctrl_geom.width(), ctrl_geom.height(),
            )
            self._control_window.setScreen(control_screen)
            self._control_window.showFullScreen()

        if self._mirror_window is not None:
            mir_geom = mirror_screen.geometry()
            if single:
                # In single-screen mode place mirror behind the control window
                # (it stays black — the user won't normally see it)
                self._mirror_window.setGeometry(
                    mir_geom.x(), mir_geom.y(),
                    mir_geom.width(), mir_geom.height(),
                )
            else:
                self._mirror_window.setGeometry(
                    mir_geom.x(), mir_geom.y(),
                    mir_geom.width(), mir_geom.height(),
                )
            self._mirror_window.setScreen(mirror_screen)
            self._mirror_window.showFullScreen()

        return ScreenAssignment(
            control_screen=control_screen,
            mirror_screen=mirror_screen,
            single_screen_mode=single,
        )

    def available_screens(self) -> list[dict[str, object]]:
        screens = self._app.screens()
        primary = self._app.primaryScreen()
        result = []
        for i, screen in enumerate(screens):
            geom = screen.geometry()
            result.append({
                "index": i,
                "name": screen.name(),
                "width": geom.width(),
                "height": geom.height(),
                "isPrimary": screen == primary,
                "label": f"Screen {i}: {screen.name()} ({geom.width()}×{geom.height()})",
            })
        return result
