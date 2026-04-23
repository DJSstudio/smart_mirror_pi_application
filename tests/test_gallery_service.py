"""Unit tests for GalleryService — pure Python, no DB or filesystem required."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.entities import VideoRecord
from app.services.gallery_service import GalleryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_video(
    id: str = "vid-1",
    session_id: str = "sess-1",
    file_path: str = "/tmp/test.mp4",
    thumbnail_path: str | None = "/tmp/test.jpg",
) -> VideoRecord:
    return VideoRecord(
        id=id,
        session_id=session_id,
        title="Look 1",
        file_path=file_path,
        thumbnail_path=thumbnail_path,
        duration_seconds=30.0,
        created_at="2024-01-01T12:00:00",
        camera_backend="usb",
        notes="",
        width=1920,
        height=1080,
    )


@pytest.fixture()
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def svc(repo: MagicMock) -> GalleryService:
    return GalleryService(repo)


# ---------------------------------------------------------------------------
# list_videos
# ---------------------------------------------------------------------------

class TestListVideos:
    def test_list_all_when_no_session_filter(self, svc: GalleryService, repo: MagicMock) -> None:
        videos = [_make_video(id=f"v{i}") for i in range(5)]
        repo.list_videos.return_value = videos

        result = svc.list_videos()

        assert result == videos
        repo.list_videos.assert_called_once_with(session_id=None)

    def test_list_filtered_by_session(self, svc: GalleryService, repo: MagicMock) -> None:
        videos = [_make_video(session_id="sess-2")]
        repo.list_videos.return_value = videos

        result = svc.list_videos(session_id="sess-2")

        assert result == videos
        repo.list_videos.assert_called_once_with(session_id="sess-2")


# ---------------------------------------------------------------------------
# get_video
# ---------------------------------------------------------------------------

class TestGetVideo:
    def test_returns_video_when_found(self, svc: GalleryService, repo: MagicMock) -> None:
        video = _make_video()
        repo.get_video.return_value = video

        result = svc.get_video("vid-1")

        assert result is video

    def test_returns_none_when_not_found(self, svc: GalleryService, repo: MagicMock) -> None:
        repo.get_video.return_value = None

        result = svc.get_video("does-not-exist")

        assert result is None


# ---------------------------------------------------------------------------
# delete_video
# ---------------------------------------------------------------------------

class TestDeleteVideo:
    def test_deletes_video_and_files(self, svc: GalleryService, repo: MagicMock) -> None:
        video = _make_video(file_path="/tmp/look.mp4", thumbnail_path="/tmp/look.jpg")
        repo.delete_video.return_value = video

        with patch("app.services.gallery_service.Path") as MockPath:
            mock_file = MagicMock()
            mock_thumb = MagicMock()
            MockPath.side_effect = lambda p: mock_file if "look.mp4" in p else mock_thumb

            result = svc.delete_video("vid-1")

        assert result is video
        repo.delete_video.assert_called_once_with("vid-1")
        mock_file.unlink.assert_called_once_with(missing_ok=True)
        mock_thumb.unlink.assert_called_once_with(missing_ok=True)

    def test_delete_returns_none_when_not_found(self, svc: GalleryService, repo: MagicMock) -> None:
        repo.delete_video.return_value = None

        result = svc.delete_video("ghost-id")

        assert result is None

    def test_delete_skips_thumbnail_unlink_when_none(
        self, svc: GalleryService, repo: MagicMock
    ) -> None:
        video = _make_video(thumbnail_path=None)
        repo.delete_video.return_value = video

        with patch.object(Path, "unlink") as mock_unlink:
            result = svc.delete_video("vid-1")

        assert result is video
        # Only one unlink call: the video file; thumbnail is None so skipped
        mock_unlink.assert_called_once_with(missing_ok=True)


# ---------------------------------------------------------------------------
# count_videos
# ---------------------------------------------------------------------------

class TestCountVideos:
    def test_count_all(self, svc: GalleryService, repo: MagicMock) -> None:
        repo.count_videos.return_value = 12

        assert svc.count_videos() == 12
        repo.count_videos.assert_called_once_with(session_id=None)

    def test_count_by_session(self, svc: GalleryService, repo: MagicMock) -> None:
        repo.count_videos.return_value = 3

        assert svc.count_videos(session_id="sess-1") == 3
        repo.count_videos.assert_called_once_with(session_id="sess-1")
