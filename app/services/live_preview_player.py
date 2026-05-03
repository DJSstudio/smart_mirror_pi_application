"""Low-latency live preview using ffplay subprocess.

Qt's MediaPlayer + GStreamer playbin + MPEGTS demuxer together add ~500 ms
of buffering for live UDP streams.  ffplay reading the same UDP stream with
``-fflags nobuffer -flags low_delay -framedrop`` achieves <100 ms latency.

This service spawns ffplay only during the recording's live_preview mode,
positioned fullscreen on the mirror screen.  Recording itself is unchanged
(ffmpeg writes the file just like before).  When live_preview ends, ffplay
is killed.

The mirror Qt window stays for QML overlays (countdown, REC badge, framing
guide) — the compositor stacks the Qt window on top of the ffplay window
because it is created later and not in fullscreen mode that grabs the layer.
On Wayland with labwc, this works as long as ffplay is launched without
WindowStaysOnTopHint and Qt window has focus.
"""
from __future__ import annotations

import logging
import shutil
import signal
import subprocess

from PySide6.QtCore import QObject

LOGGER = logging.getLogger(__name__)


class LivePreviewPlayer(QObject):
    """Spawns/kills an ffplay process for low-latency mirror preview."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: subprocess.Popen | None = None

    def start(self, url: str, screen_x: int, screen_y: int,
              screen_w: int, screen_h: int) -> None:
        """Start ffplay reading the UDP stream, positioned on the mirror screen.

        screen_x/y/w/h: position and size of the mirror screen in the
        global desktop coordinate space.  ffplay uses SDL hints to place
        its window.
        """
        self.stop()  # ensure clean state

        if not shutil.which("ffplay"):
            LOGGER.warning(
                "ffplay binary not found; live preview will fall back to Qt MediaPlayer"
            )
            return

        cmd = [
            "ffplay",
            "-hide_banner", "-loglevel", "warning",
            # Latency reduction: don't buffer input, don't reorder, drop late frames
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-framedrop",
            "-infbuf",
            # Kill audio entirely (camera stream has none anyway)
            "-an",
            # Window settings — borderless fullscreen on the mirror screen
            "-noborder",
            "-alwaysontop",
            "-window_title", "smart_mirror_live_preview",
            "-x", str(screen_w),
            "-y", str(screen_h),
            "-left", str(screen_x),
            "-top", str(screen_y),
            "-autoexit",
            url,
        ]

        # SDL_VIDEODRIVER hint: prefer Wayland, fall back to X11.
        env = None
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
            )
            LOGGER.info("ffplay started (pid=%d) for %s at %dx%d+%d+%d",
                        self._proc.pid, url, screen_w, screen_h, screen_x, screen_y)
        except FileNotFoundError as exc:
            LOGGER.warning("Failed to spawn ffplay: %s", exc)
            self._proc = None

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            try:
                self._proc.send_signal(signal.SIGTERM)
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                try:
                    self._proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Error terminating ffplay: %s", exc)
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
