"""Reasoning trace and session fork routes.

Endpoints
---------
GET  /api/sessions/{session_id}/reasoning        — list traces for a session (no node content)
GET  /api/reasoning/traces/{trace_id}            — full trace with nodes
GET  /api/reasoning/by-message/{message_id}      — trace for a specific message
POST /api/sessions/{session_id}/fork             — fork a session from a message or reasoning node
GET  /api/sessions/{session_id}/fork-info        — fork banner data (source session name, link)

Requirements: 9.4, 10.1, 11.1–11.7
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from services.reasoning.trace_store import trace_store
from core.database import (
    ReasoningTrace, ReasoningNode, Session as DbSession,
    ChatMessage, SessionLocal, utcnow_naive
)
from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------

class ForkRequest(BaseModel):
    source_message_id: str
    source_node_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trace_summary(trace: ReasoningTrace) -> dict:
    """Trace dict without node content (used in the list endpoint)."""
    return {
        "id": trace.id,
        "session_id": trace.session_id,
        "message_id": trace.message_id,
        "model": trace.model,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }


def _trace_full(trace: ReasoningTrace) -> dict:
    """Full trace dict including all nodes."""
    return {
        "id": trace.id,
        "session_id": trace.session_id,
        "message_id": trace.message_id,
        "model": trace.model,
        "full_text": trace.full_text,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
        "nodes": [
            {"id": n.id, "index": n.index, "content": n.content}
            for n in sorted(trace.nodes, key=lambda x: x.index)
        ],
    }


def _get_session_or_404(db, session_id: str, user: Optional[str]) -> DbSession:
    """Load a session and verify ownership. Raises 404 on miss or wrong owner."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if session is None or (user and session.owner and session.owner != user):
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _get_trace_or_404(db, trace_id: str, user: Optional[str]) -> ReasoningTrace:
    """Load a trace and verify ownership. Raises 404 on miss or wrong owner."""
    trace = db.query(ReasoningTrace).filter(ReasoningTrace.id == trace_id).first()
    if trace is None or (user and trace.owner and trace.owner != user):
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


# ---------------------------------------------------------------------------
# GET /api/sessions/{session_id}/reasoning
# List all reasoning traces for a session (no node content).
# Requirements: 9.4, 11.1
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/reasoning")
def list_session_traces(session_id: str, request: Request):
    user = get_current_user(request)
    db = SessionLocal()
    try:
        _get_session_or_404(db, session_id, user)
        traces = (
            db.query(ReasoningTrace)
            .filter(ReasoningTrace.session_id == session_id)
            .order_by(ReasoningTrace.created_at.desc())
            .all()
        )
        return {"traces": [_trace_summary(t) for t in traces]}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/reasoning/traces/{trace_id}
# Full trace with all nodes.
# Requirements: 9.4, 11.2
# ---------------------------------------------------------------------------

@router.get("/reasoning/traces/{trace_id}")
def get_trace(trace_id: str, request: Request):
    user = get_current_user(request)
    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        trace = (
            db.query(ReasoningTrace)
            .options(joinedload(ReasoningTrace.nodes))
            .filter(ReasoningTrace.id == trace_id)
            .first()
        )
        if trace is None or (user and trace.owner and trace.owner != user):
            raise HTTPException(status_code=404, detail="Trace not found")
        return _trace_full(trace)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/reasoning/by-message/{message_id}
# Full trace for a specific message, or {"trace": null} if none.
# Requirements: 9.4, 11.3
# ---------------------------------------------------------------------------

@router.get("/reasoning/by-message/{message_id}")
def get_trace_by_message(message_id: str, request: Request):
    user = get_current_user(request)
    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        trace = (
            db.query(ReasoningTrace)
            .options(joinedload(ReasoningTrace.nodes))
            .filter(ReasoningTrace.message_id == message_id)
            .first()
        )
        if trace is None:
            return {"trace": None}
        if user and trace.owner and trace.owner != user:
            return {"trace": None}
        return _trace_full(trace)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/sessions/{session_id}/fork
# Fork a session from a specific message (or reasoning node).
# Requirements: 11.4, 11.5, 11.6
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/fork")
def fork_session(session_id: str, body: ForkRequest, request: Request):
    user = get_current_user(request)
    db = SessionLocal()
    try:
        # 1. Load source session — verify ownership
        source_session = _get_session_or_404(db, session_id, user)

        # 2. Load messages up to and including source_message_id (ordered by timestamp)
        all_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp)
            .all()
        )

        # Slice messages up to and including the pivot message
        pivot_index = None
        for i, msg in enumerate(all_messages):
            if msg.id == body.source_message_id:
                pivot_index = i
                break

        if pivot_index is None:
            raise HTTPException(
                status_code=404,
                detail=f"Message '{body.source_message_id}' not found in session",
            )

        messages_to_copy = all_messages[: pivot_index + 1]

        # 3. Determine fork name content
        pivot_message = messages_to_copy[pivot_index]

        if body.source_node_id:
            # Use the reasoning node's content as the name basis
            node = (
                db.query(ReasoningNode)
                .filter(ReasoningNode.id == body.source_node_id)
                .first()
            )
            name_content = node.content if node else pivot_message.content
        else:
            name_content = pivot_message.content

        fork_name = "[Fork] " + (name_content or "")[:50]

        # 4. Create new Session
        new_session = DbSession(
            id=str(uuid.uuid4()),
            name=fork_name,
            endpoint_url=source_session.endpoint_url,
            model=source_session.model,
            owner=source_session.owner,
            forked_from_session_id=session_id,
            forked_from_message_id=body.source_message_id,
        )
        db.add(new_session)
        db.flush()  # ensure new_session.id is available before adding messages

        # 5. Copy messages into new session
        for msg in messages_to_copy:
            new_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=new_session.id,
                role=msg.role,
                content=msg.content,
                meta_data=msg.meta_data,
                timestamp=msg.timestamp,
            )
            db.add(new_msg)

        # 6. If source_node_id given, append an extra system message with node content
        if body.source_node_id:
            node = (
                db.query(ReasoningNode)
                .filter(ReasoningNode.id == body.source_node_id)
                .first()
            )
            if node:
                system_msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=new_session.id,
                    role="system",
                    content=node.content,
                    timestamp=utcnow_naive(),
                )
                db.add(system_msg)

        db.commit()
        logger.info(
            "Forked session %s → %s from message %s",
            session_id, new_session.id, body.source_message_id,
        )

        return {
            "new_session_id": new_session.id,
            "new_session_name": new_session.name,
            "source_session_id": session_id,
            "source_message_id": body.source_message_id,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("fork_session failed for session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="Fork failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/sessions/{session_id}/fork-info
# Returns fork banner data: source session name + link.
# Requirements: 11.7
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/fork-info")
def get_fork_info(session_id: str, request: Request):
    user = get_current_user(request)
    db = SessionLocal()
    try:
        session = _get_session_or_404(db, session_id, user)

        if not session.forked_from_session_id:
            return {"is_fork": False}

        source = db.query(DbSession).filter(
            DbSession.id == session.forked_from_session_id
        ).first()

        source_name = source.name if source else None

        return {
            "is_fork": True,
            "source_session_id": session.forked_from_session_id,
            "source_session_name": source_name,
            "source_message_id": session.forked_from_message_id,
        }
    finally:
        db.close()
