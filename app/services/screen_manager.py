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
    """Map touch input to the control screen.

    Handles all three Qt platform backends:

    X11 (xcb)
        Uses ``xinput --map-to-output`` to remap every slave pointer device
        to the control screen's RandR output.  The touchscreen's coordinate
        space is rescaled to that output, so taps always land in the right
        window regardless of where the screen sits in the virtual desktop.

    eglfs (Pi framebuffer, no display server)
        No runtime mapping needed — the Qt evdev plugin reads the touch
        device set in ``QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS``, which
        run_dev.sh pre-configures from ``/sys/class/input``.

    Wayland
        The Wayland compositor routes touch to whichever surface owns the
        physical output.  On correctly configured systems this is automatic.
        If touch is still wrong, the compositor needs to be told which output
        the touchscreen belongs to — see the WARNING log below for the fix.
    """
    import os  # noqa: PLC0415

    platform = os.environ.get("QT_QPA_PLATFORM", "")

    # ── eglfs: no runtime mapping needed ─────────────────────────────────
    if platform == "eglfs":
        LOGGER.debug("Touch mapping: eglfs — device set via QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS")
        return

    # ── Wayland ───────────────────────────────────────────────────────────
    wayland = (
        platform == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )
    if wayland:
        _map_touch_wayland(screen_name)
        return

    # ── X11 (xcb): use xinput ─────────────────────────────────────────────
    if not shutil.which("xinput"):
        LOGGER.debug("Touch mapping: xinput not found (X11 only)")
        return

    try:
        result = subprocess.run(
            ["xinput", "list", "--short"],
            capture_output=True, text=True, timeout=5,
        )

        # Collect candidate output names: Qt screen name + actual xrandr names.
        output_names = [screen_name]
        if shutil.which("xrandr"):
            try:
                xr = subprocess.run(
                    ["xrandr", "--listmonitors"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in xr.stdout.splitlines():
                    # Lines look like: " 0: +*HDMI-1 1920/527x1080/296+0+0  HDMI-1"
                    parts = line.strip().split()
                    if parts and "+" in parts[0]:
                        name = parts[-1].strip()
                        if name and name not in output_names:
                            output_names.append(name)
            except Exception:  # noqa: BLE001
                pass

        mapped = 0
        for line in result.stdout.splitlines():
            if "slave  pointer" not in line:
                continue
            try:
                dev_id = line.split("id=")[1].split()[0].strip()
                int(dev_id)
            except (IndexError, ValueError):
                continue

            dev_name = line.split("↳")[-1].split("id=")[0].strip()
            for out in output_names:
                r = subprocess.run(
                    ["xinput", "--map-to-output", dev_id, out],
                    capture_output=True, timeout=5,
                )
                if r.returncode == 0:
                    LOGGER.info("Touch: mapped %r (id=%s) → %s", dev_name, dev_id, out)
                    mapped += 1
                    break
            else:
                LOGGER.debug("Touch: could not map %r to any output %s", dev_name, output_names)

        if mapped == 0:
            LOGGER.warning(
                "Touch: no pointer devices mapped. "
                "Run 'xinput list --short' on the Pi to check available devices."
            )
        else:
            LOGGER.info("Touch: mapped %d device(s) → control screen", mapped)

    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Touch mapping error: %s", exc)


def _map_touch_wayland(screen_name: str) -> None:
    """Attempt touch-to-output mapping on Wayland.

    wlroots-based compositors (Wayfire, labwc) route touch based on which
    output the touch device is associated with.  We write a libinput device
    quirk file that sets the ``OutputName`` hint — the compositor picks this
    up on next launch.

    If the quirk file cannot be written we log the manual steps instead.
    """
    import re  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    # Find touch devices via libinput (if available)
    touch_devices: list[str] = []
    if shutil.which("libinput"):
        try:
            r = subprocess.run(
                ["libinput", "list-devices"],
                capture_output=True, text=True, timeout=10,
            )
            current_device = ""
            for line in r.stdout.splitlines():
                if line.startswith("Device:"):
                    current_device = line.split(":", 1)[1].strip()
                elif "Capabilities:" in line and "touch" in line.lower() and current_device:
                    touch_devices.append(current_device)
                    current_device = ""
        except Exception:  # noqa: BLE001
            pass

    if not touch_devices:
        LOGGER.warning(
            "Touch mapping (Wayland): could not detect touch device. "
            "To fix touch alignment, add to ~/.config/wayfire.ini:\n"
            "  [input]\n"
            "  touch_from_output = %s",
            screen_name,
        )
        return

    # Write ~/.local/share/libinput/local-overrides.quirks
    # libinput picks this up without requiring root.
    quirk_dir = Path.home() / ".local" / "share" / "libinput"
    quirk_file = quirk_dir / "local-overrides.quirks"
    try:
        quirk_dir.mkdir(parents=True, exist_ok=True)
        existing = quirk_file.read_text() if quirk_file.exists() else ""

        # Build entries for each touch device
        new_entries: list[str] = []
        for dev_name in touch_devices:
            safe_name = re.escape(dev_name)
            entry = (
                f"[Touch output mapping for {dev_name}]\n"
                f"MatchName={dev_name}\n"
                f"AttrOutputMappingHint={screen_name}\n"
            )
            if dev_name not in existing:
                new_entries.append(entry)

        if new_entries:
            with quirk_file.open("a") as fh:
                fh.write("\n" + "\n".join(new_entries))
            LOGGER.info(
                "Touch (Wayland): wrote libinput quirks for %d device(s) → %s. "
                "Restart the compositor or reboot to apply.",
                len(new_entries), screen_name,
            )
        else:
            LOGGER.debug("Touch (Wayland): libinput quirks already present")

    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Touch (Wayland): could not write libinput quirks (%s). "
            "Manual fix — add to ~/.config/wayfire.ini:\n"
            "  [input]\n"
            "  touch_from_output = %s",
            exc, screen_name,
        )
