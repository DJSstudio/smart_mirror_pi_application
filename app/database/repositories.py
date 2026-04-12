"""Data-access repositories."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.database.connection import DatabaseManager
from app.models.entities import SessionRecord, VideoRecord


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class SessionRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def create_session(self, name: str, device_id: str = "") -> SessionRecord:
        sid = str(uuid.uuid4())
        now = _now_iso()
        conn = self._db.connection
        conn.execute("UPDATE sessions SET active=0, ended_at=? WHERE active=1", (now,))
        conn.execute(
            "INSERT INTO sessions (id, name, started_at, active, device_id) VALUES (?,?,?,1,?)",
            (sid, name, now, device_id),
        )
        conn.commit()
        return self.get_active_session()  # type: ignore[return-value]

    def get_active_session(self) -> SessionRecord | None:
        row = self._db.connection.execute(
            "SELECT * FROM sessions WHERE active=1 ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return _row_to_session(row) if row else None

    def get_latest_session_for_device(self, device_id: str) -> SessionRecord | None:
        """Return the most recent session that belongs to *device_id*."""
        row = self._db.connection.execute(
            "SELECT * FROM sessions WHERE device_id=? ORDER BY started_at DESC LIMIT 1",
            (device_id,),
        ).fetchone()
        return _row_to_session(row) if row else None

    def activate_session(self, session_id: str, device_id: str) -> SessionRecord | None:
        """Make *session_id* the active session and claim it for *device_id*.

        Any currently active sessions (other than *session_id*) are ended.
        """
        conn = self._db.connection
        now = _now_iso()
        conn.execute(
            "UPDATE sessions SET active=0, ended_at=? WHERE active=1 AND id!=?",
            (now, session_id),
        )
        conn.execute(
            "UPDATE sessions SET active=1, ended_at=NULL, device_id=? WHERE id=?",
            (device_id, session_id),
        )
        conn.commit()
        return self.get_active_session()

    def claim_current_session(self, device_id: str) -> None:
        """Stamp *device_id* onto the active session if it has no owner yet."""
        self._db.connection.execute(
            "UPDATE sessions SET device_id=? WHERE active=1 AND (device_id IS NULL OR device_id='')",
            (device_id,),
        )
        self._db.connection.commit()

    def list_sessions(self, limit: int = 20) -> list[SessionRecord]:
        rows = self._db.connection.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_session(r) for r in rows]

    def count_sessions(self) -> int:
        row = self._db.connection.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        return int(row["n"]) if row else 0

    def end_session(self, session_id: str) -> None:
        conn = self._db.connection
        conn.execute(
            "UPDATE sessions SET active=0, ended_at=? WHERE id=?", (_now_iso(), session_id)
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

class VideoRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def create_video(
        self,
        *,
        session_id: str,
        title: str,
        file_path: str,
        thumbnail_path: str | None,
        duration_seconds: float | None,
        camera_backend: str,
        notes: str = "",
        width: int | None = None,
        height: int | None = None,
    ) -> VideoRecord:
        vid = str(uuid.uuid4())
        now = _now_iso()
        self._db.connection.execute(
            """
            INSERT INTO videos
              (id, session_id, title, file_path, thumbnail_path,
               duration_seconds, created_at, camera_backend, notes, width, height)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (vid, session_id, title, file_path, thumbnail_path,
             duration_seconds, now, camera_backend, notes, width, height),
        )
        self._db.connection.commit()
        return self.get_video(vid)  # type: ignore[return-value]

    def get_video(self, video_id: str) -> VideoRecord | None:
        row = self._db.connection.execute(
            "SELECT * FROM videos WHERE id=? LIMIT 1", (video_id,)
        ).fetchone()
        return _row_to_video(row) if row else None

    def list_videos(self, session_id: str | None = None) -> list[VideoRecord]:
        if session_id:
            rows = self._db.connection.execute(
                "SELECT * FROM videos WHERE session_id=? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        else:
            rows = self._db.connection.execute(
                "SELECT * FROM videos ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_video(r) for r in rows]

    def delete_video(self, video_id: str) -> VideoRecord | None:
        record = self.get_video(video_id)
        if record is None:
            return None
        self._db.connection.execute("DELETE FROM videos WHERE id=?", (video_id,))
        self._db.connection.commit()
        return record

    def count_videos(self, session_id: str | None = None) -> int:
        if session_id:
            row = self._db.connection.execute(
                "SELECT COUNT(*) AS n FROM videos WHERE session_id=?", (session_id,)
            ).fetchone()
        else:
            row = self._db.connection.execute(
                "SELECT COUNT(*) AS n FROM videos"
            ).fetchone()
        return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _row_to_session(row) -> SessionRecord:
    return SessionRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        started_at=str(row["started_at"]),
        ended_at=row["ended_at"],
        active=bool(row["active"]),
        device_id=str(row["device_id"] or ""),
    )


def _row_to_video(row) -> VideoRecord:
    return VideoRecord(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        title=str(row["title"]),
        file_path=str(row["file_path"]),
        thumbnail_path=row["thumbnail_path"],
        duration_seconds=row["duration_seconds"],
        created_at=str(row["created_at"]),
        camera_backend=str(row["camera_backend"]),
        notes=str(row["notes"]),
        width=row["width"],
        height=row["height"],
    )
