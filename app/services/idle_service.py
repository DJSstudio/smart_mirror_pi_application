"""Idle-session auto-logout service.

Two-phase flow
──────────────
1. After ``timeout_ms - warning_ms`` of inactivity → warning phase begins.
   ``warningVisible`` becomes True; ``secondsLeft`` counts down every second.
2. After ``warning_ms`` more seconds with no activity → ``timedOut`` fires.
3. Any user event during either phase resets the whole cycle back to phase 1.

The warning overlay is driven entirely from QML via the ``warningVisible``
and ``secondsLeft`` properties — no separate QML timer needed.

Usage (main.py)
───────────────
    idle = IdleService(timeout_ms=5 * 60 * 1_000, warning_ms=60 * 1_000)
    idle.install(app)                       # app = QGuiApplication
    idle.timedOut.connect(login_ctrl.startLogin)

    # Pause on pages where auto-logout is undesirable:
    def _on_page_changed():
        if app_ctrl.currentPage in ("login", "recording"):
            idle.stop()
        else:
            idle.start()
    app_ctrl.currentPageChanged.connect(_on_page_changed)

    # Expose to QML so the warning overlay can bind to it:
    ctx.setContextProperty("idleService", idle)
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Property, QEvent, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

LOGGER = logging.getLogger(__name__)

# Event types that count as user activity.
_ACTIVITY_EVENTS: frozenset[QEvent.Type] = frozenset({
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.MouseMove,
    QEvent.Type.TouchBegin,
    QEvent.Type.TouchUpdate,
    QEvent.Type.KeyPress,
    QEvent.Type.Wheel,
})


class IdleService(QObject):
    """Two-phase idle timer: warn → logout.

    Parameters
    ----------
    timeout_ms:
        Total inactivity duration before logout (default: 5 minutes).
    warning_ms:
        How many milliseconds before logout the warning is shown
        (default: 60 seconds).  Must be less than ``timeout_ms``.
    """

    timedOut        = Signal()
    warningChanged  = Signal()   # warningVisible or secondsLeft changed

    def __init__(
        self,
        timeout_ms: int  = 5 * 60 * 1_000,
        warning_ms: int  = 60 * 1_000,
        parent: QObject | None = None,
    ) -> None:
        if warning_ms >= timeout_ms:
            raise ValueError("warning_ms must be less than timeout_ms")

        super().__init__(parent)

        self._warning_ms = warning_ms
        self._warn_visible = False
        self._seconds_left = 0

        # Phase-1 timer: fires when the warning phase should begin.
        self._phase1 = QTimer(self)
        self._phase1.setSingleShot(True)
        self._phase1.setInterval(timeout_ms - warning_ms)
        self._phase1.timeout.connect(self._enter_warning)

        # Phase-2 timer: fires when the session should be terminated.
        self._phase2 = QTimer(self)
        self._phase2.setSingleShot(True)
        self._phase2.setInterval(warning_ms)
        self._phase2.timeout.connect(self._on_timeout)

        # 1-second tick to update the on-screen countdown.
        self._tick = QTimer(self)
        self._tick.setInterval(1_000)
        self._tick.timeout.connect(self._on_tick)

        self._filter: _IdleEventFilter | None = None

    # ------------------------------------------------------------------
    # QML-bindable properties
    # ------------------------------------------------------------------

    @Property(bool, notify=warningChanged)
    def warningVisible(self) -> bool:  # noqa: N802
        return self._warn_visible

    @Property(int, notify=warningChanged)
    def secondsLeft(self) -> int:  # noqa: N802
        return self._seconds_left

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, app: QGuiApplication) -> None:
        """Register the application-level event filter.

        Must be called once, after ``QGuiApplication`` is constructed.
        """
        self._filter = _IdleEventFilter(self)
        app.installEventFilter(self._filter)

    def start(self) -> None:
        """Begin (or restart) the idle countdown from scratch."""
        self._stop_all()
        self._phase1.start()

    def stop(self) -> None:
        """Halt all timers and hide the warning (e.g. when on login page)."""
        self._stop_all()

    def reset(self) -> None:
        """Reset the countdown — called automatically on any user activity.

        If the warning is currently visible it is dismissed and the full
        phase-1 countdown restarts.
        """
        if not self._phase1.isActive() and not self._phase2.isActive():
            # Timer is stopped (login / recording page) — do nothing.
            return

        was_warning = self._warn_visible
        self._stop_all()
        self._phase1.start()

        if was_warning:
            LOGGER.debug("Idle warning dismissed by user activity")
            self.warningChanged.emit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _enter_warning(self) -> None:
        """Phase 1 fired → begin the 60-second warning countdown."""
        self._warn_visible = True
        self._seconds_left = self._warning_ms // 1_000
        self._phase2.start()
        self._tick.start()
        LOGGER.info(
            "Idle warning shown — logging out in %d seconds", self._seconds_left
        )
        self.warningChanged.emit()

    def _on_tick(self) -> None:
        """Decrement the on-screen countdown once per second."""
        self._seconds_left = max(0, self._seconds_left - 1)
        self.warningChanged.emit()

    def _on_timeout(self) -> None:
        """Phase 2 fired → log out."""
        self._stop_all()
        LOGGER.info("Idle timeout — triggering auto-logout")
        self.timedOut.emit()

    def _stop_all(self) -> None:
        self._phase1.stop()
        self._phase2.stop()
        self._tick.stop()
        if self._warn_visible:
            self._warn_visible = False
            self._seconds_left = 0


class _IdleEventFilter(QObject):
    """Application-level filter: resets the idle timer on any user activity.

    Installed on ``QGuiApplication`` so every event is seen before any QML
    item handles it.  Never consumes events (always returns False).
    """

    def __init__(self, idle: IdleService) -> None:
        super().__init__()
        self._idle = idle

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in _ACTIVITY_EVENTS:
            self._idle.reset()
        return False
