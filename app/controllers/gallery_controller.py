"""Gallery controller — video listing, selection, and workflow dispatch.

Exposed to QML as `galleryController`.
"""
from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Property, Signal, Slot

from app.models.entities import VideoRecord
from app.services.gallery_service import GalleryService
from app.services.playback_service import PlaybackService

LOGGER = logging.getLogger(__name__)


class GalleryController(QObject):
    changed = Signal()
    videosChanged = Signal()

    def __init__(
        self,
        *,
        gallery_service: GalleryService,
        playback_service: PlaybackService,
        app_controller,
        session_controller,
    ) -> None:
        super().__init__()
        self._gallery = gallery_service
        self._playback = playback_service
        self._app = app_controller
        self._session_ctrl = session_controller

        self._videos: list[VideoRecord] = []
        self._selected_ids: list[str] = []  # max 2

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @Property("QVariantList", notify=videosChanged)
    def videos(self) -> list:
        return [v.to_dict() for v in self._videos]

    @Property(int, notify=changed)
    def videoCount(self) -> int:
        return len(self._videos)

    @Property("QVariantList", notify=changed)
    def selectedIds(self) -> list:
        return list(self._selected_ids)

    @Property(int, notify=changed)
    def selectedCount(self) -> int:
        return len(self._selected_ids)

    @Property(bool, notify=changed)
    def canCompare(self) -> bool:
        return len(self._selected_ids) == 2

    @Property(bool, notify=changed)
    def canLiveCompare(self) -> bool:
        return len(self._selected_ids) == 1

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        session = self._session_ctrl.activeSession
        session_id = session.get("id") if session else None
        self._videos = self._gallery.list_videos(session_id=session_id)
        self._selected_ids = []
        self.videosChanged.emit()
        self.changed.emit()

    @Slot(str)
    def toggleSelect(self, video_id: str) -> None:
        if video_id in self._selected_ids:
            self._selected_ids.remove(video_id)
        elif len(self._selected_ids) < 2:
            self._selected_ids.append(video_id)
        self.changed.emit()

    @Slot()
    def clearSelection(self) -> None:
        self._selected_ids = []
        self.changed.emit()

    @Slot(str)
    def playVideo(self, video_id: str) -> None:
        video = self._gallery.get_video(video_id)
        if video is None:
            self._app.showError("Video not found.")
            return
        self._playback.open_video(video)
        self._app.show_player()

    @Slot()
    def compareSelected(self) -> None:
        if not self.canCompare:
            self._app.showError("Select exactly 2 videos to compare.")
            return
        left = self._gallery.get_video(self._selected_ids[0])
        right = self._gallery.get_video(self._selected_ids[1])
        if left is None or right is None:
            self._app.showError("One or more selected videos could not be loaded.")
            return
        self._playback.open_compare(left, right)
        self._app.show_compare()

    @Slot()
    def liveCompareSelected(self) -> None:
        if not self.canLiveCompare:
            self._app.showError("Select exactly 1 video for live compare.")
            return
        video = self._gallery.get_video(self._selected_ids[0])
        if video is None:
            self._app.showError("Selected video could not be loaded.")
            return
        try:
            self._playback.open_live_compare(video)
            self._app.show_live_compare()
        except Exception as exc:  # noqa: BLE001
            self._app.showError(str(exc))

    @Slot(str)
    def deleteVideo(self, video_id: str) -> None:
        deleted = self._gallery.delete_video(video_id)
        if deleted:
            self._app.showStatus(f"Deleted {deleted.title}")
        if video_id in self._selected_ids:
            self._selected_ids.remove(video_id)
        self.refresh()

    @Slot(str, result=bool)
    def isSelected(self, video_id: str) -> bool:
        return video_id in self._selected_ids
