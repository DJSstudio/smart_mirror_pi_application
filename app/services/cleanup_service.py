"""Auto-delete service for expired session data.

Deletes video files and DB records for sessions whose last activity
(last logout, or last login if never logged out, or session start time)
is older than a configurable threshold. The session row and all footfall
rows are kept — footfall is the permanent record. Footfall rows are
stamped with data_deleted_at, and the session row gets purged_at.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.database.connection import DatabaseManager
from app.database.repositories import VideoRepository

LOGGER = logging.getLogger(__name__)

# Temp capture files older than this are considered abandoned and swept.
# A live recording keeps its file's mtime fresh (ffmpeg writes continuously),
# so anything this stale cannot be an in-flight capture.
_TEMP_STALE_MINUTES = 30.0


class CleanupService:
    def __init__(
        self,
        *,
        db: DatabaseManager,
        video_repo: VideoRepository,
        temp_dir: Path | None = None,
    ) -> None:
        self._db = db
        self._video_repo = video_repo
        self._temp_dir = temp_dir

    def run(self, older_than_hours: float = 1.0) -> int:
        """Delete video data for sessions inactive longer than *older_than_hours*.

        A session is eligible when:
        - It is not currently active (active = 0)
        - It has not already been purged (purged_at IS NULL)
        - Its last activity timestamp is older than the threshold.

        Last activity = MAX(footfall.logout_at) if any logout exists,
                        else MAX(footfall.login_at) if any login exists,
                        else sessions.started_at.

        Returns the number of sessions cleaned up.
        """
        threshold = (
            datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        ).isoformat()

        rows = self._db.connection.execute(
            """
            SELECT s.id   AS session_id,
                   s.name AS session_name,
                   COALESCE(
                       MAX(f.logout_at),
                       MAX(f.login_at),
                       s.started_at
                   )      AS last_activity
            FROM sessions s
            LEFT JOIN footfall f ON f.session_id = s.id
            WHERE s.active = 0
              AND s.purged_at IS NULL
            GROUP BY s.id
            HAVING last_activity < ?
            """,
            (threshold,),
        ).fetchall()

        cleaned = 0
        for row in rows:
            session_id = str(row["session_id"])
            session_name = str(row["session_name"])
            last_activity = str(row["last_activity"])
            LOGGER.info(
                "Auto-cleanup: purging session %s (%s), last activity: %s",
                session_id[:8], session_name, last_activity,
            )
            try:
                self._purge_session(session_id)
                cleaned += 1
            except Exception as exc:  # noqa: BLE001
                LOGGER.error(
                    "Auto-cleanup: failed for session %s: %s", session_id[:8], exc
                )

        if cleaned:
            LOGGER.info("Auto-cleanup: purged %d session(s)", cleaned)
        else:
            LOGGER.debug("Auto-cleanup: nothing to purge (threshold: %s)", threshold)

        # Sweep abandoned temp capture files (orphaned by crash/power-cut
        # mid-recording, or an abandoned review).  Runs every cleanup cycle.
        self._sweep_temp_dir()

        return cleaned

    def _sweep_temp_dir(self, older_than_minutes: float = _TEMP_STALE_MINUTES) -> int:
        """Delete stale capture_* files from temp_dir.

        Captures are normally removed on a clean stop/save/discard, but a
        crash or power-cut mid-recording leaves them behind, and nothing else
        ever sweeps temp_dir (login QRs self-clean separately).  Over weeks
        these fill the SD card, eventually tripping the recording disk-guard
        and blocking all recording.  Files whose mtime is older than the
        threshold cannot be an in-flight recording, so they're safe to delete.

        Pattern ``capture_*`` covers every variant: capture_qcam_*.mp4,
        capture_lc_*.mp4, capture_<pid>_<port>.h264, the remuxed .mp4, and
        the *_trimmed.mp4 intermediates (all share the capture_ prefix).
        """
        if self._temp_dir is None or not self._temp_dir.exists():
            return 0
        cutoff = time.time() - older_than_minutes * 60
        swept = 0
        for path in self._temp_dir.glob("capture_*"):
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
                    swept += 1
                    LOGGER.info("Auto-cleanup: removed stale temp capture %s", path.name)
            except OSError as exc:
                LOGGER.warning("Auto-cleanup: could not remove temp file %s: %s", path, exc)
        if swept:
            LOGGER.info("Auto-cleanup: swept %d stale temp capture file(s)", swept)
        return swept

    def _purge_session(self, session_id: str) -> None:
        """Delete all video files and DB rows for *session_id*.

        Footfall rows are kept but stamped with data_deleted_at.
        The session row is kept (to preserve footfall FK) but stamped with purged_at.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Collect video records before deleting from DB.
        videos = self._video_repo.list_videos(session_id=session_id)

        # 2. Delete video files and thumbnails from disk.
        for video in videos:
            self._delete_file(video.file_path)
            self._delete_file(video.thumbnail_path)

        with self._db.transaction() as conn:
            # 3. Delete video rows from DB.
            conn.execute("DELETE FROM videos WHERE session_id=?", (session_id,))

            # 4. Stamp footfall rows — data is gone, record remains.
            conn.execute(
                """
                UPDATE footfall
                   SET data_deleted_at = ?
                 WHERE session_id = ? AND data_deleted_at IS NULL
                """,
                (now, session_id),
            )

            # 5. Mark the session as purged — keeps the row for footfall FK integrity.
            conn.execute(
                "UPDATE sessions SET purged_at = ? WHERE id = ?",
                (now, session_id),
            )
            conn.commit()

        LOGGER.info(
            "Auto-cleanup: deleted %d video(s) for session %s",
            len(videos), session_id[:8],
        )

    @staticmethod
    def _delete_file(path: str | None) -> None:
        if not path:
            return
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
                LOGGER.debug("Auto-cleanup: deleted file %s", p)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Auto-cleanup: could not delete file %s: %s", path, exc)
