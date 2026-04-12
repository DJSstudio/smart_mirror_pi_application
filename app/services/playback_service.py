from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal

from app.models.entities import VideoRecord
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.settings_service import SettingsService


class PlaybackService(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        camera_service: CameraService,
        mirror_display: MirrorDisplayService,
        settings: SettingsService,
    ) -> None:
        super().__init__()
        self._camera_service = camera_service
        self._mirror_display = mirror_display
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._status_text = "Playback idle"
        self._compare_fill_crop = bool(settings.get("compare_fill_crop", True))

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
    def statusText(self) -> str:
        return self._status_text

    @Property(bool, notify=changed)
    def compareFillCrop(self) -> bool:
        return self._compare_fill_crop

    def show_video(self, video: VideoRecord) -> None:
        self._mode = "video"
        self._primary_source = video.to_dict()["sourceUrl"]  # type: ignore[assignment]
        self._secondary_source = ""
        self._primary_label = video.title
        self._secondary_label = ""
        self._status_text = f"Playing {video.title}"
        self._mirror_display.show_video(self._primary_source)
        self.changed.emit()

    def show_compare(self, left: VideoRecord, right: VideoRecord) -> None:
        left_url = left.to_dict()["sourceUrl"]  # type: ignore[index]
        right_url = right.to_dict()["sourceUrl"]  # type: ignore[index]
        self._mode = "compare"
        self._primary_source = str(left_url)
        self._secondary_source = str(right_url)
        self._primary_label = left.title
        self._secondary_label = right.title
        self._status_text = f"Comparing {left.title} and {right.title}"
        self._mirror_display.show_compare(self._primary_source, self._secondary_source)
        self.changed.emit()

    def start_live_compare(self, video: VideoRecord) -> None:
        preview = self._camera_service.start_preview_only()
        video_url = video.to_dict()["sourceUrl"]  # type: ignore[index]
        self._mode = "live_compare"
        self._primary_source = str(video_url)
        self._secondary_source = preview.control_preview_url
        self._primary_label = video.title
        self._secondary_label = "Live"
        self._status_text = f"Live compare with {video.title}"
        self._mirror_display.show_live_compare(
            self._primary_source,
            preview.mirror_preview_url,
        )
        self.changed.emit()

    def close_active(self) -> None:
        if self._mode == "live_compare":
            self._camera_service.stop(discard=True)
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._status_text = "Playback idle"
        self._mirror_display.show_idle_black()
        self.changed.emit()
