"""Settings controller — exposes settings to QML and handles screen / camera config.

Exposed to QML as `settingsController`.
"""
from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.mirror_display_service import MirrorDisplayService
from app.services.screen_manager import ScreenManager
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class SettingsController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        settings: SettingsService,
        mirror_display: MirrorDisplayService,
        screen_manager: ScreenManager,
        camera_service,
        app_controller,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._mirror = mirror_display
        self._screens = screen_manager
        self._camera = camera_service
        self._app = app_controller

    # ------------------------------------------------------------------
    # Mirror orientation
    # ------------------------------------------------------------------

    @Property(int, notify=changed)
    def mirrorOrientationDegrees(self) -> int:
        return int(self._settings.get("mirror_orientation_degrees", 0))

    @Slot(int)
    def setMirrorOrientation(self, degrees: int) -> None:
        self._mirror.set_orientation(degrees)
        self._settings.set("mirror_orientation_degrees", degrees)
        self.changed.emit()

    @Slot()
    def toggleMirrorPortrait(self) -> None:
        current = self.mirrorOrientationDegrees
        new_deg = 90 if current == 0 else 0
        self.setMirrorOrientation(new_deg)

    # ------------------------------------------------------------------
    # Compare fill/crop
    # ------------------------------------------------------------------

    @Property(bool, notify=changed)
    def compareFillCrop(self) -> bool:
        return bool(self._settings.get("compare_fill_crop", True))

    @Slot(bool)
    def setCompareFillCrop(self, enabled: bool) -> None:
        self._mirror.set_compare_fill_crop(enabled)
        self._settings.set("compare_fill_crop", enabled)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    @Property(str, notify=changed)
    def cameraBackend(self) -> str:
        return str(self._settings.get("camera_backend", "auto"))

    @Slot(str)
    def setCameraBackend(self, backend: str) -> None:
        self._settings.set("camera_backend", backend)
        self.changed.emit()

    @Property(int, notify=changed)
    def cameraWidth(self) -> int:
        return int(self._settings.get("camera_width", 3840))

    @Property(int, notify=changed)
    def cameraHeight(self) -> int:
        return int(self._settings.get("camera_height", 2160))

    @Property(int, notify=changed)
    def cameraFps(self) -> int:
        return int(self._settings.get("camera_fps", 30))

    @Property(bool, notify=changed)
    def cameraMirrorFlip(self) -> bool:
        return bool(self._settings.get("camera_mirror_flip", False))

    @Slot(bool)
    def setCameraMirrorFlip(self, enabled: bool) -> None:
        self._settings.set("camera_mirror_flip", enabled)
        self.changed.emit()

    @Slot(int, int, int)
    def setCameraResolution(self, width: int, height: int, fps: int) -> None:
        self._settings.set("camera_width", width)
        self._settings.set("camera_height", height)
        self._settings.set("camera_fps", fps)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Screens
    # ------------------------------------------------------------------

    @Property("QVariantList", notify=changed)
    def availableScreens(self) -> list:
        return self._screens.available_screens()

    @Property(bool, notify=changed)
    def screenAutoDetect(self) -> bool:
        return bool(self._settings.get("screen_auto_detect", True))

    @Slot(bool)
    def setScreenAutoDetect(self, enabled: bool) -> None:
        self._settings.set("screen_auto_detect", enabled)
        self.changed.emit()

    @Property(object, notify=changed)
    def autoScreenAssignment(self) -> dict:
        return self._screens.get_auto_assignment()

    @Property(int, notify=changed)
    def controlScreenIndex(self) -> int:
        return int(self._settings.get("control_screen_index", 0))

    @Property(int, notify=changed)
    def mirrorScreenIndex(self) -> int:
        return int(self._settings.get("mirror_screen_index", 1))

    @Slot(int)
    def setControlScreenIndex(self, idx: int) -> None:
        self._settings.set("control_screen_index", idx)
        self.changed.emit()

    @Slot(int)
    def setMirrorScreenIndex(self, idx: int) -> None:
        self._settings.set("mirror_screen_index", idx)
        self.changed.emit()

    @Slot()
    def applyScreenAssignment(self) -> None:
        try:
            self._screens.apply_assignment()
            self._app.showStatus("Screen assignment applied.")
        except Exception as exc:  # noqa: BLE001
            self._app.showError(str(exc))

    # ------------------------------------------------------------------
    # Mirror test
    # ------------------------------------------------------------------

    @Slot()
    def showMirrorTest(self) -> None:
        self._mirror.show_test_pattern()

    @Slot()
    def hideMirrorTest(self) -> None:
        self._mirror.show_idle_black()

    # ------------------------------------------------------------------
    # Camera info
    # ------------------------------------------------------------------

    @Property("QVariantList", notify=changed)
    def availableCameraBackends(self) -> list:
        return self._camera.available_backends()

    @Property(str, notify=changed)
    def cameraBackendLabel(self) -> str:
        return self._camera.current_backend_label()

    @Property(object, notify=changed)
    def dependenciesStatus(self) -> dict:
        return self._camera.dependencies_ok()

    @Property(object, notify=changed)
    def cameraBackendsStatus(self) -> dict:
        return self._camera.backends_status()
