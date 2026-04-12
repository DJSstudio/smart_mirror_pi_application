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

    def end_active_session(self) -> None:
        session = self._repo.get_active_session()
        if session:
            self._repo.end_session(session.id)

    def list_sessions(self, limit: int = 20) -> list[SessionRecord]:
        return self._repo.list_sessions(limit=limit)

    def count_sessions(self) -> int:
        return self._repo.count_sessions()
