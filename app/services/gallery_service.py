from __future__ import annotations

from pathlib import Path

from app.database.repositories import VideoRepository
from app.models.entities import VideoRecord


class GalleryService:
    def __init__(self, repository: VideoRepository) -> None:
        self._repository = repository

    def list_videos(self, session_id: str | None = None) -> list[VideoRecord]:
        return self._repository.list_videos(session_id=session_id)

    def get_video(self, video_id: str) -> VideoRecord | None:
        return self._repository.get_video(video_id)

    def delete_video(self, video_id: str) -> VideoRecord | None:
        return self._repository.delete_video(video_id)

    def count_videos(self, session_id: str | None = None) -> int:
        return self._repository.count_videos(session_id=session_id)

    @staticmethod
    def delete_video_files(video: VideoRecord) -> None:
        Path(video.file_path).unlink(missing_ok=True)
        if video.thumbnail_path:
            Path(video.thumbnail_path).unlink(missing_ok=True)
