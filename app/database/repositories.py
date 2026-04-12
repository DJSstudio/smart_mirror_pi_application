from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable

from app.database.connection import DatabaseManager
from app.models.entities import SessionRecord, VideoRecord


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def create_session(self, name: str) -> SessionRecord:
        session_id = str(uuid.uuid4())
        stamp = _utc_now_iso()
        connection = self._database.connection
        connection.execute("UPDATE sessions SET active = 0, ended_at = ? WHERE active = 1", (stamp,))
        connection.execute(
            """
            INSERT INTO sessions (id, name, started_at, ended_at, active)
            VALUES (?, ?, ?, NULL, 1)
            """,
            (session_id, name, stamp),
        )
        connection.commit()
        return self.get_active_session()  # type: ignore[return-value]

    def get_active_session(self) -> SessionRecord | None:
        row = self._database.connection.execute(
            """
            SELECT id, name, started_at, ended_at, active
            FROM sessions
            WHERE active = 1
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
        return _row_to_session(row) if row else None

    def list_sessions(self, limit: int = 10) -> list[SessionRecord]:
        rows = self._database.connection.execute(
            """
            SELECT id, name, started_at, ended_at, active
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_session(row) for row in rows]

    def count_sessions(self) -> int:
        row = self._database.connection.execute(
            "SELECT COUNT(*) AS total FROM sessions"
        ).fetchone()
        return int(row["total"]) if row else 0


class VideoRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

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
        video_id = str(uuid.uuid4())
        created_at = _utc_now_iso()
        connection = self._database.connection
        connection.execute(
            """
            INSERT INTO videos (
                id,
                session_id,
                title,
                file_path,
                thumbnail_path,
                duration_seconds,
                created_at,
                camera_backend,
                notes,
                width,
                height
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                session_id,
                title,
                file_path,
                thumbnail_path,
                duration_seconds,
                created_at,
                camera_backend,
                notes,
                width,
                height,
            ),
        )
        connection.commit()
        return self.get_video(video_id)  # type: ignore[return-value]

    def list_videos(self, session_id: str | None = None) -> list[VideoRecord]:
        query = (
            "SELECT * FROM videos WHERE session_id = ? ORDER BY created_at DESC"
            if session_id
            else "SELECT * FROM videos ORDER BY created_at DESC"
        )
        rows = (
            self._database.connection.execute(query, (session_id,)).fetchall()
            if session_id
            else self._database.connection.execute(query).fetchall()
        )
        return [_row_to_video(row) for row in rows]

    def get_video(self, video_id: str) -> VideoRecord | None:
        row = self._database.connection.execute(
            "SELECT * FROM videos WHERE id = ? LIMIT 1",
            (video_id,),
        ).fetchone()
        return _row_to_video(row) if row else None

    def delete_video(self, video_id: str) -> VideoRecord | None:
        record = self.get_video(video_id)
        if record is None:
            return None
        self._database.connection.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        self._database.connection.commit()
        return record

    def count_videos(self, session_id: str | None = None) -> int:
        row = (
            self._database.connection.execute(
                "SELECT COUNT(*) AS total FROM videos WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session_id
            else self._database.connection.execute(
                "SELECT COUNT(*) AS total FROM videos"
            ).fetchone()
        )
        return int(row["total"]) if row else 0

    def list_titles(self, session_id: str) -> Iterable[str]:
        rows = self._database.connection.execute(
            "SELECT title FROM videos WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        for row in rows:
            yield str(row["title"])


def _row_to_session(row) -> SessionRecord:
    return SessionRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        started_at=str(row["started_at"]),
        ended_at=row["ended_at"],
        active=bool(row["active"]),
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
