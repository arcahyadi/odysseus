"""
routes/session_share.py

Feature #8 — shared real-time workspaces.

Owner-managed share links (authenticated, like the rest of the app):
  POST   /api/share/sessions            — create a share link for a session you own
  GET    /api/share/sessions            — list your share links
  DELETE /api/share/sessions/{share_id} — revoke one of your share links

Public endpoints (the token in the URL IS the credential):
  GET /api/s/{token}        — share metadata (session name + created date;
                              never message bodies or the owner's identity)
  GET /api/s/{token}/stream — SSE: replay each stored ChatMessage of the shared
                              session as a JSON event, then keep the connection
                              open relaying in-process pub/sub payloads for that
                              session (~15s comment pings keep it alive and
                              surface dead clients).
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.database import ChatMessage as DBChatMessage
from core.database import Session as DBSession
from core.database import SessionLocal, SharedSession
from services import session_share
from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)

# Owner-facing share-management endpoints.
router = APIRouter(prefix="/api/share", tags=["share"])

# Public read endpoints — the share token is the only credential, so these are
# mounted on their own prefix and intentionally do NOT call get_current_user.
public_router = APIRouter(prefix="/api/s", tags=["share"])

# SSE keep-alive interval. A comment line is emitted whenever the connection is
# silent for this long, which also lets the server notice client disconnects.
_PING_SECONDS = 15.0


class ShareSessionRequest(BaseModel):
    session_id: str


def _public_url(request: Request, token: str) -> str:
    """Absolute URL for a share token (used for the copy-link affordance)."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/s/{token}"


def _share_dict(request: Request, share: SharedSession) -> dict:
    return {
        "id": share.id,
        "token": share.token,
        "session_id": share.session_id,
        "role": share.role,
        "created_at": share.created_at.isoformat() if share.created_at else None,
        "url": _public_url(request, share.token),
    }


# ---------------------------------------------------------------------------
# POST /api/share/sessions — create a share link
# ---------------------------------------------------------------------------

@router.post("/sessions", status_code=201)
def create_share_link(body: ShareSessionRequest, request: Request):
    """Create a viewer share link for a chat session the caller owns.

    Idempotent per (owner, session): if a link already exists it is returned
    instead of minting a second token. 404 when the session does not exist,
    403 when the session belongs to a different owner (skipped in single-user /
    auth-disabled mode, matching the repo's owner-check convention).
    """
    user = get_current_user(request)
    session_id = (body.session_id or "").strip()
    if not session_id:
        raise HTTPException(422, "session_id is required")

    db = SessionLocal()
    try:
        sess_row = db.query(DBSession).filter(DBSession.id == session_id).first()
        if sess_row is None:
            raise HTTPException(404, "Session not found")
        if user and sess_row.owner and sess_row.owner != user:
            raise HTTPException(
                403, "Access denied — session belongs to another owner"
            )

        existing_q = db.query(SharedSession).filter(
            SharedSession.session_id == session_id
        )
        if user:
            existing_q = existing_q.filter(SharedSession.owner == user)
        existing = existing_q.first()
        if existing is not None:
            return _share_dict(request, existing)

        share = session_share.create_share(db, owner=user, session_id=session_id)
        return _share_dict(request, share)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/share/sessions — list the caller's share links
# ---------------------------------------------------------------------------

@router.get("/sessions")
def list_share_links(request: Request):
    """List every share link owned by the current user, newest first.

    Each entry carries the shared session's name (from the sessions table) so
    the management UI does not need a second round-trip to label rows.
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        rows = session_share.list_shares(db, owner=user)
        session_ids = {r.session_id for r in rows}
        names: dict = {}
        if session_ids:
            pairs = (
                db.query(DBSession.id, DBSession.name)
                .filter(DBSession.id.in_(session_ids))
                .all()
            )
            names = {sid: name for sid, name in pairs}
        shares = []
        for row in rows:
            item = _share_dict(request, row)
            item["session_name"] = names.get(row.session_id)
            shares.append(item)
        return {"shares": shares}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# DELETE /api/share/sessions/{share_id} — revoke a share link
# ---------------------------------------------------------------------------

@router.delete("/sessions/{share_id}", status_code=204)
def revoke_share_link(share_id: str, request: Request):
    """Revoke one of the caller's share links. 404 when it does not exist (or
    belongs to someone else — no existence leak)."""
    user = get_current_user(request)
    db = SessionLocal()
    try:
        revoked = session_share.revoke_share(db, owner=user, share_id=share_id)
        if not revoked:
            raise HTTPException(404, "Share link not found")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public: GET /api/s/{token} — share metadata
# ---------------------------------------------------------------------------

@public_router.get("/{token}")
def shared_session_metadata(token: str, request: Request):
    """Public metadata for a share token: session name + created date only.

    Never returns message bodies or the owner's identity — possession of the
    token is the entire authorization story for this endpoint.
    """
    db = SessionLocal()
    try:
        share = session_share.resolve_token(db, token)
        if share is None:
            raise HTTPException(
                404, "This share link is invalid or has been revoked"
            )
        sess_row = (
            db.query(DBSession).filter(DBSession.id == share.session_id).first()
        )
        if sess_row is None:
            raise HTTPException(
                404, "The shared session is no longer available"
            )
        return {
            "id": share.id,
            "token": share.token,
            "session_id": share.session_id,
            "role": share.role,
            "session_name": sess_row.name,
            "session_created_at": (
                sess_row.created_at.isoformat() if sess_row.created_at else None
            ),
            "url": _public_url(request, share.token),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public: GET /api/s/{token}/stream — SSE replay + live relay
# ---------------------------------------------------------------------------

def _message_event(row: DBChatMessage) -> str:
    """Serialize one stored ChatMessage row as an SSE ``data:`` event."""
    content = row.content
    if not isinstance(content, str):
        # The column is Text, but stay defensive against legacy rows that may
        # hold list-shaped multimodal content or NULL.
        if content is None:
            content = ""
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            content = " ".join(parts)
        else:
            content = str(content)
    event = {
        "type": "message",
        "id": row.id,
        "role": row.role,
        "content": content,
    }
    ts = row.timestamp
    if ts is not None:
        event["timestamp"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@public_router.get("/{token}/stream")
def shared_session_stream(token: str, request: Request):
    """SSE stream for a shared session.

    Phase 1 replays every stored ChatMessage for the session (oldest first) as
    ``data: {json}\\n\\n`` events so a late viewer sees the full history.
    Phase 2 keeps the connection open and relays live payloads published via
    session_share.publish(session_id, payload) — e.g. the assistant message
    that the chat streaming path persists after a run. A comment ping is sent
    roughly every 15s of silence; when the client goes away the queue read is
    cancelled and the subscriber is cleaned up.
    """
    db = SessionLocal()
    try:
        share = session_share.resolve_token(db, token)
        if share is None:
            raise HTTPException(
                404, "This share link is invalid or has been revoked"
            )
        session_id = share.session_id
    finally:
        db.close()

    async def _event_stream():
        # Phase 1 — replay stored history (read fully, then close the DB so the
        # connection is not held open for the lifetime of the SSE response).
        history = []
        db = SessionLocal()
        try:
            history = (
                db.query(DBChatMessage)
                .filter(DBChatMessage.session_id == session_id)
                .order_by(DBChatMessage.timestamp.asc())
                .all()
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — stream must not die on a DB hiccup
            logger.warning(
                "share stream history read failed for session %s: %s",
                session_id,
                exc,
            )
        finally:
            db.close()
        for row in history:
            yield _message_event(row)

        # Phase 2 — live relay of in-process pub/sub payloads.
        queue, unsubscribe = session_share.subscribe(session_id)
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(
                        queue.get(), timeout=_PING_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if payload is None:
                    break
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            unsubscribe()

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        _event_stream(), media_type="text/event-stream", headers=headers
    )
