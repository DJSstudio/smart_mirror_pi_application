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

        single = len(screens) == 1
        if single:
            control_screen = screens[0]
            mirror_screen = screens[0]
        else:
            auto_detect = bool(self._settings.get("screen_auto_detect", True))
            if auto_detect:
                control_screen, mirror_screen = _auto_assign(screens)
                LOGGER.info(
                    "Screen assignment (auto) — control: %s (%dx%d)  mirror: %s (%dx%d)",
                    control_screen.name(),
                    control_screen.geometry().width(), control_screen.geometry().height(),
                    mirror_screen.name(),
                    mirror_screen.geometry().width(), mirror_screen.geometry().height(),
                )
            else:
                control_idx = int(self._settings.get("control_screen_index", 0))
                mirror_idx = int(self._settings.get("mirror_screen_index", 1))
                control_screen = screens[min(control_idx, len(screens) - 1)]
                mirror_screen = screens[min(mirror_idx, len(screens) - 1)]
                LOGGER.info(
                    "Screen assignment (manual) — control: %s  mirror: %s",
                    control_screen.name(), mirror_screen.name(),
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
            phys = screen.physicalSize()
            phys_str = (
                f"  {phys.width():.0f}×{phys.height():.0f} mm"
                if phys.width() > 0 else ""
            )
            result.append({
                "index": i,
                "name": screen.name(),
                "width": geom.width(),
                "height": geom.height(),
                "isPrimary": screen == primary,
                "label": f"Screen {i}: {screen.name()} ({geom.width()}×{geom.height()}{phys_str})",
            })
        return result

    def get_auto_assignment(self) -> dict[str, object]:
        """Return what auto-detection would assign, for display in Settings."""
        screens = self._app.screens()
        if len(screens) < 2:
            return {"controlName": "", "mirrorName": "", "available": False}
        ctrl, mirror = _auto_assign(screens)
        cg, mg = ctrl.geometry(), mirror.geometry()
        return {
            "available": True,
            "controlName": ctrl.name(),
            "controlRes": f"{cg.width()}×{cg.height()}",
            "mirrorName": mirror.name(),
            "mirrorRes": f"{mg.width()}×{mg.height()}",
        }


def _auto_assign(screens) -> tuple:
    """Return (control_screen, mirror_screen) by sorting on pixel area.

    The smallest screen is assigned to the control window (typically the Pi's
    7" DSI/HDMI touchscreen at 800×480) and the largest to the mirror display
    (typically a 1080p or 4K TV).  If all screens have the same resolution the
    first screen in Qt's list is used as control.
    """
    sorted_screens = sorted(
        screens,
        key=lambda s: s.geometry().width() * s.geometry().height(),
    )
    return sorted_screens[0], sorted_screens[-1]


def _place_fullscreen(window, screen) -> None:
    """Place a Qt window fullscreen on the given screen.

    Sequence that works on both X11 and Wayland:
      1. setScreen()      — tell Qt (and the Wayland compositor) which output to
                            use.  Must be called before the window is shown.
      2. showNormal()     — ensure the window is not in a conflicting state
                            (e.g. previously minimised or maximised).
                            ONLY called on the first show (window not yet visible).
                            Calling it again after showFullScreen() races with the
                            compositor and can leave the window stuck as a small
                            floating rectangle — the root cause of the intermittent
                            "partial mirror" bug.
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
    if not window.isVisible():
        # First call: reset any conflicting window state before going fullscreen.
        # On subsequent calls we deliberately skip showNormal() — calling it after
        # showFullScreen() has already been requested races with the compositor and
        # can revert the window to windowed mode intermittently.
        window.showNormal()
    window.setGeometry(geom.x(), geom.y(), geom.width(), geom.height())
    window.showFullScreen()


def _map_touch_to_screen(screen_name: str) -> None:
    """Map all pointer input devices to the control screen (X11 only).

    On a dual-display X11 setup the touchscreen covers the full virtual
    desktop, so taps can land in the wrong window's coordinate space.
    Mapping every slave pointer device to the control screen output fixes
    the coordinate offset without needing to identify device names.

    On Wayland the compositor routes touch to whichever surface owns the
    output, so no manual mapping is required.
    """
    import os  # noqa: PLC0415

    # Wayland: compositor handles input routing automatically — nothing to do.
    wayland = bool(os.environ.get("WAYLAND_DISPLAY") or
                   os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland")
    if wayland:
        LOGGER.debug("Touch mapping: Wayland detected — compositor handles routing")
        return

    if not shutil.which("xinput"):
        LOGGER.debug("xinput not found — skipping touch mapping")
        return

    try:
        # List all devices in short format; slave pointer lines contain
        # "slave  pointer" — these are all physical input devices that can
        # produce pointer/touch events (mice, touchscreens, trackpads, etc.).
        result = subprocess.run(
            ["xinput", "list", "--short"],
            capture_output=True, text=True, timeout=5,
        )

        mapped = 0
        for line in result.stdout.splitlines():
            if "slave  pointer" not in line:
                continue
            # Extract device id from "... id=N ..."
            try:
                dev_id = line.split("id=")[1].split()[0].strip()
                int(dev_id)  # validate it's a number
            except (IndexError, ValueError):
                continue

            r = subprocess.run(
                ["xinput", "--map-to-output", dev_id, screen_name],
                capture_output=True, timeout=5,
            )
            dev_name = line.split("↳")[-1].split("id=")[0].strip()
            if r.returncode == 0:
                LOGGER.info("Touch: mapped %r (id=%s) → %s", dev_name, dev_id, screen_name)
                mapped += 1
            else:
                LOGGER.debug("Touch: skipped %r (id=%s): %s", dev_name, dev_id, r.stderr.strip())

        if mapped == 0:
            LOGGER.warning("Touch: no slave pointer devices found to map")
        else:
            LOGGER.info("Touch: mapped %d pointer device(s) → %s", mapped, screen_name)

    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Touch mapping skipped: %s", exc)
