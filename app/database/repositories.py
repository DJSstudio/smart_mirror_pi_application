"""Data-access repositories."""
from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.database.connection import DatabaseManager
from app.models.entities import (
    FootfallEvent,
    SessionFootfallSummary,
    SessionRecord,
    VideoRecord,
)


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
        with self._db.transaction() as conn:
            conn.execute("UPDATE sessions SET active=0, ended_at=? WHERE active=1", (now,))
            conn.execute(
                "INSERT INTO sessions (id, name, started_at, active, device_id) VALUES (?,?,?,1,?)",
                (sid, name, now, device_id),
            )
            conn.commit()
        return self.get_active_session()  # type: ignore[return-value]

    def get_active_session(self) -> SessionRecord | None:
        # Locked: also called off-thread by the QR device-check callback.
        with self._db.reading() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE active=1 ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return _row_to_session(row) if row else None

    def get_latest_session_for_device(self, device_id: str) -> SessionRecord | None:
        """Return the most recent session that belongs to *device_id*."""
        # Locked: also called off-thread by the QR device-check callback.
        with self._db.reading() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE device_id=? ORDER BY started_at DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return _row_to_session(row) if row else None

    def activate_session(self, session_id: str, device_id: str) -> SessionRecord | None:
        """Make *session_id* the active session and claim it for *device_id*.

        Any currently active sessions (other than *session_id*) are ended.
        """
        now = _now_iso()
        with self._db.transaction() as conn:
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
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET device_id=? "
                "WHERE active=1 AND (device_id IS NULL OR device_id='')",
                (device_id,),
            )
            conn.commit()

    def list_sessions(self, limit: int = 20) -> list[SessionRecord]:
        rows = self._db.connection.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_session(r) for r in rows]

    def count_sessions(self) -> int:
        row = self._db.connection.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        return int(row["n"]) if row else 0

    def end_session(self, session_id: str) -> None:
        with self._db.transaction() as conn:
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
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO videos
                  (id, session_id, title, file_path, thumbnail_path,
                   duration_seconds, created_at, camera_backend, notes, width, height)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (vid, session_id, title, file_path, thumbnail_path,
                 duration_seconds, now, camera_backend, notes, width, height),
            )
            conn.commit()
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
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM videos WHERE id=? LIMIT 1", (video_id,)
            ).fetchone()
            if row is None:
                return None
            record = _row_to_video(row)
            conn.execute("DELETE FROM videos WHERE id=?", (video_id,))
            conn.commit()
        return record

    def count_videos(self, session_id: str | None = None) -> int:
        # Locked: also called off-thread by the QR device-check callback.
        with self._db.reading() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM videos WHERE session_id=?", (session_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM videos"
                ).fetchone()
        return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# Footfall analytics
# ---------------------------------------------------------------------------

class FootfallRepository:
    """Records every login arc (QR-scan → logout) for footfall analysis.

    Schema
    ------
    footfall(id, session_id, session_name, session_created, login_at, logout_at, logout_reason)

    Typical usage
    -------------
    * ``record_login(session)``      — called in LoginController._on_activated()
    * ``record_logout(session_id, reason)`` — called before startLogin() shows QR
    * ``list_session_summaries()``   — aggregated view for a report screen
    * ``export_csv(path)``           — dumps all events to a CSV file
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_login(self, session: SessionRecord) -> FootfallEvent:
        """Insert a new footfall row for a completed QR scan.

        If there are open (logout_at IS NULL) rows for a *different* session
        they are automatically closed with reason='session_switch', which
        happens when a second device scans a new QR without explicit logout.
        """
        now = _now_iso()
        fid = str(uuid.uuid4())
        with self._db.transaction() as conn:
            # Close any open arcs that belong to a different session.
            conn.execute(
                """
                UPDATE footfall
                   SET logout_at = ?, logout_reason = 'session_switch'
                 WHERE logout_at IS NULL AND session_id != ?
                """,
                (now, session.id),
            )
            conn.execute(
                """
                INSERT INTO footfall (id, session_id, session_name, session_created, login_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fid, session.id, session.name, session.started_at, now),
            )
            conn.commit()
        return self.get_event(fid)  # type: ignore[return-value]

    def record_logout(self, session_id: str, reason: str) -> None:
        """Close the most recent open arc for *session_id*.

        If no open arc exists (e.g. app startup before first scan) this is a
        no-op — we never create phantom rows.

        ``reason`` should be one of: ``'manual'``, ``'auto_idle'``,
        ``'session_switch'``.
        """
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE footfall
                   SET logout_at = ?, logout_reason = ?
                 WHERE session_id = ? AND logout_at IS NULL
                """,
                (now, reason, session_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Read — individual events
    # ------------------------------------------------------------------

    def get_event(self, event_id: str) -> FootfallEvent | None:
        row = self._db.connection.execute(
            "SELECT * FROM footfall WHERE id=? LIMIT 1", (event_id,)
        ).fetchone()
        return _row_to_footfall(row) if row else None

    def list_events(self, limit: int = 200) -> list[FootfallEvent]:
        """Return the *limit* most recent footfall events (newest first)."""
        rows = self._db.connection.execute(
            "SELECT * FROM footfall ORDER BY login_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_footfall(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — aggregated session summaries
    # ------------------------------------------------------------------

    def list_session_summaries(self, limit: int = 100) -> list[SessionFootfallSummary]:
        """Return per-session aggregated footfall stats, newest session first.

        Includes video_count, total_duration_seconds, and purge status.
        """
        rows = self._db.connection.execute(
            """
            SELECT
                f.session_id,
                f.session_name,
                f.session_created,
                COUNT(f.id)                             AS login_count,
                MIN(f.login_at)                         AS first_login_at,
                MAX(f.logout_at)                        AS last_logout_at,
                -- reason of the latest closed arc
                (SELECT logout_reason
                   FROM footfall f2
                  WHERE f2.session_id = f.session_id
                    AND f2.logout_at IS NOT NULL
                  ORDER BY f2.logout_at DESC
                  LIMIT 1)                              AS last_logout_reason,
                COALESCE(v.vc, 0)                       AS video_count,
                COALESCE(v.dur, 0.0)                    AS total_duration_seconds,
                s.purged_at                             AS purged_at
            FROM footfall f
            -- Pre-aggregate videos per session BEFORE joining: a direct
            -- LEFT JOIN videos fans every footfall row out by the video
            -- count, which inflates COUNT(f.id) (login_count) and
            -- SUM(duration). Aggregating first keeps footfall 1:1.
            LEFT JOIN (
                SELECT session_id,
                       COUNT(*)                       AS vc,
                       COALESCE(SUM(duration_seconds), 0.0) AS dur
                FROM videos
                GROUP BY session_id
            ) v ON v.session_id = f.session_id
            LEFT JOIN sessions s ON s.id = f.session_id
            GROUP BY f.session_id
            ORDER BY MAX(f.login_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_summary(r) for r in rows]

    def count_events(self) -> int:
        row = self._db.connection.execute(
            "SELECT COUNT(*) AS n FROM footfall"
        ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self, path: Path) -> Path:
        """Write all footfall events to a CSV file at *path*.

        Returns the path that was written.
        """
        events = self.list_events(limit=0)  # unlimited
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "id", "session_id", "session_name", "session_created",
                "login_at", "logout_at", "logout_reason", "data_deleted_at",
            ])
            writer.writeheader()
            for ev in events:
                writer.writerow({
                    "id": ev.id,
                    "session_id": ev.session_id,
                    "session_name": ev.session_name,
                    "session_created": ev.session_created,
                    "login_at": ev.login_at,
                    "logout_at": ev.logout_at or "",
                    "logout_reason": ev.logout_reason or "",
                    "data_deleted_at": ev.data_deleted_at or "",
                })
        return path


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


def _row_to_footfall(row) -> FootfallEvent:
    return FootfallEvent(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        session_name=str(row["session_name"] or ""),
        session_created=str(row["session_created"]),
        login_at=str(row["login_at"]),
        logout_at=row["logout_at"],
        logout_reason=row["logout_reason"],
        data_deleted_at=row["data_deleted_at"],
    )


def _row_to_summary(row) -> SessionFootfallSummary:
    return SessionFootfallSummary(
        session_id=str(row["session_id"]),
        session_name=str(row["session_name"] or ""),
        session_created=str(row["session_created"]),
        login_count=int(row["login_count"]),
        first_login_at=row["first_login_at"],
        last_logout_at=row["last_logout_at"],
        last_logout_reason=row["last_logout_reason"],
        video_count=int(row["video_count"]),
        total_duration_seconds=float(row["total_duration_seconds"]),
        purged_at=row["purged_at"],
    )
