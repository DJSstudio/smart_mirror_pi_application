from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.settings_service import SettingsService


class MirrorDisplayService(QObject):
    changed = Signal()

    def __init__(self, settings: SettingsService) -> None:
        super().__init__()
        self._settings = settings
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._orientation_degrees = int(settings.get("mirror_orientation_degrees", 0))
        self._compare_fill_crop = bool(settings.get("compare_fill_crop", True))
        self._status_text = "Mirror idle"

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

    @Property(int, notify=changed)
    def orientationDegrees(self) -> int:
        return self._orientation_degrees

    @Property(bool, notify=changed)
    def compareFillCrop(self) -> bool:
        return self._compare_fill_crop

    @Property(str, notify=changed)
    def statusText(self) -> str:
        return self._status_text

    @Slot()
    def show_idle_black(self) -> None:
        self._set_state(
            mode="idle",
            primary="",
            secondary="",
            primary_label="",
            secondary_label="",
            status="Mirror idle",
        )

    @Slot(str)
    def show_live_preview(self, source: str) -> None:
        self._set_state(
            mode="live_preview",
            primary=source,
            secondary="",
            primary_label="Live",
            secondary_label="",
            status="Live preview on mirror",
        )

    @Slot(str)
    def show_recording_preview(self, source: str) -> None:
        self._set_state(
            mode="recording_preview",
            primary=source,
            secondary="",
            primary_label="Recording",
            secondary_label="",
            status="Recording preview on mirror",
        )

    @Slot(str)
    def show_video(self, path: str) -> None:
        self._set_state(
            mode="video",
            primary=path,
            secondary="",
            primary_label="Playback",
            secondary_label="",
            status="Video playback on mirror",
        )

    @Slot(str, str)
    def show_compare(self, left_source: str, right_source: str) -> None:
        self._set_state(
            mode="compare",
            primary=left_source,
            secondary=right_source,
            primary_label="Look 1",
            secondary_label="Look 2",
            status="Compare mode on mirror",
        )

    @Slot(str, str)
    def show_live_compare(self, saved_video: str, live_source: str) -> None:
        self._set_state(
            mode="live_compare",
            primary=saved_video,
            secondary=live_source,
            primary_label="Saved",
            secondary_label="Live",
            status="Live compare on mirror",
        )

    @Slot()
    def show_test_pattern(self) -> None:
        self._set_state(
            mode="test_pattern",
            primary="",
            secondary="",
            primary_label="",
            secondary_label="",
            status="Mirror test pattern",
        )

    def set_orientation(self, degrees: int) -> None:
        self._orientation_degrees = degrees
        self.changed.emit()

    def set_compare_fill_crop(self, enabled: bool) -> None:
        self._compare_fill_crop = enabled
        self.changed.emit()

    def _set_state(
        self,
        *,
        mode: str,
        primary: str,
        secondary: str,
        primary_label: str,
        secondary_label: str,
        status: str,
    ) -> None:
        self._mode = mode
        self._primary_source = primary
        self._secondary_source = secondary
        self._primary_label = primary_label
        self._secondary_label = secondary_label
        self._status_text = status
        self.changed.emit()
