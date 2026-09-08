"""
routes/critique_routes.py — Self-critique loop config and history.
Requirements: 7.1, 7.6, 8.1, 8.3, 8.4, 8.6
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.critique.critique_service import critique_service
from core.database import CritiquePassRecord, Session as DbSession, SessionLocal
from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class GlobalCritiqueConfigRequest(BaseModel):
    enabled: bool
    critique_model: Optional[str] = None
    critique_endpoint_url: Optional[str] = None


class SessionCritiqueConfigRequest(BaseModel):
    enabled: bool
    critique_model: Optional[str] = None
    critique_endpoint_url: Optional[str] = None


def _verify_session_owner(session_id: str, user: str) -> None:
    db = SessionLocal()
    try:
        s = db.query(DbSession).filter(DbSession.id == session_id).first()
        if s is None or (s.owner and s.owner != user):
            raise HTTPException(status_code=404, detail="Session not found")
    finally:
        db.close()


def _record_summary(r) -> dict:
    return {
        "id": r.id, "session_id": r.session_id, "message_id": r.message_id,
        "primary_model": r.primary_model, "critique_model": r.critique_model,
        "was_revised": r.was_revised,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _record_full(r) -> dict:
    d = _record_summary(r)
    d.update({
        "original_draft": r.original_draft,
        "revised_response": r.revised_response,
        "original_tokens": r.original_tokens,
        "revised_tokens": r.revised_tokens,
        "error_detail": r.error_detail,
    })
    return d


@router.get("/api/critique/config")
def get_global_config(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return critique_service.get_global_config()


@router.put("/api/critique/config")
def update_global_config(body: GlobalCritiqueConfigRequest, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    critique_service.set_global(body.enabled, body.critique_model, body.critique_endpoint_url)
    return {"ok": True, **critique_service.get_global_config()}


@router.get("/api/sessions/{session_id}/critique")
def get_session_config(session_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    _verify_session_owner(session_id, user)
    return critique_service.get_session_config(session_id)


@router.put("/api/sessions/{session_id}/critique")
def update_session_config(session_id: str, body: SessionCritiqueConfigRequest, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    _verify_session_owner(session_id, user)
    critique_service.set_enabled(session_id, body.enabled, body.critique_model, body.critique_endpoint_url)
    return {"ok": True, **critique_service.get_session_config(session_id)}


@router.get("/api/sessions/{session_id}/critique/history")
def get_history(session_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    _verify_session_owner(session_id, user)
    db = SessionLocal()
    try:
        rows = (db.query(CritiquePassRecord)
                .filter(CritiquePassRecord.session_id == session_id)
                .order_by(CritiquePassRecord.created_at.desc()).all())
        return {"records": [_record_summary(r) for r in rows]}
    finally:
        db.close()


@router.get("/api/critique/records/{record_id}")
def get_record(record_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    db = SessionLocal()
    try:
        r = db.query(CritiquePassRecord).filter(CritiquePassRecord.id == record_id).first()
        if r is None or r.owner != user:
            raise HTTPException(404, "Record not found")
        return _record_full(r)
    finally:
        db.close()
