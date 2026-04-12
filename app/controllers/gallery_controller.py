from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.gallery_service import GalleryService
from app.services.playback_service import PlaybackService


class GalleryController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        gallery_service: GalleryService,
        playback_service: PlaybackService,
        app_controller,
        session_controller,
    ) -> None:
        super().__init__()
        self._gallery_service = gallery_service
        self._playback_service = playback_service
        self._app_controller = app_controller
        self._session_controller = session_controller
        self._videos: list[dict[str, object]] = []
        self._selected_ids: list[str] = []
        self._error_message = ""
        self.refresh()

    @Property("QVariantList", notify=changed)
    def videos(self):
        return self._videos

    @Property("QVariantList", notify=changed)
    def selectedIds(self):
        return self._selected_ids

    @Property(str, notify=changed)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=changed)
    def canCompare(self) -> bool:
        return len(self._selected_ids) == 2

    @Property(bool, notify=changed)
    def canLiveCompare(self) -> bool:
        return len(self._selected_ids) == 1

    @Slot()
    def refresh(self) -> None:
        self._videos = [video.to_dict() for video in self._gallery_service.list_videos()]
        self._selected_ids = [video_id for video_id in self._selected_ids if any(item["id"] == video_id for item in self._videos)]
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
        self._selected_ids.clear()
        self.changed.emit()

    @Slot(str)
    def openVideo(self, video_id: str) -> None:
        video = self._gallery_service.get_video(video_id)
        if video is None:
            self._set_error("Video not found")
            return
        self._playback_service.show_video(video)
        self._app_controller.show_player_page()
        self._app_controller.showStatus(f"Opened {video.title}")

    @Slot()
    def startCompare(self) -> None:
        if len(self._selected_ids) != 2:
            self._set_error("Select exactly two looks to compare.")
            return
        left = self._gallery_service.get_video(self._selected_ids[0])
        right = self._gallery_service.get_video(self._selected_ids[1])
        if left is None or right is None:
            self._set_error("One of the selected videos no longer exists.")
            return
        self._playback_service.show_compare(left, right)
        self._app_controller.show_compare_page()
        self._app_controller.showStatus("Compare view opened")

    @Slot()
    def startLiveCompare(self) -> None:
        if len(self._selected_ids) != 1:
            self._set_error("Select one look for live compare.")
            return
        video = self._gallery_service.get_video(self._selected_ids[0])
        if video is None:
            self._set_error("Selected video no longer exists.")
            return
        try:
            self._playback_service.start_live_compare(video)
            self._app_controller.show_live_compare_page()
            self._app_controller.showStatus("Live compare opened")
        except Exception as exc:  # noqa: BLE001
            self._set_error(str(exc))

    @Slot(str)
    def deleteVideo(self, video_id: str) -> None:
        video = self._gallery_service.delete_video(video_id)
        if video is None:
            self._set_error("Video not found")
            return
        self._gallery_service.delete_video_files(video)
        self.refresh()
        self._session_controller.refresh()
        self._app_controller.showStatus(f"Deleted {video.title}")

    def _set_error(self, message: str) -> None:
        self._error_message = message
        self.changed.emit()
        self._app_controller.showError(message)
