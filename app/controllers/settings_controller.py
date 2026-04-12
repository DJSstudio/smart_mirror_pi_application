from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.screen_manager import ScreenManager
from app.services.settings_service import SettingsService


class SettingsController(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        settings: SettingsService,
        mirror_display: MirrorDisplayService,
        screen_manager: ScreenManager,
        camera_service: CameraService,
        app_controller,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._mirror_display = mirror_display
        self._screen_manager = screen_manager
        self._camera_service = camera_service
        self._app_controller = app_controller

    @Property("QVariantList", notify=changed)
    def displays(self):
        return self._screen_manager.describe_screens()

    @Property("QVariantList", notify=changed)
    def cameraBackends(self):
        return self._camera_service.available_backends()

    @Property(int, notify=changed)
    def controlScreenIndex(self) -> int:
        return int(self._settings.get("control_screen_index", 0))

    @Property(int, notify=changed)
    def mirrorScreenIndex(self) -> int:
        return int(self._settings.get("mirror_screen_index", 1))

    @Property(int, notify=changed)
    def mirrorOrientationDegrees(self) -> int:
        return int(self._settings.get("mirror_orientation_degrees", 0))

    @Property(bool, notify=changed)
    def compareFillCrop(self) -> bool:
        return bool(self._settings.get("compare_fill_crop", True))

    @Property(str, notify=changed)
    def cameraBackend(self) -> str:
        return str(self._settings.get("camera_backend", "auto"))

    @Property(str, notify=changed)
    def currentCameraBackendLabel(self) -> str:
        return self._camera_service.current_backend_label()

    @Property(str, notify=changed)
    def dependencySummary(self) -> str:
        deps = self._camera_service.dependencies_summary()
        bits = [f"{key}:{'ok' if available else 'missing'}" for key, available in deps.items()]
        return " | ".join(bits)

    @Slot(int, int)
    def saveScreenAssignment(self, control_index: int, mirror_index: int) -> None:
        self._settings.update(
            {
                "control_screen_index": control_index,
                "mirror_screen_index": mirror_index,
            }
        )
        self._screen_manager.apply_assignment()
        self.changed.emit()
        self._app_controller.showStatus("Screen assignment updated")

    @Slot(int)
    def setMirrorOrientation(self, degrees: int) -> None:
        self._settings.set("mirror_orientation_degrees", degrees)
        self._mirror_display.set_orientation(degrees)
        self.changed.emit()
        self._app_controller.showStatus(f"Mirror orientation set to {degrees}°")

    @Slot(bool)
    def setCompareFillCrop(self, enabled: bool) -> None:
        self._settings.set("compare_fill_crop", enabled)
        self._mirror_display.set_compare_fill_crop(enabled)
        self.changed.emit()
        self._app_controller.showStatus("Mirror compare fill mode updated")

    @Slot(str)
    def setCameraBackend(self, backend: str) -> None:
        self._settings.set("camera_backend", backend)
        self.changed.emit()
        self._app_controller.showStatus(f"Camera backend preference set to {backend}")

    @Slot()
    def showMirrorTestPattern(self) -> None:
        self._mirror_display.show_test_pattern()
        self._app_controller.showStatus("Mirror test pattern active")

    @Slot()
    def blackoutMirror(self) -> None:
        self._mirror_display.show_idle_black()
        self._app_controller.showStatus("Mirror returned to black idle")
