"""Kill-switches dashboard route — read-only state of ODYSSEUS_* switches."""

from fastapi import APIRouter

from src.killswitch_registry import categories, read_states

router = APIRouter(prefix="/api/killswitches", tags=["killswitches"])


@router.get("")
async def list_killswitches():
    """Retourne l'etat reel de tous les kill-switches (lecture seule)."""
    try:
        return {"ok": True, "categories": categories(), "switches": read_states()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
