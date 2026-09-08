"""
routes/agent_routes.py

REST + SSE endpoints for multi-agent orchestration runs.

Endpoints
---------
POST   /api/agents/runs                   — start a new root AgentRun
GET    /api/agents/runs                   — list runs for current user
GET    /api/agents/runs/{run_id}          — get single run detail
GET    /api/agents/runs/{run_id}/stream   — SSE stream of run events
POST   /api/agents/runs/{run_id}/pause    — pause a run
POST   /api/agents/runs/{run_id}/resume   — resume a paused run
POST   /api/agents/runs/{run_id}/cancel   — cancel a run
DELETE /api/agents/runs/{run_id}          — owner-only hard delete

All mutating endpoints require the caller to own the run (403 otherwise).
The router is registered in app.py with prefix /api/agents.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 12.1, 12.2, 12.3, 12.4, 12.6
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.orchestration.orchestrator import orchestrator, DepthLimitError
from services.orchestration import run_store
from services.orchestration.oversight import pause_run, resume_run, cancel_run
from src.auth_helpers import get_current_user
from core.database import AgentRun, SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STREAM_TIMEOUT_SECONDS = 30 * 60  # 30 minutes


def _run_to_dict(run: AgentRun) -> dict:
    """Serialise an AgentRun ORM object to a plain JSON-safe dict."""
    return {
        "id": run.id,
        "owner": run.owner,
        "parent_run_id": run.parent_run_id,
        "root_run_id": run.root_run_id,
        "depth": run.depth,
        "task_description": run.task_description,
        "status": run.status,
        "result": run.result,
        "error_detail": run.error_detail,
        "input_tokens": run.input_tokens or 0,
        "output_tokens": run.output_tokens or 0,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _require_user(request: Request) -> str:
    """Return the current username, raising 401 if not authenticated."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _get_owned_run(run_id: str, user: str) -> AgentRun:
    """
    Fetch a run by ID and verify ownership.

    Raises:
        HTTPException 404 — run not found
        HTTPException 403 — run found but owned by someone else
    """
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="AgentRun not found")
    if run.owner != user:
        raise HTTPException(status_code=403, detail="Not authorised to access this run")
    return run


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartRunRequest(BaseModel):
    session_id: str
    task_description: str
    persona_id: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /api/agents/runs  — start a new root AgentRun
# ---------------------------------------------------------------------------

@router.post("/runs")
async def start_agent_run(request: Request, body: StartRunRequest):
    """
    Create and immediately begin executing a new root AgentRun.

    Returns the freshly created AgentRun record as JSON.

    Requirements: 2.1, 2.6, 12.1
    """
    user = _require_user(request)

    try:
        run = await orchestrator.start_run(
            task=body.task_description,
            owner=user,
            persona_id=body.persona_id,
            session_id=body.session_id,
        )
    except DepthLimitError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to start agent run: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create AgentRun")

    return _run_to_dict(run)


# ---------------------------------------------------------------------------
# GET /api/agents/runs  — list runs for current user
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_agent_runs(
    request: Request,
    status: Optional[str] = None,
    root_run_id: Optional[str] = None,
):
    """
    Return all AgentRun records owned by the authenticated user.

    Supports optional `status` and `root_run_id` query filters.

    Requirements: 2.2, 12.2
    """
    user = _require_user(request)

    runs = run_store.list_runs_for_owner(
        owner=user,
        status=status,
        root_run_id=root_run_id,
    )
    return {"runs": [_run_to_dict(r) for r in runs], "total": len(runs)}


# ---------------------------------------------------------------------------
# GET /api/agents/runs/{run_id}  — get single run detail
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str, request: Request):
    """
    Return the full detail of a single AgentRun including its subtree.

    Returns 403 if the caller does not own the run, 404 if it doesn't exist.

    Requirements: 2.6, 12.3
    """
    user = _require_user(request)
    run = _get_owned_run(run_id, user)

    data = _run_to_dict(run)

    # Include direct child run IDs so the caller can explore the tree
    subtree = run_store.get_subtree(run_id)
    child_ids = [r.id for r in subtree if r.parent_run_id == run_id]
    data["child_run_ids"] = child_ids

    return data


# ---------------------------------------------------------------------------
# GET /api/agents/runs/{run_id}/stream  — SSE event stream
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/stream")
async def stream_agent_run_events(run_id: str, request: Request):
    """
    Open a Server-Sent Events stream that delivers real-time updates for the
    run tree rooted at run_id.

    Event types emitted:
      - agent_run_event      : status/progress update for a single run node
      - agent_graph_snapshot : full serialised subtree (all nodes + edges)

    The stream is closed after STREAM_TIMEOUT_SECONDS (30 min) or when the
    client disconnects.

    Requirements: 2.1, 2.2, 2.6, 2.7
    """
    user = _require_user(request)
    _get_owned_run(run_id, user)  # ownership check — raises 403/404 if needed

    async def event_generator():
        queue = orchestrator._get_event_queue(run_id)

        # Immediately emit a snapshot of the current tree state so newly
        # connecting clients get the full picture without waiting for the
        # next event.
        subtree = run_store.get_subtree(run_id)
        if subtree:
            snapshot = {
                "type": "agent_graph_snapshot",
                "root_run_id": run_id,
                "nodes": [_run_to_dict(r) for r in subtree],
            }
            yield f"event: agent_graph_snapshot\ndata: {json.dumps(snapshot)}\n\n"

        deadline = asyncio.get_event_loop().time() + _STREAM_TIMEOUT_SECONDS

        try:
            while True:
                # Respect client disconnect
                if await request.is_disconnected():
                    logger.debug("SSE client disconnected for run_id=%s", run_id)
                    return

                # Check timeout
                if asyncio.get_event_loop().time() > deadline:
                    logger.info("SSE stream timed out for run_id=%s", run_id)
                    return

                # Drain any queued events (non-blocking first, then short wait)
                try:
                    event_data = queue.get_nowait()
                except asyncio.QueueEmpty:
                    # Short sleep to avoid busy-loop; then re-check disconnect
                    await asyncio.sleep(0.25)
                    continue

                event_type = event_data.get("type", "agent_run_event")
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

                # After every agent_run_event, also emit a fresh graph snapshot
                # so the frontend graph view stays in sync without needing to
                # poll a separate endpoint.
                if event_type == "agent_run_event":
                    try:
                        subtree = run_store.get_subtree(run_id)
                        snapshot = {
                            "type": "agent_graph_snapshot",
                            "root_run_id": run_id,
                            "nodes": [_run_to_dict(r) for r in subtree],
                        }
                        yield f"event: agent_graph_snapshot\ndata: {json.dumps(snapshot)}\n\n"
                    except Exception as snap_exc:
                        logger.warning(
                            "Failed to build graph snapshot for run_id=%s: %s",
                            run_id, snap_exc,
                        )

        except asyncio.CancelledError:
            # Client disconnected — exit cleanly
            return
        except Exception as exc:
            logger.exception("SSE stream error for run_id=%s: %s", run_id, exc)
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering for SSE
        },
    )


# ---------------------------------------------------------------------------
# POST /api/agents/runs/{run_id}/pause
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/pause")
async def pause_agent_run(run_id: str, request: Request):
    """
    Signal all running sub-agents in the tree rooted at run_id to pause.

    The pause takes effect at the next safe yield point in each agent loop.

    Requirements: 2.3
    """
    user = _require_user(request)
    run = _get_owned_run(run_id, user)

    ok = await pause_run(run.root_run_id or run_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to pause run")

    # Reflect the paused status in the DB for the root run immediately so
    # callers polling GET /runs/{run_id} see it right away.
    run_store.update_run_status(run_id, "paused")

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/agents/runs/{run_id}/resume
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/resume")
async def resume_agent_run(run_id: str, request: Request):
    """
    Unblock all paused sub-agents in the tree rooted at run_id.

    Requirements: 2.4
    """
    user = _require_user(request)
    run = _get_owned_run(run_id, user)

    ok = await resume_run(run.root_run_id or run_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to resume run")

    run_store.update_run_status(run_id, "running")

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/agents/runs/{run_id}/cancel
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/cancel")
async def cancel_agent_run(run_id: str, request: Request):
    """
    Immediately cancel all agents in the tree rooted at run_id.

    Sets cancel flags in memory and bulk-updates all DB records to 'cancelled'.

    Requirements: 2.5
    """
    user = _require_user(request)
    run = _get_owned_run(run_id, user)

    result = await cancel_run(run.root_run_id or run_id)
    if result.get("cancelled", 0) == 0:
        # cancel_run returns {cancelled:0} on failure; also on an empty subtree
        # which is not a hard error — treat either case as success from the
        # caller's perspective (idempotent cancel is fine).
        logger.info(
            "cancel_agent_run: no runs cancelled for run_id=%s (may be already terminal)",
            run_id,
        )

    return {"ok": True, "cancelled_count": result.get("cancelled", 0)}


# ---------------------------------------------------------------------------
# DELETE /api/agents/runs/{run_id}  — hard delete (owner only)
# ---------------------------------------------------------------------------

@router.delete("/runs/{run_id}")
async def delete_agent_run(run_id: str, request: Request):
    """
    Permanently delete the AgentRun and all descendant runs via FK cascade.

    Only the run's owner may call this endpoint.

    Requirements: 12.4, 12.6
    """
    user = _require_user(request)
    _get_owned_run(run_id, user)  # 403/404 guard

    db = SessionLocal()
    try:
        run_obj = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run_obj is None:
            # Already gone — treat as success (idempotent)
            return {"ok": True}
        db.delete(run_obj)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete AgentRun %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete run")
    finally:
        db.close()

    return {"ok": True}
