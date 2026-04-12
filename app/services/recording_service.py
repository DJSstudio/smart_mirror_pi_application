"""Recording lifecycle — prepare-for-review, save, discard."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from app.config.paths import AppPaths
from app.database.repositories import VideoRepository
from app.media.ffmpeg_tools import (
    generate_thumbnail,
    probe_dimensions,
    probe_duration,
    remux_h264_to_mp4,
    safe_unlink,
)
from app.models.entities import CompletedCapture, PreparedRecording, VideoRecord
from app.services.session_service import SessionService
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class RecordingService:
    def __init__(
        self,
        *,
        paths: AppPaths,
        settings: SettingsService,
        repository: VideoRepository,
        session_service: SessionService,
    ) -> None:
        self._paths = paths
        self._settings = settings
        self._repo = repository
        self._sessions = session_service

    def prepare_review(self, capture: CompletedCapture) -> PreparedRecording:
        """Ensure the capture is in MP4 format, ready for Qt playback."""
        if capture.file_format == "mp4":
            if not capture.file_path.exists() or capture.file_path.stat().st_size < 512:
                raise RuntimeError(
                    "No video data was captured. The camera may not be initialised — "
                    "enable it via raspi-config → Interface Options → Camera, then reboot."
                )
            return PreparedRecording(file_path=capture.file_path, backend=capture.backend)

        if capture.file_format == "h264":
            if not capture.file_path.exists() or capture.file_path.stat().st_size < 512:
                raise RuntimeError(
                    "No video data was captured. The camera may not be initialised — "
                    "enable it via raspi-config → Interface Options → Camera, then reboot."
                )
            fps = int(self._settings.get("camera_fps", 30))
            mp4_path = capture.file_path.with_suffix(".mp4")
            LOGGER.info("Remuxing H.264 → MP4: %s → %s", capture.file_path, mp4_path)
            try:
                remux_h264_to_mp4(capture.file_path, mp4_path, fps)
            except Exception as exc:  # noqa: BLE001
                safe_unlink(capture.file_path)
                raise RuntimeError(f"Failed to process recording: {exc}") from exc
            safe_unlink(capture.file_path)
            return PreparedRecording(file_path=mp4_path, backend=capture.backend)

        raise RuntimeError(f"Unsupported capture format: {capture.file_format}")

    def save_prepared(self, recording: PreparedRecording) -> VideoRecord:
        session = self._sessions.ensure_active_session()
        sequence = self._repo.count_videos(session.id) + 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self._paths.videos_dir / f"{ts}_look_{sequence:03d}.mp4"
        shutil.move(str(recording.file_path), dest)

        thumb_path = self._paths.thumbnails_dir / f"{dest.stem}.jpg"
        duration = probe_duration(dest)
        width, height = probe_dimensions(dest)

        thumbnail: str | None = None
        try:
            generate_thumbnail(dest, thumb_path)
            thumbnail = str(thumb_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Thumbnail generation failed: %s", exc)

        return self._repo.create_video(
            session_id=session.id,
            title=f"Look {sequence}",
            file_path=str(dest),
            thumbnail_path=thumbnail,
            duration_seconds=duration,
            camera_backend=recording.backend,
            width=width,
            height=height,
        )

    def discard_prepared(self, recording: PreparedRecording | None) -> None:
        if recording is not None:
            safe_unlink(recording.file_path)
