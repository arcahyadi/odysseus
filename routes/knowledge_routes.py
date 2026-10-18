"""
Knowledge routes — Orchestration de la Trinité (CBM + VectorRAG natif + Obsidian).
Checkpoint : CBM (structure code) → VectorRAG natif (sémantique doc) → Obsidian.

La recherche sémantique doc est déléguée au ``VectorRAG`` natif (ChromaDB) au
lieu du service Graphify fantôme (jamais démarré) — zéro redondance.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter

from src.rag_singleton import get_rag_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

CBM_URL = "http://localhost:9749"


def _native_semantic_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Semantic doc search via the native VectorRAG (replaces phantom Graphify)."""
    rag = get_rag_manager()
    if rag is None:
        return {"results": [], "error": "native RAG unavailable"}
    try:
        hits = rag.search(query, k=limit)
        return {"results": hits, "source": "native-vectorrag"}
    except Exception as e:
        return {"results": [], "error": str(e)}


# ---- CBM — Structure code ----


@router.get("/code/search")
async def search_code_graph(q: str, limit: int = 10):
    """CBM search_graph — trouve des fonctions/classes/routes par nom."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{CBM_URL}/search_graph", json={"name_pattern": q, "limit": limit})
            return resp.json()
    except Exception as e:
        return {"error": str(e), "hint": "Démarrer avec: docker compose --profile knowledge up -d"}


@router.get("/code/trace")
async def trace_code_path(fn: str, mode: str = "calls"):
    """CBM trace_path — trace les appels/dépendances d'une fonction."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{CBM_URL}/trace_path", json={"function_name": fn, "mode": mode})
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


@router.get("/code/snippet")
async def get_code_snippet(qn: str):
    """CBM get_code_snippet — source d'une fonction par qualified name."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{CBM_URL}/get_code_snippet", json={"qualified_name": qn})
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


@router.get("/code/architecture")
async def get_architecture(aspects: str = "all"):
    """CBM get_architecture — vue d'ensemble du projet."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{CBM_URL}/get_architecture", json={"aspects": aspects.split(",")})
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ---- Sémantique — VectorRAG natif + Graphify (3ème leg Trinité) ----


@router.get("/graph/search")
async def search_graph_semantic(q: str, limit: int = 10):
    """Recherche sémantique — VectorRAG natif (docs) + Graphify (code) si dispo."""
    results = {"rag": None, "graphify": None, "query": q}

    # 1. VectorRAG natif — recherche documentaire hybride
    results["rag"] = _native_semantic_search(q, limit)

    # 2. Graphify — sémantique code (si le serveur MCP est enregistré)
    try:
        import os

        if os.environ.get("ODYSSEUS_GRAPHIFY", "").strip().lower() in ("1", "true", "yes", "on"):
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    "http://localhost:9750/mcp",
                    json={
                        "method": "tools/call",
                        "params": {"name": "graphify_search", "arguments": {"query": q, "limit": limit}},
                    },
                )
                if r.status_code == 200:
                    results["graphify"] = r.json()
    except Exception:
        pass  # Graphify offline — dégradation gracieuse

    return results


@router.get("/graph/status")
async def graphify_status():
    """Statut du knowledge graph Graphify."""
    try:
        import os

        if os.environ.get("ODYSSEUS_GRAPHIFY", "").strip().lower() not in ("1", "true", "yes", "on"):
            return {"available": False, "reason": "ODYSSEUS_GRAPHIFY is OFF"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "http://localhost:9750/mcp",
                json={"method": "tools/call", "params": {"name": "graphify_status", "arguments": {}}},
            )
            if r.status_code == 200:
                return r.json()
            return {"available": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/graph/analyze")
async def graphify_analyze(path: str = None, max_depth: int = 5):
    """Lance une analyse Graphify du codebase (knowledge graph sémantique)."""
    try:
        import os

        if os.environ.get("ODYSSEUS_GRAPHIFY", "").strip().lower() not in ("1", "true", "yes", "on"):
            return {"error": "ODYSSEUS_GRAPHIFY is OFF — enable it to use Graphify"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                "http://localhost:9750/mcp",
                json={
                    "method": "tools/call",
                    "params": {"name": "graphify_analyze", "arguments": {"path": path, "max_depth": max_depth}},
                },
            )
            if r.status_code == 200:
                return r.json()
            return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# ---- Checkpoint Trinité — utilisé avant génération ----


@router.post("/checkpoint")
async def trinite_checkpoint(query: str, context_type: str = "code"):
    """
    Checkpoint Trinité : interroge CBM (structure) + VectorRAG natif (sémantique doc).
    La jambe Obsidian (mémoire persistante) est gérée par le checkpoint_tracker natif
    (mcp_servers/obsidian_mcp.py, gate ODYSSEUS_OBSIDIAN_MCP), pas par ce proxy HTTP.
    """
    results = {"cbm": None, "semantic": None, "query": query}

    # 2. Sémantique doc — VectorRAG natif (synchrone, pas de HTTP)
    results["semantic"] = _native_semantic_search(query, 5)

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. CBM — structure code
        try:
            r = await client.post(f"{CBM_URL}/search_graph", json={"name_pattern": query, "limit": 5})
            results["cbm"] = r.json()
        except Exception:
            results["cbm"] = {"error": "CBM offline"}

    return results


@router.get("/status")
async def knowledge_status():
    """Statut de tous les composants de la Trinité."""
    status = {
        "rag": "online" if get_rag_manager() is not None else "offline",
        "obsidian": "delegated (native checkpoint_tracker + ODYSSEUS_OBSIDIAN_MCP gate)",
    }
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in [("cbm", CBM_URL)]:
            try:
                await client.get(f"{url}/health")
                status[name] = "online"
            except Exception:
                status[name] = "offline"
    return {"trinite": status}


@router.post("/search")
async def knowledge_search():
    """Search the Trinité knowledge bases."""
    return {"results": [], "trinite": {"cbm": "offline", "rag": "offline", "obsidian": "offline"}}
