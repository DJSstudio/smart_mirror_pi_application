"""Real-DB tests for SessionRepository retention semantics."""
from __future__ import annotations

from app.database.connection import DatabaseManager
from app.database.repositories import SessionRepository


def _repo(tmp_path):
    db = DatabaseManager(tmp_path / "test.db")
    db.initialize()
    return db, SessionRepository(db)


def _purged_at(db: DatabaseManager, sid: str):
    with db.reading() as conn:
        row = conn.execute(
            "SELECT purged_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    return row["purged_at"] if row else "MISSING"


def test_activate_session_clears_purged_at(tmp_path) -> None:
    # Data-retention guarantee: if a session was purged by the cleanup service
    # and is later resumed (QR Resume), any footage recorded after the resume
    # MUST be subject to retention again.  Cleanup only selects rows WHERE
    # purged_at IS NULL, so a stale purged_at would make the new footage immune
    # to purging forever.  activate_session must reset purged_at to NULL.
    db, repo = _repo(tmp_path)
    session = repo.create_session("S", device_id="dev-1")
    sid = session.id

    # Simulate the cleanup service having purged this session, then it going
    # inactive (as it would after a logout).
    with db.transaction() as conn:
        conn.execute(
            "UPDATE sessions SET active=0, purged_at=? WHERE id=?",
            ("2026-01-01T00:00:00+00:00", sid),
        )
        conn.commit()
    assert _purged_at(db, sid) == "2026-01-01T00:00:00+00:00"

    # Resume / reactivate the session.
    repo.activate_session(sid, device_id="dev-1")

    assert _purged_at(db, sid) is None


def test_activate_session_makes_it_active(tmp_path) -> None:
    db, repo = _repo(tmp_path)
    first = repo.create_session("A", device_id="dev-1")
    second = repo.create_session("B", device_id="dev-2")
    # Re-activating the first ends the second (only one active session).
    repo.activate_session(first.id, device_id="dev-1")
    active = repo.get_active_session()
    assert active is not None
    assert active.id == first.id
    assert active.id != second.id
