"""Smart Mirror Pi — application entry point."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
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


def _load_qml(engine: QQmlApplicationEngine, path: Path):
    before = len(engine.rootObjects())
    engine.load(QUrl.fromLocalFile(str(path)))
    roots = engine.rootObjects()
    if len(roots) <= before:
        raise RuntimeError(f"QML load failed — check syntax: {path}")
    return roots[-1]


def main() -> int:
    # ----------------------------------------------------------------
    # Bootstrap
    # ----------------------------------------------------------------
    paths = AppPaths.discover()
    paths.ensure_directories()

    settings = SettingsService(paths)
    configure_logging(paths, str(settings.get("log_level", "INFO")))
    LOGGER.info("=" * 60)
    LOGGER.info("Smart Mirror Pi  starting up")
    LOGGER.info("Data dir: %s", paths.data_dir)

    # ----------------------------------------------------------------
    # Database
    # ----------------------------------------------------------------
    db = DatabaseManager(paths.database_path)
    db.initialize()
    session_repo = SessionRepository(db)
    video_repo = VideoRepository(db)

    # ----------------------------------------------------------------
    # Services
    # ----------------------------------------------------------------
    session_service = SessionService(session_repo)
    gallery_service = GalleryService(video_repo)
    camera_service = CameraService(paths, settings)
    mirror_display = MirrorDisplayService(settings)
    recording_service = RecordingService(
        paths=paths,
        settings=settings,
        repository=video_repo,
        session_service=session_service,
    )
    playback_service = PlaybackService(
        camera_service=camera_service,
        mirror_display=mirror_display,
        settings=settings,
    )

    # ----------------------------------------------------------------
    # Qt application
    # ----------------------------------------------------------------
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Smart Mirror Pi")
    app.setOrganizationName("Smart Mirror")

    screen_manager = ScreenManager(app, settings)

    # ----------------------------------------------------------------
    # Controllers
    # ----------------------------------------------------------------
    app_ctrl = AppController(playback_service)
    session_ctrl = SessionController(
        session_service=session_service,
        gallery_service=gallery_service,
    )
    gallery_ctrl = GalleryController(
        gallery_service=gallery_service,
        playback_service=playback_service,
        app_controller=app_ctrl,
        session_controller=session_ctrl,
    )
    recording_ctrl = RecordingController(
        camera_service=camera_service,
        recording_service=recording_service,
        mirror_display=mirror_display,
        app_controller=app_ctrl,
        session_controller=session_ctrl,
        gallery_controller=gallery_ctrl,
    )
    app_ctrl.attach_recording_controller(recording_ctrl)
    settings_ctrl = SettingsController(
        settings=settings,
        mirror_display=mirror_display,
        screen_manager=screen_manager,
        camera_service=camera_service,
        app_controller=app_ctrl,
    )

    # ----------------------------------------------------------------
    # QML engine
    # ----------------------------------------------------------------
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("appController", app_ctrl)
    ctx.setContextProperty("sessionController", session_ctrl)
    ctx.setContextProperty("galleryController", gallery_ctrl)
    ctx.setContextProperty("recordingController", recording_ctrl)
    ctx.setContextProperty("settingsController", settings_ctrl)
    ctx.setContextProperty("mirrorDisplay", mirror_display)
    ctx.setContextProperty("playbackService", playback_service)

    qml_root = paths.repo_root / "app" / "qml"
    control_win = _load_qml(engine, qml_root / "ControlWindow.qml")
    mirror_win  = _load_qml(engine, qml_root / "MirrorWindow.qml")

    # ----------------------------------------------------------------
    # Screen placement
    # ----------------------------------------------------------------
    screen_manager.bind_windows(control_win, mirror_win)
    assignment = screen_manager.apply_assignment()
    LOGGER.info(
        "Windows placed — control: %s  mirror: %s  single=%s",
        assignment.control_screen.name(),
        assignment.mirror_screen.name(),
        assignment.single_screen_mode,
    )

    # Ensure mirror starts black
    mirror_display.show_idle_black()

    # Initial gallery load
    gallery_ctrl.refresh()

    # Refresh placement after the event loop starts (handles late screen init)
    QTimer.singleShot(200, screen_manager.apply_assignment)

    # ----------------------------------------------------------------
    # Shutdown
    # ----------------------------------------------------------------
    def _on_quit() -> None:
        LOGGER.info("Shutting down Smart Mirror Pi")
        try:
            playback_service.close_active()
        except Exception:  # noqa: BLE001
            pass
        try:
            camera_service.stop(discard=True)
        except Exception:  # noqa: BLE001
            pass
        db.close()

    app.aboutToQuit.connect(_on_quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
