"""CleanupService retention tests — recent footage must survive a restart.

Regression guard for the field bug: resuming a session (which carries an OLD
logout_at) and recording a fresh clip, then restarting the app, wiped the
just-recorded gallery because age was measured from the stale logout instead of
the recent video.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.database.connection import DatabaseManager
from app.database.repositories import VideoRepository
from app.services.cleanup_service import CleanupService


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _setup(tmp_path):
    db = DatabaseManager(tmp_path / "t.db")
    db.initialize()
    return db, VideoRepository(db)


def _add_session(db, sid, started_at, active=0):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO sessions (id, name, started_at, active, device_id) "
            "VALUES (?,?,?,?,?)",
            (sid, sid, started_at, active, "dev"),
        )
        conn.commit()


def _add_footfall(db, sid, login_at, logout_at=None):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO footfall (id, session_id, session_name, session_created, "
            "login_at, logout_at) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), sid, sid, login_at, login_at, logout_at),
        )
        conn.commit()


def _add_video(db, sid, created_at, file_path):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO videos (id, session_id, title, file_path, thumbnail_path, "
            "duration_seconds, created_at, camera_backend, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), sid, "clip", file_path, None, 1.0, created_at, "usb", ""),
        )
        conn.commit()


def _purged_at(db, sid):
    with db.reading() as conn:
        row = conn.execute(
            "SELECT purged_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    return row["purged_at"]


def test_recent_video_survives_old_logout(tmp_path) -> None:
    # The exact field repro: a resumed session with a 2h-old logout but a clip
    # recorded 4 minutes ago must NOT be purged on the next startup cleanup.
    db, vrepo = _setup(tmp_path)
    now = datetime.now(timezone.utc)
    sid = "s-resume"
    _add_session(db, sid, started_at=_iso(now - timedelta(hours=3)))
    _add_footfall(
        db, sid,
        login_at=_iso(now - timedelta(hours=3)),
        logout_at=_iso(now - timedelta(hours=2)),  # OLD logout (the trap)
    )
    _add_footfall(db, sid, login_at=_iso(now - timedelta(minutes=5)))  # resume, no logout
    vfile = tmp_path / "recent.mp4"
    vfile.write_bytes(b"DATA")
    _add_video(db, sid, created_at=_iso(now - timedelta(minutes=4)), file_path=str(vfile))

    cleaned = CleanupService(db=db, video_repo=vrepo, temp_dir=tmp_path).run(
        older_than_hours=1
    )

    assert cleaned == 0
    assert vfile.exists()              # gallery kept
    assert _purged_at(db, sid) is None


def test_stale_session_is_purged(tmp_path) -> None:
    # Retention still works: a session whose newest signal (incl. its last
    # video) is older than the threshold is purged.
    db, vrepo = _setup(tmp_path)
    now = datetime.now(timezone.utc)
    sid = "s-stale"
    _add_session(db, sid, started_at=_iso(now - timedelta(hours=5)))
    _add_footfall(
        db, sid,
        login_at=_iso(now - timedelta(hours=5)),
        logout_at=_iso(now - timedelta(hours=4)),
    )
    vfile = tmp_path / "old.mp4"
    vfile.write_bytes(b"DATA")
    _add_video(db, sid, created_at=_iso(now - timedelta(hours=4)), file_path=str(vfile))

    cleaned = CleanupService(db=db, video_repo=vrepo, temp_dir=tmp_path).run(
        older_than_hours=1
    )

    assert cleaned == 1
    assert not vfile.exists()          # footage deleted by retention
    assert _purged_at(db, sid) is not None


def test_active_session_never_purged(tmp_path) -> None:
    db, vrepo = _setup(tmp_path)
    now = datetime.now(timezone.utc)
    sid = "s-active"
    _add_session(db, sid, started_at=_iso(now - timedelta(hours=5)), active=1)
    vfile = tmp_path / "active.mp4"
    vfile.write_bytes(b"DATA")
    _add_video(db, sid, created_at=_iso(now - timedelta(hours=4)), file_path=str(vfile))

    cleaned = CleanupService(db=db, video_repo=vrepo, temp_dir=tmp_path).run(
        older_than_hours=1
    )

    assert cleaned == 0
    assert vfile.exists()
