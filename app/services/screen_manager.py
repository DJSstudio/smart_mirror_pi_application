from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QGuiApplication, QScreen

from app.platform.screen_utils import screen_area, screen_to_descriptor
from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class DisplayAssignment:
    control_screen: QScreen
    mirror_screen: QScreen
    screens: list[QScreen]


class ScreenManager:
    def __init__(self, app: QGuiApplication, settings: SettingsService) -> None:
        self._app = app
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._control_window = None
        self._mirror_window = None

    def bind_windows(self, control_window, mirror_window) -> None:
        self._control_window = control_window
        self._mirror_window = mirror_window

    def describe_screens(self) -> list[dict[str, object]]:
        primary = self._app.primaryScreen()
        return [
            screen_to_descriptor(screen, index, primary)
            for index, screen in enumerate(self._app.screens())
        ]

    def current_assignment(self) -> DisplayAssignment:
        screens = self._app.screens()
        if not screens:
            raise RuntimeError("No displays detected")
        control_index = self._safe_index(self._settings.get("control_screen_index"), screens)
        mirror_index = self._safe_index(self._settings.get("mirror_screen_index"), screens)

        if control_index is not None:
            control_screen = screens[control_index]
        elif mirror_index is not None:
            control_screen = self._pick_control_screen(screens, exclude=screens[mirror_index])
        else:
            control_screen = self._pick_control_screen(screens)

        if mirror_index is not None:
            mirror_screen = screens[mirror_index]
        elif control_index is not None:
            mirror_screen = self._pick_mirror_screen(screens, control_screen)
        else:
            mirror_screen = self._pick_mirror_screen(screens, control_screen)

        if len(screens) > 1 and mirror_screen == control_screen:
            mirror_screen = self._pick_mirror_screen(screens, control_screen)

        return DisplayAssignment(
            control_screen=control_screen,
            mirror_screen=mirror_screen,
            screens=screens,
        )

    def apply_assignment(self) -> DisplayAssignment:
        assignment = self.current_assignment()
        self._log_assignment(assignment)
        if self._control_window is not None:
            self._place_window(self._control_window, assignment.control_screen)
        if self._mirror_window is not None:
            self._place_window(self._mirror_window, assignment.mirror_screen)
        return assignment

    @staticmethod
    def _safe_index(raw_value, screens: list[QScreen]) -> int | None:
        try:
            index = int(raw_value)
        except (TypeError, ValueError):
            return None
        return index if 0 <= index < len(screens) else None

    @staticmethod
    def _pick_mirror_screen(screens: list[QScreen], control_screen: QScreen) -> QScreen:
        if len(screens) == 1:
            return screens[0]
        candidates = [screen for screen in screens if screen != control_screen]
        candidates.sort(key=screen_area, reverse=True)
        return candidates[0]

    @staticmethod
    def _pick_control_screen(
        screens: list[QScreen],
        exclude: QScreen | None = None,
    ) -> QScreen:
        if len(screens) == 1:
            return screens[0]
        candidates = [screen for screen in screens if screen != exclude] if exclude else list(screens)
        candidates.sort(key=screen_area)
        return candidates[0]

    def _log_assignment(self, assignment: DisplayAssignment) -> None:
        descriptors = self.describe_screens()
        self._logger.info("Detected screens: %s", descriptors)
        self._logger.info(
            "Using control=%s mirror=%s",
            assignment.control_screen.name(),
            assignment.mirror_screen.name(),
        )

    @staticmethod
    def _place_window(window, screen: QScreen) -> None:
        geometry = screen.geometry()
        if hasattr(window, "setScreen"):
            window.setScreen(screen)
        if hasattr(window, "setPosition"):
            window.setPosition(QPoint(geometry.x(), geometry.y()))
        if hasattr(window, "setX"):
            window.setX(geometry.x())
        if hasattr(window, "setY"):
            window.setY(geometry.y())
        if hasattr(window, "resize"):
            window.resize(QSize(geometry.width(), geometry.height()))
        if hasattr(window, "showFullScreen"):
            window.showFullScreen()
