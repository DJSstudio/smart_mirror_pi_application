from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseManager:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self._database_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def initialize(self) -> None:
        connection = self.connection
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                thumbnail_path TEXT,
                duration_seconds REAL,
                created_at TEXT NOT NULL,
                camera_backend TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                width INTEGER,
                height INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_active
                ON sessions(active);

            CREATE INDEX IF NOT EXISTS idx_videos_session_created
                ON videos(session_id, created_at DESC);
            """
        )
        connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
