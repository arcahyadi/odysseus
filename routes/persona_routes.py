"""Persona routes — /api/personas and /api/sessions/{session_id}/persona."""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.auth_helpers import get_current_user
from services.personas.persona_manager import persona_manager, PersonaLimitError
from core.database import Session as DbSession, SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["personas"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _persona_dict(p) -> dict:
    tools = []
    if p.allowed_tools:
        try:
            tools = json.loads(p.allowed_tools)
        except Exception:
            tools = []
    return {
        "id": p.id,
        "owner": p.owner,
        "name": p.name,
        "system_prompt": p.system_prompt,
        "allowed_tools": tools,
        "memory_scope": p.memory_scope,
        "model_ref": p.model_ref,
        "endpoint_url": p.endpoint_url,
        "is_builtin": p.is_builtin,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreatePersonaRequest(BaseModel):
    name: str
    system_prompt: str
    allowed_tools: Optional[List[str]] = None
    memory_scope: Optional[str] = None
    model_ref: Optional[str] = None
    endpoint_url: Optional[str] = None


class UpdatePersonaRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    memory_scope: Optional[str] = None
    model_ref: Optional[str] = None
    endpoint_url: Optional[str] = None


class ActivatePersonaRequest(BaseModel):
    persona_id: str


# ---------------------------------------------------------------------------
# GET /api/personas — list active user personas + built-ins
# ---------------------------------------------------------------------------

@router.get("/api/personas")
def list_personas(request: Request):
    """Return all active user-owned personas plus built-in personas. Requirements: 3.6, 3.7"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    personas = persona_manager.list_for_user(owner=user)
    return {"personas": [_persona_dict(p) for p in personas]}


# ---------------------------------------------------------------------------
# POST /api/personas — create new persona
# ---------------------------------------------------------------------------

@router.post("/api/personas", status_code=201)
def create_persona(request: Request, body: CreatePersonaRequest):
    """Create a new user persona. Requirements: 3.1, 3.2, 3.5, 3.8"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    kwargs = {}
    if body.memory_scope is not None:
        kwargs["memory_scope"] = body.memory_scope
    if body.model_ref is not None:
        kwargs["model_ref"] = body.model_ref
    if body.endpoint_url is not None:
        kwargs["endpoint_url"] = body.endpoint_url
    if body.allowed_tools is not None:
        kwargs["allowed_tools"] = json.dumps(body.allowed_tools)
    try:
        persona = persona_manager.create(
            owner=user,
            name=body.name,
            system_prompt=body.system_prompt,
            **kwargs,
        )
    except PersonaLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _persona_dict(persona)


# ---------------------------------------------------------------------------
# GET /api/personas/{persona_id} — get single persona
# ---------------------------------------------------------------------------

@router.get("/api/personas/{persona_id}")
def get_persona(persona_id: str, request: Request):
    """Return a single persona by ID. Requirements: 3.1"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    persona = persona_manager.get(persona_id, owner=user)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
    return _persona_dict(persona)


# ---------------------------------------------------------------------------
# PUT /api/personas/{persona_id} — update persona (user-owned only)
# ---------------------------------------------------------------------------

@router.put("/api/personas/{persona_id}")
def update_persona(persona_id: str, request: Request, body: UpdatePersonaRequest):
    """Update a user-owned persona. Requirements: 3.3"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Only pass explicitly-set fields (non-None) to the manager
    kwargs = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.system_prompt is not None:
        kwargs["system_prompt"] = body.system_prompt
    if body.memory_scope is not None:
        kwargs["memory_scope"] = body.memory_scope
    if body.model_ref is not None:
        kwargs["model_ref"] = body.model_ref
    if body.endpoint_url is not None:
        kwargs["endpoint_url"] = body.endpoint_url
    if body.allowed_tools is not None:
        kwargs["allowed_tools"] = json.dumps(body.allowed_tools)

    try:
        persona = persona_manager.update(persona_id=persona_id, owner=user, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        msg = str(exc)
        if "built-in" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return _persona_dict(persona)


# ---------------------------------------------------------------------------
# DELETE /api/personas/{persona_id} — soft-delete (user-owned only)
# ---------------------------------------------------------------------------

@router.delete("/api/personas/{persona_id}", status_code=204)
def delete_persona(persona_id: str, request: Request):
    """Soft-delete a user-owned persona (sets is_active=False). Requirements: 3.4"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        persona_manager.delete(persona_id=persona_id, owner=user)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        msg = str(exc)
        if "built-in" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


# ---------------------------------------------------------------------------
# POST /api/sessions/{session_id}/persona — activate persona for session
# ---------------------------------------------------------------------------

@router.post("/api/sessions/{session_id}/persona")
def activate_session_persona(session_id: str, request: Request, body: ActivatePersonaRequest):
    """Activate a persona for a session. Requirements: 4.1, 4.5"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Verify the session belongs to the user
    db = SessionLocal()
    try:
        session_row = db.query(DbSession).filter(DbSession.id == session_id).first()
    finally:
        db.close()

    if session_row is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if session_row.owner != user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        persona = persona_manager.activate_for_session(
            session_id=session_id,
            persona_id=body.persona_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _persona_dict(persona)


# ---------------------------------------------------------------------------
# DELETE /api/sessions/{session_id}/persona — deactivate persona for session
# ---------------------------------------------------------------------------

@router.delete("/api/sessions/{session_id}/persona", status_code=204)
def deactivate_session_persona(session_id: str, request: Request):
    """Deactivate the active persona for a session. Requirements: 4.6, 4.7"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Verify the session belongs to the user
    db = SessionLocal()
    try:
        session_row = db.query(DbSession).filter(DbSession.id == session_id).first()
    finally:
        db.close()

    if session_row is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    if session_row.owner != user:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    persona_manager.deactivate_for_session(session_id=session_id)
