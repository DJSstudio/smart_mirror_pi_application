"""Session lifecycle management."""
from __future__ import annotations

from datetime import datetime

from app.database.repositories import SessionRepository
from app.models.entities import SessionRecord


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def ensure_active_session(self) -> SessionRecord:
        session = self._repo.get_active_session()
        if session is None:
            stamp = datetime.now().strftime("%B %d, %Y")
            session = self._repo.create_session(f"Session — {stamp}")
        return session

    def new_session(self) -> SessionRecord:
        stamp = datetime.now().strftime("%B %d, %Y  %H:%M")
        return self._repo.create_session(f"Session — {stamp}")

    def get_active_session(self) -> SessionRecord | None:
        return self._repo.get_active_session()

    def get_or_resume_for_device(self, device_id: str) -> tuple[SessionRecord, bool]:
        """Return *(session, was_resumed)* for the given *device_id*.

        Resolution order
        ────────────────
        1. If the device already owns the current active session → confirm (resumed).
        2. If the device has a *different* previous session → switch to it (resumed).
        3. If the current session is unclaimed → claim it for the device (new).
        4. Otherwise → create a fresh session for the device (new).
        """
        existing = self._repo.get_latest_session_for_device(device_id)
        current = self._repo.get_active_session()

        if existing:
            if current and existing.id == current.id:
                # Device already owns the active session — just confirm.
                return current, True
            # Switch to the device's previous session.
            session = self._repo.activate_session(existing.id, device_id)
            return session, True  # type: ignore[return-value]

        # New device on this mirror.
        if current and not current.device_id:
            # Current session is unclaimed — stamp it for this device.
            self._repo.claim_current_session(device_id)
            return self._repo.get_active_session(), False  # type: ignore[return-value]

        # Current session belongs to someone else (or there is none) — fresh start.
        stamp = datetime.now().strftime("%B %d, %Y  %H:%M")
        session = self._repo.create_session(f"Session — {stamp}", device_id=device_id)
        return session, False

    def new_session_for_device(self, device_id: str) -> SessionRecord:
        """Create a brand-new session owned by *device_id* (never resumes).

        Used when the user explicitly chooses "Start Fresh" after scanning QR.
        Any currently active session is ended by ``create_session``.
        """
        stamp = datetime.now().strftime("%B %d, %Y  %H:%M")
        return self._repo.create_session(f"Session — {stamp}", device_id=device_id)

    def get_device_session(self, device_id: str) -> SessionRecord | None:
        """Return the most-recent session owned by *device_id* (any status)."""
        return self._repo.get_latest_session_for_device(device_id)

    def relink_active_session(self, device_id: str) -> SessionRecord | None:
        """Claim the currently active session for a new *device_id*.

        Used when the same physical user returns but their browser has a new
        device_id (e.g. the Pi's IP changed between visits, resetting
        localStorage).  The session and its videos are preserved; only the
        device_id ownership is updated.
        """
        current = self._repo.get_active_session()
        if current is None:
            return None
        return self._repo.activate_session(current.id, device_id)

    def end_active_session(self) -> None:
        session = self._repo.get_active_session()
        if session:
            self._repo.end_session(session.id)

    def list_sessions(self, limit: int = 20) -> list[SessionRecord]:
        return self._repo.list_sessions(limit=limit)

    def count_sessions(self) -> int:
        return self._repo.count_sessions()
