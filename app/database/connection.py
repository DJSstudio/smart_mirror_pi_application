"""SQLite connection and schema management."""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, database_path: Path) -> None:
        self._path = database_path
        self._conn: sqlite3.Connection | None = None
        # Serializes concurrent write operations from multiple threads
        # (e.g. bg recording thread vs main-thread cleanup timer).
        # Reads don't need the lock — WAL mode allows concurrent readers.
        self._lock = threading.Lock()

    @contextmanager
    def transaction(self):
        """Acquire the write lock and yield the connection.

        All multi-step write sequences (execute … execute … commit) must
        run inside ``with db.transaction() as conn:`` to prevent races
        between the Qt main thread and background worker threads.
        """
        with self._lock:
            yield self.connection

    @contextmanager
    def reading(self):
        """Acquire the lock for a read issued OFF the Qt main thread.

        The single sqlite3.Connection is shared across threads
        (check_same_thread=False).  A read fired from an HTTP handler thread
        (the QR device-check callback) can otherwise interleave with a
        writer's in-flight transaction on the same connection — yielding a
        partial view or 'recursive use of cursors'.  Off-thread reads run
        under the same lock writers use so they can't interleave.  (Main-
        thread reads don't need this — they're sequenced with writes by the
        event loop / completion signals.)
        """
        with self._lock:
            yield self.connection

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            # Wait up to 5s for a lock instead of raising immediately — covers
            # off-thread reads (HTTP handlers) overlapping a writer's commit.
            self._conn.execute("PRAGMA busy_timeout=5000")
            # Explicit NORMAL: durable for committed txns under WAL while
            # avoiding an fsync per commit (kinder to the SD card than FULL).
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def checkpoint(self) -> None:
        """Truncate the write-ahead log to bound its on-disk growth.

        Called periodically (cleanup timer) and on shutdown.  Without this the
        -wal file can grow unbounded over weeks of uptime.  Held under the
        write lock so it can't interleave with a writer mid-transaction.
        """
        if self._conn is None:
            return
        try:
            with self._lock:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as exc:
            LOGGER.warning("WAL checkpoint failed: %s", exc)

    def initialize(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                ended_at    TEXT,
                active      INTEGER NOT NULL DEFAULT 1,
                device_id   TEXT NOT NULL DEFAULT ''
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

            -- Footfall analytics: one row per login arc (QR scan → logout).
            -- Multiple rows per session_id are normal (repeat logins).
            CREATE TABLE IF NOT EXISTS footfall (
                id              TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                session_name    TEXT NOT NULL DEFAULT '',
                session_created TEXT NOT NULL,
                login_at        TEXT NOT NULL,
                logout_at       TEXT,
                logout_reason   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_active
                ON sessions(active);

            CREATE INDEX IF NOT EXISTS idx_videos_session_created
                ON videos(session_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_footfall_session
                ON footfall(session_id, login_at DESC);

            CREATE INDEX IF NOT EXISTS idx_footfall_login_at
                ON footfall(login_at DESC);
        """)
        self.connection.commit()
        # Migrations: add columns that may not exist in older databases.
        _migrations = [
            "ALTER TABLE sessions ADD COLUMN device_id TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE sessions ADD COLUMN purged_at TEXT",
            "ALTER TABLE footfall ADD COLUMN data_deleted_at TEXT",
        ]
        for stmt in _migrations:
            try:
                self.connection.execute(stmt)
                self.connection.commit()
            except sqlite3.OperationalError as exc:
                # "duplicate column name" is the expected idempotent re-run.
                # Anything else (disk full, locked, corruption) is a real
                # failure that would leave a half-migrated schema — surface it
                # rather than silently masking it into a later "no such column".
                if "duplicate column" not in str(exc).lower():
                    LOGGER.error("Migration failed (%s): %s", stmt, exc)
                    raise

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
