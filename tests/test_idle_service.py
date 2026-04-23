"""Unit tests for IdleService — two-phase idle timer.

Uses a lightweight mock of PySide6 Qt classes so the tests run in any
environment (CI, Mac dev) without a display or a full Qt installation.
The mock covers exactly the QObject / QTimer / Signal surface that
IdleService relies on.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Minimal PySide6 stub — installed before importing IdleService
# ---------------------------------------------------------------------------

class _Signal:
    """Per-instance signal with connect() / emit() semantics."""
    def __init__(self, *_types):
        self._slots: list = []

    # Called on the *class* when used as a descriptor — return a per-instance copy
    def __set_name__(self, owner, name):
        self._attr = f"_sig_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if not hasattr(obj, self._attr):
            sig = _Signal()
            sig._slots = []
            object.__setattr__(obj, self._attr, sig)
        return object.__getattribute__(obj, self._attr)

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _QTimer:
    """Synchronous stand-in for QTimer (no event loop required)."""
    def __init__(self, parent=None):
        self.timeout = _Signal()
        self._interval = 0
        self._single  = False
        self._active  = False

    def setSingleShot(self, v: bool) -> None:  # noqa: N802
        self._single = v

    def setInterval(self, ms: int) -> None:  # noqa: N802
        self._interval = ms

    def isActive(self) -> bool:  # noqa: N802
        return self._active

    def start(self) -> None:
        self._active = True

    def stop(self) -> None:
        self._active = False

    def fire(self) -> None:
        """Test helper: simulate timer expiry."""
        self._active = False
        self.timeout.emit()


class _QObject:
    def __init__(self, parent=None):
        pass


def _Property(*args, **kwargs):
    """Stub for @Property decorator — behaves like @property in tests."""
    def decorator(fn):
        return property(fn)
    return decorator


# Build fake PySide6 package tree
_pyside6_pkg = types.ModuleType("PySide6")
_qt_core     = types.ModuleType("PySide6.QtCore")
_qt_gui      = types.ModuleType("PySide6.QtGui")

_qt_core.QObject  = _QObject
_qt_core.QTimer   = _QTimer
_qt_core.Signal   = _Signal
_qt_core.Property = _Property
_qt_core.QEvent   = MagicMock()

_qt_gui.QGuiApplication = MagicMock()

sys.modules.setdefault("PySide6",        _pyside6_pkg)
sys.modules.setdefault("PySide6.QtCore", _qt_core)
sys.modules.setdefault("PySide6.QtGui",  _qt_gui)

# Now safe to import — all PySide6 references resolve to the stubs above
from app.services.idle_service import IdleService  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def idle() -> IdleService:
    """IdleService with short durations for fast testing (10s total, 3s warning)."""
    return IdleService(timeout_ms=10_000, warning_ms=3_000)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_warning_ms_equal_to_timeout_raises(self) -> None:
        with pytest.raises(ValueError):
            IdleService(timeout_ms=5_000, warning_ms=5_000)

    def test_warning_ms_greater_than_timeout_raises(self) -> None:
        with pytest.raises(ValueError):
            IdleService(timeout_ms=5_000, warning_ms=6_000)

    def test_initial_state_is_inactive(self, idle: IdleService) -> None:
        assert idle.warningVisible is False
        assert idle.secondsLeft == 0
        assert not idle._phase1.isActive()
        assert not idle._phase2.isActive()


# ---------------------------------------------------------------------------
# Start / stop
# ---------------------------------------------------------------------------

class TestStartStop:
    def test_start_activates_phase1_only(self, idle: IdleService) -> None:
        idle.start()
        assert idle._phase1.isActive()
        assert not idle._phase2.isActive()
        assert not idle._tick.isActive()

    def test_stop_halts_all_timers(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        idle.stop()
        assert not idle._phase1.isActive()
        assert not idle._phase2.isActive()
        assert not idle._tick.isActive()

    def test_stop_clears_warning_state(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        idle.stop()
        assert idle.warningVisible is False
        assert idle.secondsLeft == 0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_when_stopped_does_nothing(self, idle: IdleService) -> None:
        """reset() on a stopped timer (login / recording page) must be a no-op."""
        idle.reset()
        assert not idle._phase1.isActive()

    def test_reset_while_running_restarts_phase1(self, idle: IdleService) -> None:
        idle.start()
        idle.reset()
        assert idle._phase1.isActive()
        assert not idle._phase2.isActive()

    def test_reset_during_warning_clears_warning_and_restarts_phase1(
        self, idle: IdleService
    ) -> None:
        idle.start()
        idle._enter_warning()
        assert idle.warningVisible is True

        idle.reset()

        assert idle.warningVisible is False
        assert idle._phase1.isActive()
        assert not idle._phase2.isActive()


# ---------------------------------------------------------------------------
# Warning phase
# ---------------------------------------------------------------------------

class TestWarningPhase:
    def test_enter_warning_sets_visible_and_seconds(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        assert idle.warningVisible is True
        assert idle.secondsLeft == 3   # warning_ms=3_000 → 3 seconds

    def test_enter_warning_starts_phase2_and_tick(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        assert idle._phase2.isActive()
        assert idle._tick.isActive()

    def test_tick_decrements_seconds_left(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        idle._on_tick()
        assert idle.secondsLeft == 2

    def test_tick_does_not_go_below_zero(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        for _ in range(10):
            idle._on_tick()
        assert idle.secondsLeft == 0

    def test_warning_emits_signal_on_enter(self, idle: IdleService) -> None:
        events: list = []
        idle.warningChanged.connect(lambda: events.append(1))
        idle.start()
        idle._enter_warning()
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# Timeout (phase 2)
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_timeout_emits_timed_out_signal(self, idle: IdleService) -> None:
        fired: list = []
        idle.timedOut.connect(lambda: fired.append(True))
        idle.start()
        idle._on_timeout()
        assert fired == [True]

    def test_timeout_stops_all_timers(self, idle: IdleService) -> None:
        idle.start()
        idle._enter_warning()
        idle._on_timeout()
        assert not idle._phase1.isActive()
        assert not idle._phase2.isActive()
        assert not idle._tick.isActive()

    def test_timeout_fires_after_phase1_then_phase2(self, idle: IdleService) -> None:
        """Verify the two-phase chain: phase1.fire() → warning; phase2.fire() → logout."""
        fired: list = []
        idle.timedOut.connect(lambda: fired.append(True))
        idle.start()

        # Simulate phase-1 timer expiry
        idle._phase1.fire()
        assert idle.warningVisible is True
        assert fired == []

        # Simulate phase-2 timer expiry
        idle._phase2.fire()
        assert fired == [True]
