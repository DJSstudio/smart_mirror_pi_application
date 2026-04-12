from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from app.config.logging_config import configure_logging
from app.config.paths import AppPaths
from app.controllers.app_controller import AppController
from app.controllers.gallery_controller import GalleryController
from app.controllers.recording_controller import RecordingController
from app.controllers.session_controller import SessionController
from app.controllers.settings_controller import SettingsController
from app.database.connection import DatabaseManager
from app.database.repositories import SessionRepository, VideoRepository
from app.services.camera_service import CameraService
from app.services.gallery_service import GalleryService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.playback_service import PlaybackService
from app.services.recording_service import RecordingService
from app.services.screen_manager import ScreenManager
from app.services.session_service import SessionService
from app.services.settings_service import SettingsService


LOGGER = logging.getLogger(__name__)


def _load_root(engine: QQmlApplicationEngine, file_path: Path):
    before = len(engine.rootObjects())
    engine.load(QUrl.fromLocalFile(str(file_path)))
    roots = engine.rootObjects()
    if len(roots) <= before:
        raise RuntimeError(f"Failed to load QML root: {file_path}")
    return roots[-1]


def main() -> int:
    paths = AppPaths.discover()
    paths.ensure_directories()
    settings = SettingsService(paths)
    configure_logging(paths, str(settings.get("log_level", "INFO")))
    LOGGER.info("Launching Smart Mirror Pi")

    database = DatabaseManager(paths.database_path)
    database.initialize()

    session_repository = SessionRepository(database)
    video_repository = VideoRepository(database)
    session_service = SessionService(session_repository)
    gallery_service = GalleryService(video_repository)
    camera_service = CameraService(paths, settings)
    mirror_display = MirrorDisplayService(settings)
    playback_service = PlaybackService(
        camera_service=camera_service,
        mirror_display=mirror_display,
        settings=settings,
    )
    recording_service = RecordingService(
        paths=paths,
        settings=settings,
        repository=video_repository,
        session_service=session_service,
    )

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Smart Mirror Pi")
    app.setOrganizationName("Smart Mirror")

    screen_manager = ScreenManager(app, settings)

    app_controller = AppController(playback_service)
    session_controller = SessionController(
        session_service=session_service,
        gallery_service=gallery_service,
    )
    gallery_controller = GalleryController(
        gallery_service=gallery_service,
        playback_service=playback_service,
        app_controller=app_controller,
        session_controller=session_controller,
    )
    recording_controller = RecordingController(
        camera_service=camera_service,
        recording_service=recording_service,
        mirror_display=mirror_display,
        app_controller=app_controller,
        session_controller=session_controller,
        gallery_controller=gallery_controller,
    )
    app_controller.attach_recording_controller(recording_controller)
    settings_controller = SettingsController(
        settings=settings,
        mirror_display=mirror_display,
        screen_manager=screen_manager,
        camera_service=camera_service,
        app_controller=app_controller,
    )

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("appController", app_controller)
    context.setContextProperty("sessionController", session_controller)
    context.setContextProperty("galleryController", gallery_controller)
    context.setContextProperty("recordingController", recording_controller)
    context.setContextProperty("settingsController", settings_controller)
    context.setContextProperty("mirrorDisplay", mirror_display)
    context.setContextProperty("playbackService", playback_service)

    qml_root = paths.repo_root / "app" / "qml"
    control_window = _load_root(engine, qml_root / "ControlWindow.qml")
    mirror_window = _load_root(engine, qml_root / "MirrorWindow.qml")

    screen_manager.bind_windows(control_window, mirror_window)
    assignment = screen_manager.apply_assignment()
    LOGGER.info(
        "Control screen: %s | Mirror screen: %s",
        assignment.control_screen.name(),
        assignment.mirror_screen.name(),
    )
    mirror_display.show_idle_black()

    def _shutdown() -> None:
        LOGGER.info("Shutting down Smart Mirror Pi")
        try:
            playback_service.close_active()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to close playback cleanly")
        try:
            camera_service.stop(discard=True)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to stop camera cleanly")
        database.close()

    app.aboutToQuit.connect(_shutdown)

    exit_code = app.exec()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
