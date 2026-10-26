"""Diagnostics routes — admin-only service health, log tail, and DB stats."""

import logging
import os
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request

from core.constants import DATA_DIR
from core.middleware import require_admin

logger = logging.getLogger(__name__)


def setup_diagnostics_routes(
    rag_manager,
    rag_available: bool,
    memory_vector=None,
) -> APIRouter:
    router = APIRouter(tags=["diagnostics"])

    @router.get("/api/diagnostics/services")
    async def get_service_health(request: Request) -> Dict[str, Any]:
        """Consolidated degraded-state report for ChromaDB, SearXNG, email,
        ntfy, and provider endpoints. Non-intrusive probes — safe to poll."""
        require_admin(request)
        from src.service_health import collect_service_health
        return await collect_service_health(rag_manager, memory_vector)

    @router.get("/api/diagnostics/logs")
    async def get_diagnostics_logs(request: Request, limit: int = 200) -> Dict[str, Any]:
        require_admin(request)
        limit = max(1, min(limit, 1000))
        try:
            log_file = os.path.join(DATA_DIR, "logs", "app.log")
            if not os.path.exists(log_file):
                return {"status": "success", "logs": []}

            # Safe tail read of the log file (max 5MB via rotation)
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            tail_lines = lines[-limit:] if len(lines) > limit else lines
            tail_lines = [line.rstrip('\r\n') for line in tail_lines]

            return {
                "status": "success",
                "logs": tail_lines
            }
        except Exception:
            logger.exception("Diagnostics logs retrieval failed")
            raise HTTPException(500, "Failed to retrieve logs")

    @router.get("/api/db/stats")
    async def get_database_stats(request: Request) -> Dict[str, Any]:
        require_admin(request)
        try:
            from core.database import get_detailed_stats
            return get_detailed_stats()
        except Exception:
            logger.exception("DB stats retrieval failed")
            raise HTTPException(500, "Failed to retrieve database statistics")

    return router
