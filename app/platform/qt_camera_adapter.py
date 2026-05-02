"""USB camera adapter using Qt's QMediaCaptureSession.

Replaces the ffmpeg→UDP→MediaPlayer pipeline with a direct Qt camera path:
the same camera frames feed both the live preview (via QVideoSink → QML
VideoOutput) and the file recording (via QMediaRecorder).  No H.264
encode-decode round-trip for the preview, eliminating the ~500ms latency
the ffmpeg path introduced.

Returns ``mirror_preview_url=""`` because the mirror QML reads frames from
the QtCameraSession's videoSink directly, not from a stream URL.
"""
from __future__ import annotations

from pathlib import Path

from app.models.entities import CameraPreview, CompletedCapture
from app.platform.base_camera_adapter import BaseCameraAdapter
from app.services.qt_camera_session import QtCameraSession


class QtCameraAdapter(BaseCameraAdapter):
    backend_name = "usb_qt"

    def __init__(self, session: QtCameraSession) -> None:
        super().__init__()
        self._session = session
        self._capture_path: Path | None = None

    def is_available(self) -> bool:
        # We rely on QMediaDevices to find cameras; check at start time
        # (cheap there).  Returning True here lets CameraService include us
        # as a candidate; the real check happens when start_recording runs.
        return True

    def start_recording(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
    ) -> CameraPreview:
        cap_path = work_dir / f"capture_qcam_{id(self):x}.mp4"
        self._session.start_recording(
            device_hint=device_hint,
            width=width, height=height, fps=fps,
            bitrate=bitrate,
            output_path=cap_path,
        )
        self._capture_path = cap_path
        return CameraPreview(
            control_preview_url="",
            mirror_preview_url="",  # mirror reads videoSink directly
            backend=self.backend_name,
            recording=True,
        )

    def start_preview(
        self,
        *,
        work_dir: Path,
        width: int,
        height: int,
        fps: int,
        bitrate: int,
        device_hint: str | None,
    ) -> CameraPreview:
        self._session.start_preview(
            device_hint=device_hint,
            width=width, height=height, fps=fps,
        )
        self._capture_path = None
        return CameraPreview(
            control_preview_url="",
            mirror_preview_url="",
            backend=self.backend_name,
            recording=False,
        )

    def stop(self, discard: bool = False) -> CompletedCapture | None:
        recorded = self._session.stop()
        cap_path = self._capture_path
        self._capture_path = None

        if discard:
            if cap_path is not None:
                cap_path.unlink(missing_ok=True)
            return None

        # Use the path the session reports actually got written, falling back
        # to the path we asked for.
        final_path = recorded or cap_path
        if final_path is None or not final_path.exists():
            return None
        return CompletedCapture(
            file_path=final_path,
            file_format="mp4",
            backend=self.backend_name,
        )

    def is_alive(self) -> bool:
        return self._session.is_alive()
