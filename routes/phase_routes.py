"""
Phase-lock routes — Changer la phase d'une session via l'API.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/phase", tags=["phase-lock"])

VALID_PHASES = Literal["RESEARCH", "INNOVATE", "PLAN", "BUILD", "VERIFY"]


class PhaseChangeRequest(BaseModel):
    phase: VALID_PHASES
    session_id: str


@router.post("/set")
async def set_phase(req: PhaseChangeRequest):
    """Définit la phase d'une session."""
    try:
        from src.tool_registry import ToolRegistry

        registry = ToolRegistry.get_instance()
        registry.set_phase(req.session_id, req.phase)
        return {
            "ok": True,
            "session_id": req.session_id,
            "phase": req.phase,
            "message": registry.get_phase_message(req.session_id),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/current/{session_id}")
async def get_phase(session_id: str):
    """Retourne la phase actuelle d'une session."""
    try:
        from src.tool_registry import ToolRegistry

        registry = ToolRegistry.get_instance()
        phase = registry.get_phase(session_id)
        return {"session_id": session_id, "phase": phase, "message": registry.get_phase_message(session_id)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/config")
async def get_phase_config():
    """Retourne la config phase-lock complète."""
    try:
        from src.tool_registry import ToolRegistry

        registry = ToolRegistry.get_instance()
        return registry._config
    except Exception as e:
        return {"error": str(e)}
