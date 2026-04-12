"""Session controller — start/end sessions, expose active session to QML.

Exposed to QML as `sessionController`.
"""
from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.session_service import SessionService

LOGGER = logging.getLogger(__name__)


class SessionController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        session_service: SessionService,
        gallery_service,
    ) -> None:
        super().__init__()
        self._sessions = session_service
        self._gallery = gallery_service
        self._active: dict | None = None
        self._session_count = 0
        self._video_count = 0
        self.refresh()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @Property(object, notify=changed)
    def activeSession(self) -> dict | None:
        return self._active

    @Property(int, notify=changed)
    def sessionCount(self) -> int:
        return self._session_count

    @Property(int, notify=changed)
    def videoCount(self) -> int:
        return self._video_count

    @Property(bool, notify=changed)
    def hasActiveSession(self) -> bool:
        return self._active is not None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def newSession(self) -> None:
        self._sessions.new_session()
        self.refresh()
        LOGGER.info("New session started")

    @Slot()
    def endSession(self) -> None:
        self._sessions.end_active_session()
        self.refresh()
        LOGGER.info("Session ended")

    @Slot()
    def refresh(self) -> None:
        session = self._sessions.get_active_session()
        if session is None:
            session = self._sessions.ensure_active_session()
        self._active = session.to_dict() if session else None
        self._session_count = self._sessions.count_sessions()
        session_id = self._active["id"] if self._active else None
        self._video_count = self._gallery.count_videos(session_id=session_id)
        self.changed.emit()
