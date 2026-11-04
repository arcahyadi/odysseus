"""
services/session_share.py

Feature #8 — shared real-time workspaces.

Service layer for share links that grant read-only (viewer) access to a chat
session:

  - create_share / list_shares / revoke_share / resolve_token: thin ORM
    helpers over the `SharedSession` row in core.database.
  - new_token: url-safe bearer token (secrets.token_urlsafe).
  - subscribe / publish: tiny in-process pub/sub registry used by the public
    SSE stream (/api/s/{token}/stream) to relay live events for a session.
    There is no global event bus in the app; this module-level dict is the
    only bus and is intentionally scoped to one process.

The chat pipeline currently persists assistant messages without calling
publish(). To make live relaying useful, the streaming save path (e.g. the
save_assistant_response helper in routes/chat_helpers.py, which both chat and
agent streaming modes funnel through in routes/chat_routes.py) should one day
call session_share.publish(session_id, {...}) right after a message is
persisted — wrapped in try/except so a share bug can never break chat.

Pure stdlib + sqlalchemy only (no FastAPI imports here).
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid

from sqlalchemy.exc import IntegrityError

from core.database import SharedSession, utcnow_naive

logger = logging.getLogger(__name__)

# Bounded per-viewer queue: a viewer that never reads must not grow an
# unbounded buffer inside the chat process.
_QUEUE_MAXSIZE = 200

# In-process registry: session_id -> set[asyncio.Queue]. All access happens on
# the event-loop thread (subscribers and publishers are async request handlers),
# mirroring how the rest of the app treats its in-memory registries.
_SUBSCRIBERS: dict[str, set] = {}


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

def new_token() -> str:
    """Return a fresh url-safe share token (18 bytes of entropy)."""
    return secrets.token_urlsafe(18)


# ---------------------------------------------------------------------------
# DB helpers (db is a SQLAlchemy session, e.g. core.database.SessionLocal())
# ---------------------------------------------------------------------------

def create_share(db, owner, session_id):
    """Persist a new viewer share row for *session_id* and return it.

    owner="" (or None) is the single-user / auth-disabled mode convention used
    across the repo. Raises sqlalchemy.exc.IntegrityError upstream if a token
    collision survives the retry loop.
    """
    owner = owner or ""
    session_id = (session_id or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    for _attempt in range(5):
        row = SharedSession(
            id=str(uuid.uuid4()),
            owner=owner,
            session_id=session_id,
            token=new_token(),
            role="viewer",
            created_at=utcnow_naive(),
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            # Astronomically unlikely token collision — roll back and retry.
            db.rollback()
            continue
    raise RuntimeError("Could not allocate a unique share token")


def list_shares(db, owner):
    """Return the share rows visible to *owner*, newest first.

    When owner is empty (auth disabled / single-user) no owner filter is
    applied — everything in the local install is the operator's.
    """
    q = db.query(SharedSession)
    if owner:
        q = q.filter(SharedSession.owner == owner)
    return q.order_by(SharedSession.created_at.desc()).all()


def revoke_share(db, owner, share_id) -> bool:
    """Delete the share with *share_id* when the *owner* may revoke it.

    Returns True if a row was deleted, False if nothing matched (owner-scoped,
    so another user's share_id looks like a miss).
    """
    share_id = (share_id or "").strip()
    if not share_id:
        return False
    q = db.query(SharedSession).filter(SharedSession.id == share_id)
    if owner:
        q = q.filter(SharedSession.owner == owner)
    row = q.first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def resolve_token(db, token):
    """Return the SharedSession row for *token*, or None when unknown."""
    token = (token or "").strip()
    if not token:
        return None
    return db.query(SharedSession).filter(SharedSession.token == token).first()


# ---------------------------------------------------------------------------
# In-process pub/sub (used by the public SSE stream)
# ---------------------------------------------------------------------------

def subscribe(session_id: str):
    """Register a subscriber queue for live events on *session_id*.

    Returns (queue, unsubscribe). The queue receives payload dicts that were
    publish()ed for the session; unsubscribe() detaches the queue and prunes
    the registry entry when it was the last subscriber (safe to call twice).
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    subs = _SUBSCRIBERS.setdefault(session_id, set())
    subs.add(queue)

    def _unsubscribe() -> None:
        subs = _SUBSCRIBERS.get(session_id)
        if subs is not None:
            subs.discard(queue)
            if not subs:
                _SUBSCRIBERS.pop(session_id, None)

    return queue, _unsubscribe


def publish(session_id: str, payload: dict) -> int:
    """Fan *payload* out to every queue subscribed to *session_id*.

    Returns how many subscribers received it (0 when nobody is listening).
    Designed to be called from the chat save path, so it NEVER raises and
    never blocks: full queues drop the event rather than stall the caller.
    """
    if payload is None:
        return 0
    subs = _SUBSCRIBERS.get(session_id)
    if not subs:
        return 0
    delivered = 0
    for queue in list(subs):
        try:
            queue.put_nowait(payload)
            delivered += 1
        except asyncio.QueueFull:
            # Slow viewer — drop the oldest queued event to make room for the
            # freshest one, then deliver.
            try:
                queue.get_nowait()
                queue.put_nowait(payload)
                delivered += 1
            except Exception:
                logger.debug("share publish overflow for %s", session_id, exc_info=True)
        except Exception:
            logger.debug("share publish failed for %s", session_id, exc_info=True)
    return delivered
