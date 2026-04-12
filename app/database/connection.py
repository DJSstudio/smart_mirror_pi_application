"""SQLite connection and schema management."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseManager:
    def __init__(self, database_path: Path) -> None:
        self._path = database_path
        self._conn: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                ended_at    TEXT,
                active      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS videos (
                id               TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                title            TEXT NOT NULL,
                file_path        TEXT NOT NULL,
                thumbnail_path   TEXT,
                duration_seconds REAL,
                created_at       TEXT NOT NULL,
                camera_backend   TEXT NOT NULL DEFAULT '',
                notes            TEXT NOT NULL DEFAULT '',
                width            INTEGER,
                height           INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_active
                ON sessions(active);

            CREATE INDEX IF NOT EXISTS idx_videos_session_created
                ON videos(session_id, created_at DESC);
        """)
        self.connection.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
