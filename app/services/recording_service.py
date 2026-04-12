from __future__ import annotations

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
        self._repository = repository
        self._session_service = session_service

    def prepare_review(self, capture: CompletedCapture) -> PreparedRecording:
        if capture.file_format == "mp4":
            return PreparedRecording(file_path=capture.file_path, backend=capture.backend)
        if capture.file_format != "h264":
            raise RuntimeError(f"Unsupported capture format: {capture.file_format}")
        review_path = self._paths.temp_dir / f"{capture.file_path.stem}.mp4"
        remux_h264_to_mp4(
            capture.file_path,
            review_path,
            int(self._settings.get("camera_fps", 30)),
        )
        safe_unlink(capture.file_path)
        return PreparedRecording(file_path=review_path, backend=capture.backend)

    def save_prepared(self, recording: PreparedRecording) -> VideoRecord:
        session = self._session_service.ensure_active_session()
        sequence = self._repository.count_videos(session.id) + 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = self._paths.videos_dir / f"{timestamp}_look_{sequence:03d}.mp4"
        shutil.move(str(recording.file_path), destination)
        thumbnail_path = self._paths.thumbnails_dir / f"{destination.stem}.jpg"
        duration = probe_duration(destination)
        width, height = probe_dimensions(destination)
        try:
            generate_thumbnail(destination, thumbnail_path)
            thumbnail = str(thumbnail_path)
        except Exception:  # noqa: BLE001
            thumbnail = None
        return self._repository.create_video(
            session_id=session.id,
            title=f"Look {sequence}",
            file_path=str(destination),
            thumbnail_path=thumbnail,
            duration_seconds=duration,
            camera_backend=recording.backend,
            width=width,
            height=height,
        )

    def discard_prepared(self, recording: PreparedRecording | None) -> None:
        if recording is not None:
            safe_unlink(recording.file_path)
