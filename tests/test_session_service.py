"""Unit tests for SessionService — pure Python, no DB required."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from app.models.entities import SessionRecord
from app.services.session_service import SessionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    id: str = "sess-1",
    name: str = "Session — Jan 01, 2024",
    device_id: str = "",
    active: bool = True,
) -> SessionRecord:
    return SessionRecord(
        id=id,
        name=name,
        started_at="2024-01-01T00:00:00",
        ended_at=None,
        active=active,
        device_id=device_id,
    )


@pytest.fixture()
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def svc(repo: MagicMock) -> SessionService:
    return SessionService(repo)


# ---------------------------------------------------------------------------
# ensure_active_session
# ---------------------------------------------------------------------------

class TestEnsureActiveSession:
    def test_returns_existing_active_session(self, svc: SessionService, repo: MagicMock) -> None:
        existing = _make_session()
        repo.get_active_session.return_value = existing

        result = svc.ensure_active_session()

        assert result is existing
        repo.create_session.assert_not_called()

    def test_creates_session_when_none_exists(self, svc: SessionService, repo: MagicMock) -> None:
        new_session = _make_session(id="sess-new")
        repo.get_active_session.return_value = None
        repo.create_session.return_value = new_session

        result = svc.ensure_active_session()

        assert result is new_session
        repo.create_session.assert_called_once()
        name_arg = repo.create_session.call_args[0][0]
        assert name_arg.startswith("Session —")


# ---------------------------------------------------------------------------
# new_session
# ---------------------------------------------------------------------------

class TestNewSession:
    def test_always_creates_new_session(self, svc: SessionService, repo: MagicMock) -> None:
        new_session = _make_session(id="sess-fresh")
        repo.create_session.return_value = new_session

        result = svc.new_session()

        assert result is new_session
        repo.create_session.assert_called_once()


# ---------------------------------------------------------------------------
# get_or_resume_for_device
# ---------------------------------------------------------------------------

class TestGetOrResumeForDevice:
    def test_device_owns_active_session_returns_resumed(
        self, svc: SessionService, repo: MagicMock
    ) -> None:
        session = _make_session(id="s1", device_id="dev-abc")
        repo.get_latest_session_for_device.return_value = session
        repo.get_active_session.return_value = session

        result, was_resumed = svc.get_or_resume_for_device("dev-abc")

        assert result is session
        assert was_resumed is True
        repo.activate_session.assert_not_called()

    def test_device_has_previous_session_activates_it(
        self, svc: SessionService, repo: MagicMock
    ) -> None:
        old = _make_session(id="s-old", device_id="dev-abc")
        current = _make_session(id="s-current", device_id="dev-xyz")
        activated = _make_session(id="s-old", device_id="dev-abc")

        repo.get_latest_session_for_device.return_value = old
        repo.get_active_session.return_value = current
        repo.activate_session.return_value = activated

        result, was_resumed = svc.get_or_resume_for_device("dev-abc")

        assert result is activated
        assert was_resumed is True
        repo.activate_session.assert_called_once_with("s-old", "dev-abc")

    def test_new_device_claims_unclaimed_current_session(
        self, svc: SessionService, repo: MagicMock
    ) -> None:
        unclaimed = _make_session(id="s-unclaimed", device_id="")
        claimed = _make_session(id="s-unclaimed", device_id="dev-new")

        repo.get_latest_session_for_device.return_value = None
        repo.get_active_session.side_effect = [unclaimed, claimed]
        repo.claim_current_session.return_value = None

        result, was_resumed = svc.get_or_resume_for_device("dev-new")

        assert result is claimed
        assert was_resumed is False
        repo.claim_current_session.assert_called_once_with("dev-new")

    def test_new_device_creates_fresh_session_when_current_is_claimed(
        self, svc: SessionService, repo: MagicMock
    ) -> None:
        current = _make_session(id="s-other", device_id="dev-someone-else")
        fresh = _make_session(id="s-fresh", device_id="dev-new")

        repo.get_latest_session_for_device.return_value = None
        repo.get_active_session.return_value = current
        repo.create_session.return_value = fresh

        result, was_resumed = svc.get_or_resume_for_device("dev-new")

        assert result is fresh
        assert was_resumed is False
        repo.create_session.assert_called_once()


# ---------------------------------------------------------------------------
# end_active_session
# ---------------------------------------------------------------------------

class TestEndActiveSession:
    def test_ends_active_session(self, svc: SessionService, repo: MagicMock) -> None:
        session = _make_session(id="s1")
        repo.get_active_session.return_value = session

        svc.end_active_session()

        repo.end_session.assert_called_once_with("s1")

    def test_noop_when_no_active_session(self, svc: SessionService, repo: MagicMock) -> None:
        repo.get_active_session.return_value = None

        svc.end_active_session()

        repo.end_session.assert_not_called()


# ---------------------------------------------------------------------------
# count_sessions / list_sessions
# ---------------------------------------------------------------------------

class TestCountAndList:
    def test_count_delegates_to_repo(self, svc: SessionService, repo: MagicMock) -> None:
        repo.count_sessions.return_value = 7
        assert svc.count_sessions() == 7

    def test_list_delegates_to_repo(self, svc: SessionService, repo: MagicMock) -> None:
        sessions = [_make_session(id=f"s{i}") for i in range(3)]
        repo.list_sessions.return_value = sessions

        result = svc.list_sessions(limit=3)

        assert result == sessions
        repo.list_sessions.assert_called_once_with(limit=3)
