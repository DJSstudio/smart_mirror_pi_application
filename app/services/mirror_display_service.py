"""Mirror display state machine.

This service is the single authority over what the mirror window shows.
QML MirrorWindow binds to properties on this object via the context property
`mirrorDisplay`.

Mirror states
─────────────
  idle            — pure black (default on boot and after any feature ends)
  live_preview    — live camera feed during recording session
  video           — single video playback
  compare         — side-by-side two video comparison
  live_compare    — saved video (left) + live camera (right)
  test_pattern    — coloured test card used from Settings
"""
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

    @Property(int, notify=changed)
    def orientationDegrees(self) -> int:
        return self._orientation_degrees

    @Property(bool, notify=changed)
    def compareFillCrop(self) -> bool:
        return self._compare_fill_crop

    # ------------------------------------------------------------------
    # Transition slots (callable from Python and from QML)
    # ------------------------------------------------------------------

    @Slot()
    def show_idle_black(self) -> None:
        self._set("idle", "", "", "", "")

    @Slot(str)
    def show_live_preview(self, source: str) -> None:
        self._set("live_preview", source, "", "Live", "")

    @Slot(str)
    def show_video(self, path: str) -> None:
        self._set("video", path, "", "Playback", "")

    @Slot(str, str)
    def show_compare(self, left: str, right: str) -> None:
        self._set("compare", left, right, "Look A", "Look B")

    @Slot(str, str)
    def show_live_compare(self, saved: str, live: str) -> None:
        self._set("live_compare", saved, live, "Saved", "Live")

    @Slot()
    def show_test_pattern(self) -> None:
        self._set("test_pattern", "", "", "", "")

    # ------------------------------------------------------------------
    # Configuration setters (not slots — called by SettingsController)
    # ------------------------------------------------------------------

    def set_orientation(self, degrees: int) -> None:
        self._orientation_degrees = degrees
        self._settings.set("mirror_orientation_degrees", degrees)
        self.changed.emit()

    def set_compare_fill_crop(self, enabled: bool) -> None:
        self._compare_fill_crop = enabled
        self._settings.set("compare_fill_crop", enabled)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _set(
        self,
        mode: str,
        primary: str,
        secondary: str,
        primary_label: str,
        secondary_label: str,
    ) -> None:
        self._mode = mode
        self._primary_source = primary
        self._secondary_source = secondary
        self._primary_label = primary_label
        self._secondary_label = secondary_label
        self.changed.emit()
