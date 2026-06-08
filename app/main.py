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
from app.controllers.export_controller import ExportController
from app.controllers.gallery_controller import GalleryController
from app.controllers.login_controller import LoginController
from app.controllers.recording_controller import RecordingController
from app.controllers.session_controller import SessionController
from app.controllers.settings_controller import SettingsController
from app.database.connection import DatabaseManager
from app.database.repositories import FootfallRepository, SessionRepository, VideoRepository
from app.services.camera_service import CameraService
from app.services.gallery_service import GalleryService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.playback_service import PlaybackService
from app.services.recording_service import RecordingService
from app.controllers.wifi_controller import WifiController
from app.services.cleanup_service import CleanupService
from app.services.idle_service import IdleService
from app.services.wifi_service import WifiService
from app.services.screen_manager import ScreenManager
from app.services.session_service import SessionService
from app.services.settings_service import SettingsService
from app.services.share_server import ShareServer

LOGGER = logging.getLogger(__name__)


def _check_multimedia_backend() -> None:
    """Log Qt Multimedia backend status with actionable diagnostics."""
    import os  # noqa: PLC0415

    # Show where Qt is looking for multimedia plugins
    try:
        from PySide6.QtCore import QLibraryInfo  # noqa: PLC0415
        plugin_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        mm_dir = os.path.join(plugin_dir, "multimedia")
        if os.path.isdir(mm_dir):
            plugins = os.listdir(mm_dir)
            LOGGER.info("Qt multimedia plugin dir: %s  plugins: %s", mm_dir, plugins)
        else:
            LOGGER.warning(
                "Qt multimedia plugin dir does not exist: %s  "
                "pip-PySide6 on this platform may not ship a multimedia backend. "
                "Try: sudo apt install python3-pyside6.qtmultimedia",
                mm_dir,
            )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Could not query Qt plugin path: %s", exc)

    # Try creating a MediaPlayer to confirm backend works
    try:
        from PySide6.QtMultimedia import QMediaPlayer  # noqa: PLC0415
        player = QMediaPlayer()
        if player.error() == QMediaPlayer.Error.NoError:
            LOGGER.info("Qt Multimedia backend: OK")
        else:
            LOGGER.warning(
                "Qt Multimedia backend not available: %s  video will be black.",
                player.errorString(),
            )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Qt Multimedia import failed: %s", exc)


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
    from app.platform.base_camera_adapter import BaseCameraAdapter  # noqa: PLC0415
    LOGGER.info("=" * 60)
    LOGGER.info("Smart Mirror Pi  starting up")
    LOGGER.info("Hardware: %s", BaseCameraAdapter.detect_pi_model() or "non-Pi")
    LOGGER.info("Data dir: %s", paths.data_dir)

    # ----------------------------------------------------------------
    # Database
    # ----------------------------------------------------------------
    db = DatabaseManager(paths.database_path)
    db.initialize()
    session_repo = SessionRepository(db)
    video_repo = VideoRepository(db)
    footfall_repo = FootfallRepository(db)

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
        paths=paths,
        recording_service=recording_service,
    )
    # Auto-cleanup: delete video data for sessions idle > threshold.
    # Runs once at startup (before Qt) then every 30 min via QTimer below.
    _cleanup_hours = float(settings.get("session_cleanup_hours", 1))
    cleanup_service = CleanupService(db=db, video_repo=video_repo)
    cleanup_service.run(older_than_hours=_cleanup_hours)

    _share_port = int(settings.get("share_server_port", 8765))
    _share_tls = bool(settings.get("share_server_tls", False))
    share_server = ShareServer(
        port=_share_port,
        tls=_share_tls,
        cert_dir=paths.data_dir / "tls",
    )
    share_server.start()

    # ----------------------------------------------------------------
    # Qt application
    # ----------------------------------------------------------------
    app = QGuiApplication(sys.argv)
    _check_multimedia_backend()
    app.setApplicationName("Smart Mirror Pi")
    app.setOrganizationName("Smart Mirror")

    # QMediaCaptureSession requires QGuiApplication to exist before it is
    # constructed, so we create the camera session here and hand it off to
    # CameraService.  Also exposed to QML as `qtCamera` further down.
    from app.services.qt_camera_session import QtCameraSession  # noqa: PLC0415
    qt_camera_session = QtCameraSession()
    camera_service.attach_qt_camera_session(qt_camera_session)
    playback_service.attach_qt_camera_session(qt_camera_session)
    # Cache the camera enumeration NOW, before any recording starts and
    # ffmpeg locks the source camera.  On Pi 4, Qt's GStreamer-based v4l2
    # enumeration can fail to list any cameras once ffmpeg is holding the
    # source — looking them up from this cache avoids that race.
    n = qt_camera_session.prime_devices()
    LOGGER.info("Qt camera enumeration: %d device(s) found", n)

    screen_manager = ScreenManager(app, settings)

    # Periodic cleanup — runs every 30 minutes while the app is open.
    _cleanup_timer = QTimer()
    _cleanup_timer.setInterval(30 * 60 * 1_000)  # 30 minutes
    _cleanup_timer.timeout.connect(lambda: cleanup_service.run(older_than_hours=_cleanup_hours))
    _cleanup_timer.start()

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
    # When PlaybackService saves a Live Compare recording, refresh the
    # gallery so the new entry appears immediately.
    playback_service.videoSaved.connect(lambda _title: (
        gallery_ctrl.refresh(),
        session_ctrl.refresh(),
    ))
    recording_ctrl = RecordingController(
        camera_service=camera_service,
        recording_service=recording_service,
        mirror_display=mirror_display,
        app_controller=app_ctrl,
        session_controller=session_ctrl,
        gallery_controller=gallery_ctrl,
    )
    app_ctrl.attach_recording_controller(recording_ctrl)
    login_ctrl = LoginController(
        share_server=share_server,
        session_service=session_service,
        gallery_service=gallery_service,
        footfall_repo=footfall_repo,
        session_ctrl=session_ctrl,
        gallery_ctrl=gallery_ctrl,
        mirror_display=mirror_display,
        app_controller=app_ctrl,
        temp_dir=paths.temp_dir,
    )
    export_ctrl = ExportController(
        gallery_service=gallery_service,
        session_service=session_service,
        mirror_display=mirror_display,
        share_server=share_server,
        temp_dir=paths.temp_dir,
        app_controller=app_ctrl,
    )
    wifi_ctrl = WifiController(WifiService())
    settings_ctrl = SettingsController(
        settings=settings,
        mirror_display=mirror_display,
        screen_manager=screen_manager,
        camera_service=camera_service,
        app_controller=app_ctrl,
    )

    # ----------------------------------------------------------------
    # Idle auto-logout
    # ----------------------------------------------------------------
    _idle_timeout_ms = int(settings.get("idle_timeout_seconds", 300)) * 1_000
    _idle_warning_ms = int(settings.get("idle_warning_seconds", 60)) * 1_000
    idle_service = IdleService(
        timeout_ms=_idle_timeout_ms,
        warning_ms=_idle_warning_ms,
    )
    idle_service.install(app)
    idle_service.timedOut.connect(login_ctrl.autoLogout)

    # Pause on pages where auto-logout makes no sense:
    #   login     — already at the login screen, nothing to time out
    #   recording — never interrupt an active capture mid-session
    def _on_page_changed() -> None:
        if app_ctrl.currentPage in ("login", "recording"):
            idle_service.stop()
        else:
            idle_service.start()

    app_ctrl.currentPageChanged.connect(_on_page_changed)

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
    ctx.setContextProperty("exportController", export_ctrl)
    ctx.setContextProperty("loginController", login_ctrl)
    ctx.setContextProperty("wifiController", wifi_ctrl)
    ctx.setContextProperty("mirrorDisplay", mirror_display)
    ctx.setContextProperty("playbackService", playback_service)
    ctx.setContextProperty("idleService", idle_service)
    ctx.setContextProperty("qtCamera", qt_camera_session)

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

    # Start QR login flow: show QR on mirror, login page on control window.
    # The login controller will navigate to dashboard after a successful scan.
    login_ctrl.startLogin()

    # Safety re-check: re-assert fullscreen after the compositor has had time to
    # settle (late screen init on Pi).  _place_fullscreen skips showNormal() on
    # the second call so this cannot race with the initial placement above.
    QTimer.singleShot(800, screen_manager.apply_assignment)

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
        try:
            share_server.stop()
        except Exception:  # noqa: BLE001
            pass
        db.close()

    app.aboutToQuit.connect(_on_quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
