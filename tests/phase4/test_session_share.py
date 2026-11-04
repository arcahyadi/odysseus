"""
tests/phase4/test_session_share.py

Small unit tests for the feature #8 session-share service layer: token
generation, owner-scoped CRUD helpers, and the in-process pub/sub registry.
Route-level/SSE behaviour is intentionally out of scope here (fast, focused).

# Feature: session-share
"""

import asyncio

import sqlalchemy
from sqlalchemy.orm import sessionmaker

from core.database import Base, Session as DBSession, SharedSession
from services import session_share


def _make_db():
    """Fresh in-memory database with all core tables (incl. shared_sessions)."""
    engine = sqlalchemy.create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _seed_session(db, sid: str, owner: str = "alice", name: str = "Shared chat"):
    row = DBSession(
        id=sid, name=name, endpoint_url="http://x/v1", model="m", owner=owner
    )
    db.add(row)
    db.commit()
    return row


def test_new_token_is_urlsafe_and_unique():
    tokens = {session_share.new_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(t and set(t) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-") for t in tokens)


def test_create_share_sets_token_role_and_resolves():
    db = _make_db()
    _seed_session(db, "sess-1")
    try:
        share = session_share.create_share(db, owner="alice", session_id="sess-1")
        assert share.id and len(share.token) >= 20
        assert share.role == "viewer"
        assert share.owner == "alice"
        # resolve_token round-trips; unknown token resolves to None.
        assert session_share.resolve_token(db, share.token).id == share.id
        assert session_share.resolve_token(db, "no-such-token") is None
        assert session_share.resolve_token(db, "") is None
    finally:
        db.close()


def test_create_share_normalizes_empty_owner():
    db = _make_db()
    _seed_session(db, "sess-2", owner="")
    try:
        share = session_share.create_share(db, owner=None, session_id="sess-2")
        assert share.owner == ""
    finally:
        db.close()


def test_list_shares_is_owner_scoped():
    db = _make_db()
    _seed_session(db, "s-a1", owner="alice")
    _seed_session(db, "s-b1", owner="bob")
    try:
        session_share.create_share(db, owner="alice", session_id="s-a1")
        session_share.create_share(db, owner="bob", session_id="s-b1")
        alice_ids = {r.session_id for r in session_share.list_shares(db, "alice")}
        assert alice_ids == {"s-a1"}
        # Single-user mode (owner="") sees everything.
        assert {r.session_id for r in session_share.list_shares(db, "")} == {
            "s-a1", "s-b1",
        }
    finally:
        db.close()


def test_revoke_share_requires_matching_owner():
    db = _make_db()
    _seed_session(db, "sess-3", owner="alice")
    try:
        share = session_share.create_share(db, owner="alice", session_id="sess-3")
        # A different owner cannot revoke alice's link.
        assert session_share.revoke_share(db, owner="bob", share_id=share.id) is False
        assert session_share.resolve_token(db, share.token) is not None
        # The owner can.
        assert session_share.revoke_share(db, owner="alice", share_id=share.id) is True
        assert session_share.resolve_token(db, share.token) is None
        # Revoking again is a miss.
        assert session_share.revoke_share(db, owner="alice", share_id=share.id) is False
    finally:
        db.close()


def test_publish_subscribe_delivers_and_cleans_up():
    async def _scenario():
        queue, unsubscribe = session_share.subscribe("sess-live")
        try:
            delivered = session_share.publish(
                "sess-live", {"type": "message", "content": "hello"}
            )
            assert delivered == 1
            payload = queue.get_nowait()
            assert payload == {"type": "message", "content": "hello"}
        finally:
            unsubscribe()
        # After unsubscribe nobody receives events for that session.
        assert session_share.publish("sess-live", {"x": 1}) == 0
        # Events for an unsubscribed session are dropped silently.
        assert session_share.publish("sess-unknown", {"x": 1}) == 0

    asyncio.run(_scenario())


def test_share_row_cascades_when_session_deleted():
    db = _make_db()
    _seed_session(db, "sess-del", owner="alice")
    try:
        share = session_share.create_share(db, owner="alice", session_id="sess-del")
        assert share.id
        # Foreign keys are ON for sqlite in this app; deleting the session row
        # must remove the dependent share row automatically.
        row = db.query(DBSession).filter(DBSession.id == "sess-del").one()
        db.delete(row)
        db.commit()
        # Drop the identity map so the query re-reads the DB (the ORM would
        # otherwise hand back the stale, now-deleted in-memory instance).
        db.expunge_all()
        assert (
            db.query(SharedSession)
            .filter(SharedSession.session_id == "sess-del")
            .first()
            is None
        )
    finally:
        db.close()
