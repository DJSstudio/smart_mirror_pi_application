"""Screen detection and window placement."""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication, QScreen

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
            _place_fullscreen(self._control_window, control_screen)

        if self._mirror_window is not None:
            _place_fullscreen(self._mirror_window, mirror_screen)

        # Map touchscreen input to the control screen so touch events don't
        # land on the mirror display.
        if not single:
            _map_touch_to_screen(control_screen.name())

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


def _place_fullscreen(window, screen) -> None:
    """Place a Qt window fullscreen on the given screen.

    Sequence that works on both X11 and Wayland:
      1. setScreen()      — tell Qt (and the Wayland compositor) which output to
                            use.  Must be called before the window is shown.
      2. showNormal()     — ensure the window is not in a conflicting state
                            (e.g. previously minimised or maximised).
      3. setGeometry()    — move to the screen's coordinate rect.  On X11 this
                            is the primary mechanism; on Wayland compositors that
                            honour xdg-output coordinates it also works.
      4. showFullScreen() — request fullscreen; compositor uses the output
                            that was set in steps 1–3.

    IMPORTANT: do NOT add Qt.WindowStaysOnBottomHint to the window's flags.
    On X11 and many Wayland compositors that hint sets a sub-normal window
    level which silently prevents showFullScreen() from succeeding, leaving
    the window as a centred floating rectangle.
    """
    geom = screen.geometry()
    window.setScreen(screen)
    window.showNormal()
    window.setGeometry(geom.x(), geom.y(), geom.width(), geom.height())
    window.showFullScreen()


def _map_touch_to_screen(screen_name: str) -> None:
    """Use xinput to restrict all touch/pointer input devices to the control screen.

    On Raspberry Pi with two HDMI displays the touchscreen defaults to the
    combined virtual desktop, so touch events that physically land on the mirror
    display (the wrong screen) also fire inside the control window's coordinate
    space.  Mapping the device to the control output fixes the coordinate offset
    and ensures the mirror display ignores touch entirely.

    Silently skips if xinput is not installed or no touch device is found.
    """
    if not shutil.which("xinput"):
        LOGGER.debug("xinput not found — skipping touch mapping")
        return
    try:
        result = subprocess.run(
            ["xinput", "list", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        for raw_name in result.stdout.splitlines():
            name = raw_name.strip()
            if not name:
                continue
            lower = name.lower()
            if any(k in lower for k in ("touch", "wacom", "pen", "digitizer", "stylus")):
                subprocess.run(
                    ["xinput", "--map-to-output", name, screen_name],
                    capture_output=True, timeout=5,
                )
                LOGGER.info("Mapped touch device %r → %s", name, screen_name)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Touch mapping skipped: %s", exc)
