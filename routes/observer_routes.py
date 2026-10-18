"""Observer routes — read-only drift visibility (UI veracity batch).

Exposes the behavioural drift signal already computed by ``src.observer``
so the admin System panel can render it. Read-only: no mutation, no
kill-switch activation. The Observer keeps persistent inter-run state at
module level, so a fresh instance here reflects the real accumulated drift.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/observer", tags=["observer"])


@router.get("/drift")
async def get_drift():
    """Current behavioural drift summary (honest projection, never fabricated)."""
    try:
        from src.observer import Observer

        summary = Observer().get_summary()
        return {
            "ok": True,
            "drift_level": summary.get("drift_level"),
            "harness_touched": summary.get("harness_touched"),
            "runs_tracked": summary.get("runs_tracked"),
            "latest_codeburn_one_shot_rate": summary.get("latest_codeburn_one_shot_rate"),
            "recommendation": summary.get("recommendation"),
        }
    except Exception as exc:  # pragma: no cover - defensive, never 500 unhandled
        logger.exception("Failed to read observer drift summary")
        return {"ok": False, "error": str(exc)}
