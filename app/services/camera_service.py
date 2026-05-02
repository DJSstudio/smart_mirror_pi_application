"""Camera service — selects the right adapter and manages the active session."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config.paths import AppPaths
from app.models.entities import CameraPreview, CompletedCapture
from app.platform.qt_camera_adapter import QtCameraAdapter
from app.platform.raspberry_pi_camera_adapter import RaspberryPiCameraAdapter
from app.platform.usb_camera_adapter import UsbCameraAdapter
from app.services.qt_camera_session import QtCameraSession
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class CameraService:
    def __init__(self, paths: AppPaths, settings: SettingsService) -> None:
        self._paths = paths
        self._settings = settings
        self._pi = RaspberryPiCameraAdapter()
        self._usb = UsbCameraAdapter()                       # legacy ffmpeg path
        self._qt_usb: QtCameraAdapter | None = None          # populated after QGuiApplication
        self._active = None  # currently running adapter

    def attach_qt_camera_session(self, session: QtCameraSession) -> None:
        """Inject the Qt camera session after QGuiApplication exists.

        QMediaCaptureSession requires QGuiApplication, so we can't construct
        the adapter at module-init time.  Called from main.py once the Qt
        app is up.
        """
        self._qt_usb = QtCameraAdapter(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_recording(self) -> CameraPreview:
        self._stop_any(discard=True)
        adapter = self._pick()
        self._active = adapter
        return adapter.start_recording(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device") or None,
        )

    def start_preview_only(self) -> CameraPreview:
        """Used by Live Compare — needs a stream URL the mirror MediaPlayer
        can render alongside the saved video.  Always use the legacy adapters
        (ffmpeg → UDP) for this; the Qt camera path produces frames via
        QVideoSink which the compare-mode QML can't consume.
        """
        self._stop_any(discard=True)
        adapter = self._pick(prefer_url_stream=True)
        self._active = adapter
        return adapter.start_preview(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device") or None,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        capture = self._stop_any(discard=discard)
        return capture

    def is_active(self) -> bool:
        return self._active is not None

    def is_alive(self) -> bool:
        """Return True if the active camera subprocess is still running."""
        if self._active is None:
            return False
        return self._active.is_alive()

    def available_backends(self) -> list[dict[str, object]]:
        return [
            {"key": "auto",         "label": "Auto detect",          "available": self._pi.is_available() or self._usb.is_available()},
            {"key": "raspberry_pi", "label": "Raspberry Pi camera",   "available": self._pi.is_available()},
            {"key": "usb",          "label": "USB webcam",            "available": self._usb.is_available()},
        ]

    def current_backend_label(self) -> str:
        adapter = self._active or self._pick(raise_on_missing=False)
        if adapter is None:
            return "No camera"
        return adapter.backend_name

    def dependencies_ok(self) -> dict[str, bool]:
        return {
            "rpicam-vid": shutil.which("rpicam-vid") is not None,
            "ffmpeg":     shutil.which("ffmpeg")     is not None,
            "ffprobe":    shutil.which("ffprobe")    is not None,
        }

    def backends_status(self) -> dict[str, bool]:
        """Check which camera backends are actually working (not just installed)."""
        return {
            "Pi camera (CSI)": self._pi.is_available(),
            "USB webcam":      self._usb.is_available(),
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _stop_any(self, discard: bool) -> CompletedCapture | None:
        if self._active is None:
            return None
        result = self._active.stop(discard=discard)
        self._active = None
        return result

    def _pick(self, raise_on_missing: bool = True, prefer_url_stream: bool = False):
        """Choose adapter.

        - USB recording (low latency): prefer Qt's QMediaCaptureSession path
        - USB live_compare / preview: needs URL stream → always legacy ffmpeg
        - Pi camera: rpicam-vid in both cases
        - Override with camera_backend = "usb_ffmpeg" to force legacy on USB
        """
        pref = str(self._settings.get("camera_backend", "auto"))
        usb_qt_ready = self._qt_usb is not None and not prefer_url_stream

        if pref == "raspberry_pi" and self._pi.is_available():
            return self._pi
        if pref == "usb_ffmpeg" and self._usb.is_available():
            return self._usb
        if pref == "usb" and self._usb.is_available():
            return self._qt_usb if usb_qt_ready else self._usb
        # auto
        if self._pi.is_available():
            return self._pi
        if self._usb.is_available():
            return self._qt_usb if usb_qt_ready else self._usb
        if raise_on_missing:
            raise RuntimeError(
                "No camera backend available. "
                "Connect a USB webcam or ensure rpicam-vid is installed."
            )
        return None
