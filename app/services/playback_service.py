"""Playback service — orchestrates video playback and mirror display for gallery workflows."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.models.entities import VideoRecord
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class PlaybackService(QObject):
    """Exposed to QML as `playbackService`.

    Tracks the current playback session (mode + sources) and keeps
    MirrorDisplayService in sync.
    """

    changed = Signal()

    def __init__(
        self,
        *,
        camera_service: CameraService,
        mirror_display: MirrorDisplayService,
        settings: SettingsService,
    ) -> None:
        super().__init__()
        self._camera = camera_service
        self._mirror = mirror_display
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._primary_video_id = ""

    # ------------------------------------------------------------------
    # QML-readable properties
    # ------------------------------------------------------------------

    @Property(str, notify=changed)
    def mode(self) -> str:
        return self._mode

    @Property(str, notify=changed)
    def primarySource(self) -> str:
        return self._primary_source

    @Property(str, notify=changed)
    def secondarySource(self) -> str:
        return self._secondary_source

    @Property(str, notify=changed)
    def primaryLabel(self) -> str:
        return self._primary_label

    @Property(str, notify=changed)
    def secondaryLabel(self) -> str:
        return self._secondary_label

    @Property(str, notify=changed)
    def currentVideoId(self) -> str:
        return self._primary_video_id

    # ------------------------------------------------------------------
    # Actions — decorated as @Slot so QML can call them directly
    # ------------------------------------------------------------------

    @Slot()
    def close_active(self) -> None:
        """Stop any active playback and return mirror to idle/black."""
        if self._mode == "live_compare":
            self._camera.stop(discard=True)
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._primary_video_id = ""
        self._mirror.show_idle_black()
        self.changed.emit()

    # ------------------------------------------------------------------
    # Called by GalleryController (Python-to-Python, Slot not strictly
    # required but added for completeness)
    # ------------------------------------------------------------------

    def open_video(self, video: VideoRecord) -> None:
        url = str(video.to_dict()["sourceUrl"])
        self._mode = "video"
        self._primary_source = url
        self._secondary_source = ""
        self._primary_label = video.title
        self._secondary_label = ""
        self._primary_video_id = video.id
        self._mirror.show_video(url)
        self.changed.emit()

    def open_compare(self, left: VideoRecord, right: VideoRecord) -> None:
        left_url  = str(left.to_dict()["sourceUrl"])
        right_url = str(right.to_dict()["sourceUrl"])
        self._mode = "compare"
        self._primary_source = left_url
        self._secondary_source = right_url
        self._primary_label = left.title
        self._secondary_label = right.title
        self._mirror.show_compare(left_url, right_url)
        self.changed.emit()

    def open_live_compare(self, video: VideoRecord) -> None:
        preview   = self._camera.start_preview_only()
        video_url = str(video.to_dict()["sourceUrl"])
        self._mode = "live_compare"
        self._primary_source = video_url
        self._secondary_source = preview.control_preview_url
        self._primary_label = video.title
        self._secondary_label = "Live"
        self._mirror.show_live_compare(video_url, preview.mirror_preview_url)
        self.changed.emit()
