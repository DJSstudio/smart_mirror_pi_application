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
    trim_mp4,
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

    def prepare_review(
        self, capture: CompletedCapture, trim_start: float = 0.0
    ) -> PreparedRecording:
        """Ensure the capture is in MP4 format, ready for Qt playback.

        trim_start — seconds to drop from the beginning of the raw file.
        Used to remove the camera warm-up period recorded during countdown.
        """
        if capture.file_format == "mp4":
            if not capture.file_path.exists() or capture.file_path.stat().st_size < 512:
                raise RuntimeError(
                    "No video data was captured. "
                    "If using the Pi camera, enable it via raspi-config → Interface Options → Camera and reboot. "
                    "You can also switch to the USB backend in Settings."
                )
            if trim_start > 0:
                trimmed = capture.file_path.parent / (
                    capture.file_path.stem + "_trimmed.mp4"
                )
                LOGGER.info("Trimming %.1fs warmup from %s", trim_start, capture.file_path)
                try:
                    trim_mp4(capture.file_path, trimmed, trim_start)
                except Exception as exc:  # noqa: BLE001
                    safe_unlink(trimmed)
                    raise RuntimeError(f"Failed to trim recording: {exc}") from exc
                safe_unlink(capture.file_path)
                return PreparedRecording(file_path=trimmed, backend=capture.backend)
            return PreparedRecording(file_path=capture.file_path, backend=capture.backend)

        if capture.file_format == "h264":
            if not capture.file_path.exists() or capture.file_path.stat().st_size < 512:
                raise RuntimeError(
                    "No video data was captured. "
                    "If using the Pi camera, enable it via raspi-config → Interface Options → Camera and reboot. "
                    "You can also switch to the USB backend in Settings."
                )
            fps = int(self._settings.get("camera_fps", 30))
            mp4_path = capture.file_path.with_suffix(".mp4")
            LOGGER.info(
                "Remuxing H.264 → MP4 (trim=%.1fs): %s → %s",
                trim_start, capture.file_path, mp4_path,
            )
            try:
                remux_h264_to_mp4(capture.file_path, mp4_path, fps, trim_start=trim_start)
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
        src = recording.file_path
        dest = self._paths.videos_dir / f"{ts}_look_{sequence:03d}.mp4"
        thumb_path = self._paths.thumbnails_dir / f"{dest.stem}.jpg"

        # Probe + thumbnail on the SOURCE (still in temp).  If any of this
        # fails the source is untouched, so the controller's retry still
        # works and nothing is orphaned in videos_dir.
        duration = probe_duration(src)
        width, height = probe_dimensions(src)
        thumbnail: str | None = None
        try:
            generate_thumbnail(src, thumb_path)
            thumbnail = str(thumb_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Thumbnail generation failed: %s", exc)

        # Move into place, then create the DB row.  Previously the move
        # happened first, so a failed insert left an orphaned file in
        # videos_dir (cleanup only reclaims files it finds via DB rows) AND a
        # retry hit FileNotFoundError (source already moved away → clip lost).
        # Now, if the insert fails we move the file back so the source is
        # restored for a retry and nothing is orphaned.
        shutil.move(str(src), dest)
        try:
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
        except Exception:
            try:
                shutil.move(str(dest), str(src))  # roll back so retry works
            except Exception:  # noqa: BLE001
                LOGGER.exception("save_prepared: rollback move failed (file at %s)", dest)
            if thumbnail:
                safe_unlink(thumb_path)
            raise

    def discard_prepared(self, recording: PreparedRecording | None) -> None:
        if recording is not None:
            safe_unlink(recording.file_path)
