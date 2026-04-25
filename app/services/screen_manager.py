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
    """Map touch to the control output on Wayland — no reboot required.

    Two-stage approach:

    1. **Runtime** — try ``wf-msg`` (Wayfire IPC) to apply the mapping to the
       *running* compositor immediately.  If it succeeds, touch is fixed right
       now without any restart.

    2. **Persistent** — write ``[input-device:<name>]`` sections to
       ``~/.config/wayfire.ini`` so the mapping survives compositor restarts
       automatically.  This is a one-time write; future app launches skip it.
    """
    from pathlib import Path  # noqa: PLC0415

    touch_names = _find_touch_device_names()
    if not touch_names:
        LOGGER.warning(
            "Touch (Wayland): no touch device found in /sys/class/input. "
            "Run 'libinput list-devices' to find the device name, then add:\n"
            "  [input-device:<device-name>]\n"
            "  output = %s\n"
            "to ~/.config/wayfire.ini",
            screen_name,
        )
        return

    # ── Stage 1: runtime via wf-msg (no reboot) ──────────────────────────
    runtime_ok = _wfmsg_map_touch(touch_names, screen_name)

    # ── Stage 2: persist to wayfire.ini ──────────────────────────────────
    wayfire_ini = Path.home() / ".config" / "wayfire.ini"
    if not wayfire_ini.exists():
        if not runtime_ok:
            LOGGER.warning(
                "Touch (Wayland): ~/.config/wayfire.ini not found and wf-msg "
                "unavailable. Create the file and add:\n"
                "  [input-device:%s]\n  output = %s",
                touch_names[0], screen_name,
            )
        return

    try:
        content = wayfire_ini.read_text()
        new_sections: list[str] = []
        for name in touch_names:
            if f"[input-device:{name}]" not in content:
                new_sections.append(f"\n[input-device:{name}]\noutput = {screen_name}\n")

        if new_sections:
            with wayfire_ini.open("a") as fh:
                fh.write("".join(new_sections))
            LOGGER.info(
                "Touch (Wayland): persisted %d device section(s) to wayfire.ini → %s",
                len(new_sections), screen_name,
            )
        else:
            LOGGER.debug("Touch (Wayland): wayfire.ini already has device sections")

    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Touch (Wayland): could not update wayfire.ini: %s", exc)


def _wfmsg_map_touch(touch_names: list[str], screen_name: str) -> bool:
    """Apply touch-to-output mapping at runtime via Wayfire IPC (wf-msg).

    Returns True if at least one device was successfully mapped.
    Falls back to the JSON socket if the ``wf-msg`` CLI is unavailable.
    """
    import json    # noqa: PLC0415
    import os      # noqa: PLC0415
    import socket  # noqa: PLC0415
    import struct  # noqa: PLC0415

    mapped = 0

    LOGGER.info(
        "Touch (Wayland): attempting runtime map of %s → %s",
        touch_names, screen_name,
    )

    # ── Try wf-msg CLI first (simpler) ───────────────────────────────────
    wf_msg = shutil.which("wf-msg")
    if wf_msg:
        LOGGER.debug("Touch: wf-msg found at %s", wf_msg)
        for name in touch_names:
            try:
                r = subprocess.run(
                    ["wf-msg", "input-device", name, "output", screen_name],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    LOGGER.info(
                        "Touch (Wayland): runtime mapped %r → %s via wf-msg",
                        name, screen_name,
                    )
                    mapped += 1
                else:
                    LOGGER.warning(
                        "Touch (Wayland): wf-msg failed for %r (rc=%d): %s",
                        name, r.returncode, r.stderr.strip(),
                    )
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Touch: wf-msg exception for %r: %s", name, exc)
        if mapped:
            return True
    else:
        LOGGER.debug("Touch: wf-msg not in PATH")

    # ── Try Wayfire JSON socket directly ─────────────────────────────────
    socket_path = _find_wayfire_socket()
    if not socket_path:
        LOGGER.debug("Touch (Wayland): Wayfire socket not found — wf-msg unavailable")
        return False

    for name in touch_names:
        try:
            msg = json.dumps({
                "method": "input/configure-device",
                "data": {"device": name, "output": screen_name},
            }).encode()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect(socket_path)
                s.sendall(struct.pack("<I", len(msg)) + msg)
                hdr = s.recv(4)
                if len(hdr) == 4:
                    length = struct.unpack("<I", hdr)[0]
                    resp = json.loads(s.recv(length))
                    if resp.get("result") == "ok":
                        LOGGER.info(
                            "Touch (Wayland): runtime mapped %r → %s via IPC socket",
                            name, screen_name,
                        )
                        mapped += 1
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Touch (Wayland): IPC socket attempt failed: %s", exc)

    return mapped > 0


def _find_wayfire_socket() -> str:
    """Locate the Wayfire IPC socket path.

    Checks in order:
      1. ``$WAYFIRE_SOCKET`` environment variable
      2. Glob ``$XDG_RUNTIME_DIR/wayfire-*.socket``
      3. Glob ``/run/user/<uid>/wayfire-*.socket``

    Returns the first existing path, or ``""`` if none found.
    """
    import glob  # noqa: PLC0415
    import os    # noqa: PLC0415

    explicit = os.environ.get("WAYFIRE_SOCKET", "")
    if explicit and os.path.exists(explicit):
        return explicit

    # Scan runtime dir for any wayfire socket
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    for path in sorted(glob.glob(f"{runtime_dir}/wayfire*.socket")):
        if os.path.exists(path):
            LOGGER.debug("Touch: found Wayfire socket at %s", path)
            return path

    return ""


def _find_touch_device_names() -> list[str]:
    """Return input device names that look like touchscreens.

    Two sources are tried in order:

    1. ``libinput list-devices`` — returns the *libinput* device name, which is
       what Wayfire and other wlroots compositors use internally.  This is the
       most reliable source because the name matches exactly what the compositor
       expects in IPC calls and ``wayfire.ini`` sections.

    2. ``/sys/class/input/event*/device/name`` — the *kernel* event device name.
       Usually identical to the libinput name but can differ on some setups
       (e.g. "Goodix Capacitive TouchScreen" vs "Goodix-TS").

    De-duplicated; libinput names appear first.
    """
    from pathlib import Path  # noqa: PLC0415

    _TOUCH_KEYWORDS = ("touch", "goodix", "ft5", "eeti", "ilitek", "waveshare")
    names: list[str] = []

    def _add(name: str) -> None:
        if name and name not in names:
            names.append(name)

    # ── Source 1: libinput (preferred — matches compositor's view) ────────
    if shutil.which("libinput"):
        try:
            result = subprocess.run(
                ["libinput", "list-devices"],
                capture_output=True, text=True, timeout=5,
            )
            current_name = ""
            is_touch = False
            for line in result.stdout.splitlines():
                if line.startswith("Device:"):
                    # Flush previous device
                    if is_touch and current_name:
                        _add(current_name)
                    current_name = line.split("Device:", 1)[1].strip()
                    is_touch = False
                elif "Capabilities" in line and "touch" in line.lower():
                    is_touch = True
                elif any(k in line.lower() for k in _TOUCH_KEYWORDS):
                    # Catch keyword in any field (Kernel:, Udev:, etc.)
                    pass
            # Flush last device
            if is_touch and current_name:
                _add(current_name)
            if names:
                LOGGER.debug("Touch: libinput devices found: %s", names)
        except Exception:  # noqa: BLE001
            pass

    # ── Source 2: kernel sysfs (fallback) ─────────────────────────────────
    try:
        for name_file in Path("/sys/class/input").glob("event*/device/name"):
            name = name_file.read_text().strip()
            if any(k in name.lower() for k in _TOUCH_KEYWORDS):
                _add(name)
    except Exception:  # noqa: BLE001
        pass

    if not names:
        LOGGER.debug("Touch: no touch devices found via libinput or sysfs")

    return names
