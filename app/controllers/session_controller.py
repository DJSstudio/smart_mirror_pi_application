from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.gallery_service import GalleryService
from app.services.session_service import SessionService


class SessionController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        session_service: SessionService,
        gallery_service: GalleryService,
    ) -> None:
        super().__init__()
        self._session_service = session_service
        self._gallery_service = gallery_service
        self._active_name = ""
        self._active_id = ""
        self._clip_count = 0
        self._session_count = 0
        self.refresh()

    @Property(str, notify=changed)
    def activeSessionName(self) -> str:
        return self._active_name

    @Property(str, notify=changed)
    def activeSessionId(self) -> str:
        return self._active_id

    @Property(int, notify=changed)
    def clipCount(self) -> int:
        return self._clip_count

    @Property(int, notify=changed)
    def sessionCount(self) -> int:
        return self._session_count

    @Slot()
    def refresh(self) -> None:
        session = self._session_service.ensure_active_session()
        self._active_name = session.name
        self._active_id = session.id
        self._clip_count = self._gallery_service.count_videos(session.id)
        self._session_count = self._session_service.count_sessions()
        self.changed.emit()

    @Slot(str)
    def newSession(self, name: str = "") -> None:
        self._session_service.new_session(name.strip() or None)
        self.refresh()
