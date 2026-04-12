"""Gallery — video listing and deletion."""
from __future__ import annotations

from pathlib import Path

from app.database.repositories import VideoRepository
from app.models.entities import VideoRecord


class GalleryService:
    def __init__(self, repository: VideoRepository) -> None:
        self._repo = repository

    def list_videos(self, session_id: str | None = None) -> list[VideoRecord]:
        return self._repo.list_videos(session_id=session_id)

    def get_video(self, video_id: str) -> VideoRecord | None:
        return self._repo.get_video(video_id)

    def delete_video(self, video_id: str) -> VideoRecord | None:
        record = self._repo.delete_video(video_id)
        if record:
            Path(record.file_path).unlink(missing_ok=True)
            if record.thumbnail_path:
                Path(record.thumbnail_path).unlink(missing_ok=True)
        return record

    def count_videos(self, session_id: str | None = None) -> int:
        return self._repo.count_videos(session_id=session_id)
