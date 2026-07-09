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

# Minimum free space required before allowing a new recording.
# At 8 Mbps (default bitrate) this gives ~8 minutes of headroom.
_MIN_FREE_BYTES = 500 * 1024 * 1024  # 500 MB


class CameraService:
    def __init__(self, paths: AppPaths, settings: SettingsService) -> None:
        self._paths = paths
        self._settings = settings
        self._pi = RaspberryPiCameraAdapter()
        self._usb = UsbCameraAdapter()                  # legacy ffmpeg+UDP fallback
        self._qt_usb: QtCameraAdapter | None = None     # default USB path (QCamera + ffmpeg-pipe)
        self._active = None

    def attach_qt_camera_session(self, session: QtCameraSession) -> None:
        """Inject the Qt camera session after QGuiApplication exists."""
        self._qt_usb = QtCameraAdapter(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_recording(self) -> CameraPreview:
        self._check_disk_space()
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
            mirror_flip=bool(self._settings.get("camera_mirror_flip", False)),
            mirror_orientation_degrees=int(self._settings.get("mirror_orientation_degrees", 0)),
        )

    def start_preview_only(self) -> CameraPreview:
        """Open the camera for preview-only (no recording).  Used by Live
        Compare.  Routes through the same adapter as recording — for USB
        that's the Qt path (QCamera → QVideoSink), so the live half of
        Live Compare gets the same low-latency rendering as the main
        recording flow.  Mirror's liveCompareComp uses VideoOutput +
        attachSink for the live pane (no URL needed).
        """
        # Disk guard on the DEFAULT recording path: normal recording uses the
        # deferred flow (start_preview_only warmup → begin_writing_file), and
        # Live Compare can hit "Record Live".  Both ultimately write to disk, so
        # gate here — start_recording() (the legacy/fallback path) checks too.
        # Both callers surface a raised RuntimeError cleanly (recording_controller
        # falls back to start_recording which re-checks; gallery_controller's
        # liveCompareSelected wraps this in try/except → showError).
        self._check_disk_space()
        self._stop_any(discard=True)
        adapter = self._pick()
        self._active = adapter
        return adapter.start_preview(
            work_dir=self._paths.temp_dir,
            width=int(self._settings.get("camera_width", 1280)),
            height=int(self._settings.get("camera_height", 720)),
            fps=int(self._settings.get("camera_fps", 30)),
            bitrate=int(self._settings.get("camera_bitrate", 8_000_000)),
            device_hint=self._settings.get("camera_device") or None,
            mirror_flip=bool(self._settings.get("camera_mirror_flip", False)),
            mirror_orientation_degrees=int(self._settings.get("mirror_orientation_degrees", 0)),
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        capture = self._stop_any(discard=discard)
        return capture

    def supports_deferred_recording(self) -> bool:
        """True if the selected backend supports the preview→record split
        (start_preview_only warmup, then begin_writing_file at T=0).

        Only the USB QCamera adapter does.  The Pi CSI and legacy ffmpeg
        adapters MUST record from the start via start_recording() — for them,
        start_preview_only() opens a preview that writes NO capture file, so if
        the controller took the deferred path it would reach Stop with nothing
        to save ("no file was produced").  The controller calls this up front to
        pick the right path, because start_preview_only() succeeds (doesn't
        raise) on those adapters and so can't be used to detect support.
        """
        adapter = self._active or self._pick(raise_on_missing=False)
        return adapter is not None and hasattr(adapter, "begin_writing_file")

    def begin_writing_file(self) -> bool:
        """Switch the active adapter from preview-only to recording.  Used
        by recording_controller's deferred-recording flow: opens camera
        early for warmup, then begins file recording when countdown ends.
        Returns True if the adapter supports deferred recording AND the
        camera is currently in preview mode; False otherwise (caller
        should fall back to start_recording).
        """
        if self._active is None:
            return False
        if not hasattr(self._active, "begin_writing_file"):
            return False
        path = self._active.begin_writing_file(self._paths.temp_dir)
        return path is not None

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

    def _check_disk_space(self) -> None:
        """Raise RuntimeError if the data directory has less than _MIN_FREE_BYTES free."""
        try:
            free = shutil.disk_usage(self._paths.data_dir).free
        except OSError as exc:
            LOGGER.warning("Could not check disk space: %s", exc)
            return  # non-fatal: let recording proceed
        if free < _MIN_FREE_BYTES:
            free_mb = free // (1024 * 1024)
            needed_mb = _MIN_FREE_BYTES // (1024 * 1024)
            raise RuntimeError(
                f"Not enough disk space to record — {free_mb} MB free, "
                f"{needed_mb} MB required. Free up space and try again."
            )
        LOGGER.debug("Disk space OK: %d MB free", free // (1024 * 1024))

    def _stop_any(self, discard: bool) -> CompletedCapture | None:
        if self._active is None:
            return None
        result = self._active.stop(discard=discard)
        self._active = None
        return result

    def _pick(self, raise_on_missing: bool = True):
        """Choose camera adapter.

        Decision tree for USB:
          - "usb" / "auto"  → QtCameraAdapter (QCamera preview + ffmpeg-pipe recording)
          - "usb_ffmpeg"    → legacy ffmpeg+UDP+MediaPlayer (laggy fallback)
        Used by both recording and Live Compare; the Qt path now renders
        the live pane in QML via VideoOutput so Live Compare benefits from
        the same low-latency preview as recording.
        """
        pref = str(self._settings.get("camera_backend", "auto"))
        qt_ready = self._qt_usb is not None

        if pref == "raspberry_pi" and self._pi.is_available():
            return self._pi
        if pref == "usb_ffmpeg" and self._usb.is_available():
            return self._usb
        if pref in ("usb", "usb_qt"):
            if qt_ready:
                return self._qt_usb
            if self._usb.is_available():
                return self._usb
        # auto
        if self._pi.is_available():
            return self._pi
        if qt_ready:
            return self._qt_usb
        if self._usb.is_available():
            return self._usb
        if raise_on_missing:
            raise RuntimeError(
                "No camera backend available. "
                "Connect a USB webcam or ensure rpicam-vid is installed."
            )
        return None
