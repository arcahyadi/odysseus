"""
routes/memory/graph_routes.py

Graph memory API: entity search, detail, and full export.
Requirements: 4.3–4.8
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from services.memory.graph import graph_store
from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory/graph")


@router.get("/entities")
def list_graph_entities(request: Request, q: Optional[str] = None):
    """Search or list all entities for the current user. Req 4.3"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    entities = graph_store.search_entities(user, fragment=q or "")
    return {"entities": entities}


@router.get("/entity/{entity_id}")
def get_graph_entity(entity_id: str, request: Request):
    """Return a single entity with its direct neighbours. Req 4.4, 4.8"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = graph_store.get_entity_with_neighbours(user, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return result


@router.get("/export")
def export_graph(request: Request):
    """Export full owner graph as nodes + edges. Req 4.5"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return graph_store.export_graph(user)
