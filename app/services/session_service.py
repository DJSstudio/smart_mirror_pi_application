from __future__ import annotations

from datetime import datetime

from app.database.repositories import SessionRepository
from app.models.entities import SessionRecord


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    def ensure_active_session(self) -> SessionRecord:
        session = self._repository.get_active_session()
        if session:
            return session
        return self.new_session()

    def new_session(self, name: str | None = None) -> SessionRecord:
        label = name or datetime.now().strftime("Floor Session %b %d %H:%M")
        return self._repository.create_session(label)

    def get_active_session(self) -> SessionRecord | None:
        return self._repository.get_active_session()

    def list_sessions(self, limit: int = 10) -> list[SessionRecord]:
        return self._repository.list_sessions(limit=limit)

    def count_sessions(self) -> int:
        return self._repository.count_sessions()
