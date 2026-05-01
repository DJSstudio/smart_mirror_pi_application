"""Playback service — orchestrates video playback and mirror display for gallery workflows."""
from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.config.paths import AppPaths
from app.media.ffmpeg_tools import combine_vstack, safe_unlink
from app.models.entities import VideoRecord
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class PlaybackService(QObject):
    """Exposed to QML as `playbackService`.

    Tracks the current playback session (mode + sources) and keeps
    MirrorDisplayService in sync.
    """

    changed = Signal()

    # Emitted when an async compare-combine job finishes (success or error).
    compareReady = Signal()

    def __init__(
        self,
        *,
        camera_service: CameraService,
        mirror_display: MirrorDisplayService,
        settings: SettingsService,
        paths: AppPaths,
    ) -> None:
        super().__init__()
        self._camera = camera_service
        self._mirror = mirror_display
        self._paths = paths
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._primary_video_id = ""
        self._compare_temp_path: Path | None = None
        self._compare_pending = False
        self._compare_error = ""

    # ------------------------------------------------------------------
    # QML-readable properties
    # ------------------------------------------------------------------

    @Property(str, notify=changed)
    def mode(self) -> str:
        return self._mode

    @Property(str, notify=changed)
    def primarySource(self) -> str:
        return self._primary_source

    @Property(str, notify=changed)
    def secondarySource(self) -> str:
        return self._secondary_source

    @Property(str, notify=changed)
    def primaryLabel(self) -> str:
        return self._primary_label

    @Property(str, notify=changed)
    def secondaryLabel(self) -> str:
        return self._secondary_label

    @Property(str, notify=changed)
    def currentVideoId(self) -> str:
        return self._primary_video_id

    @Property(bool, notify=compareReady)
    def comparePending(self) -> bool:
        return self._compare_pending

    @Property(str, notify=compareReady)
    def compareError(self) -> str:
        return self._compare_error

    # ------------------------------------------------------------------
    # Actions — decorated as @Slot so QML can call them directly
    # ------------------------------------------------------------------

    @Slot()
    def close_active(self) -> None:
        """Stop any active playback and return mirror to idle/black."""
        if self._mode == "live_compare":
            self._camera.stop(discard=True)
        # Delete the compare temp file we generated for this session.
        if self._compare_temp_path is not None:
            safe_unlink(self._compare_temp_path)
            self._compare_temp_path = None
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._primary_video_id = ""
        self._compare_pending = False
        self._compare_error = ""
        self._mirror.show_idle_black()
        self.changed.emit()
        self.compareReady.emit()

    # ------------------------------------------------------------------
    # Called by GalleryController (Python-to-Python, Slot not strictly
    # required but added for completeness)
    # ------------------------------------------------------------------

    def open_video(self, video: VideoRecord) -> None:
        url = str(video.to_dict()["sourceUrl"])
        self._mode = "video"
        self._primary_source = url
        self._secondary_source = ""
        self._primary_label = video.title
        self._secondary_label = ""
        self._primary_video_id = video.id
        self._mirror.show_video(url)
        self.changed.emit()

    def open_compare(self, left: VideoRecord, right: VideoRecord) -> None:
        """Combine two videos into a single vstacked file, then play it.

        Why combine: the Pi 4 has only one hardware H.264 decoder, so playing
        two streams simultaneously causes one to fall back to software and
        stutter.  Pre-combining means the mirror does just ONE decode.
        """
        # Show "preparing…" state on the control screen while ffmpeg runs.
        self._mode = "compare"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = left.title
        self._secondary_label = right.title
        self._compare_pending = True
        self._compare_error = ""
        self.changed.emit()
        self.compareReady.emit()

        left_path = Path(left.file_path)
        right_path = Path(right.file_path)
        out_path = self._paths.temp_dir / f"compare_{uuid.uuid4().hex}.mp4"

        def _bg() -> None:
            try:
                combine_vstack(left_path, right_path, out_path)
                self._compare_temp_path = out_path
                url = out_path.resolve().as_uri()
                self._primary_source = url
                self._compare_pending = False
                self._mirror.show_video(url)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Compare combine failed: %s", exc)
                safe_unlink(out_path)
                self._compare_pending = False
                self._compare_error = f"Could not prepare comparison: {exc}"
            self.changed.emit()
            self.compareReady.emit()

        threading.Thread(target=_bg, daemon=True).start()

    def open_live_compare(self, video: VideoRecord) -> None:
        preview   = self._camera.start_preview_only()
        video_url = str(video.to_dict()["sourceUrl"])
        self._mode = "live_compare"
        self._primary_source = video_url
        self._secondary_source = preview.control_preview_url
        self._primary_label = video.title
        self._secondary_label = "Live"
        self._mirror.show_live_compare(video_url, preview.mirror_preview_url)
        self.changed.emit()
