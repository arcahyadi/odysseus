"""
routes/plan_routes.py

Plan management and execution endpoints.

POST   /api/plans                            — create plan from goal (LLM decomposition)
GET    /api/plans                            — list user's plans
GET    /api/plans/{plan_id}                  — full plan with steps
PUT    /api/plans/{plan_id}                  — update plan metadata
DELETE /api/plans/{plan_id}                  — owner only
POST   /api/plans/{plan_id}/execute          — start/resume execution (background task, 202)
POST   /api/plans/{plan_id}/pause            — pause execution
POST   /api/plans/{plan_id}/cancel           — cancel execution
GET    /api/plans/{plan_id}/steps            — list steps
POST   /api/plans/{plan_id}/steps            — add a step
PUT    /api/plans/{plan_id}/steps/{step_id}  — update step
DELETE /api/plans/{plan_id}/steps/{step_id}  — delete step (guard: cannot delete running step)

Requirements: 5.1–5.6, 6.1, 6.4, 6.6, 6.7
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from services.planning.planner import create_plan
from services.planning.executor import plan_executor
from core.database import Plan, PlanStep, SessionLocal, utcnow_naive
from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreatePlanRequest(BaseModel):
    goal: str
    model: str
    endpoint_url: str


class UpdatePlanRequest(BaseModel):
    title: Optional[str] = None
    goal: Optional[str] = None
    model: Optional[str] = None
    endpoint_url: Optional[str] = None


class CreateStepRequest(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: Optional[int] = None
    # Document-aware execution context (optional)
    doc_id: Optional[str] = None
    doc_action: Optional[str] = None  # "create" | "update" | "edit" | "suggest" | "read"


class CreateDocumentStepRequest(BaseModel):
    """Create a document-aware step (alternative to CreateStepRequest)."""
    title: str
    description: Optional[str] = None
    order_index: Optional[int] = None
    doc_id: str
    doc_action: str  # "create" | "update" | "edit" | "suggest" | "read"
    session_id: Optional[str] = None


class FromDocumentRequest(BaseModel):
    """Create (and optionally execute) a plan from an editor document."""

    document_id: str
    auto_execute: bool = False


class UpdateStepRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _plan_dict(plan: Plan) -> dict:
    """Serialize a Plan to the standard summary shape."""
    steps = getattr(plan, "steps", None) or []
    step_count = len(steps)
    done_count = sum(1 for s in steps if s.status == "done")
    return {
        "id": plan.id,
        "owner": plan.owner,
        "title": plan.title,
        "goal": plan.goal,
        "status": plan.status,
        "current_step_index": plan.current_step_index,
        "model": plan.model,
        "endpoint_url": plan.endpoint_url,
        "step_count": step_count,
        "done_count": done_count,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _plan_full_dict(plan: Plan) -> dict:
    """Serialize a Plan including its ordered steps."""
    data = _plan_dict(plan)
    data["steps"] = [_step_dict(s) for s in (plan.steps or [])]
    return data


def _step_dict(step: PlanStep) -> dict:
    """Serialize a PlanStep."""
    return {
        "id": step.id,
        "plan_id": step.plan_id,
        "order_index": step.order_index,
        "title": step.title,
        "description": step.description,
        "status": step.status,
        "output": step.output,
        "error_detail": step.error_detail,
        "retry_count": step.retry_count,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "ended_at": step.ended_at.isoformat() if step.ended_at else None,
        "doc_id": step.doc_id,
        "doc_action": step.doc_action,
    }


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------

def _get_plan_for_user(db, plan_id: str, user: Optional[str]) -> Plan:
    """
    Load a Plan by id. Raises 404 if not found.
    Raises 403 if the plan is owned by someone else.

    When user is None or empty (single-user / auth-disabled mode) we skip the
    ownership check so the operator can still manage plans.
    """
    plan: Optional[Plan] = db.query(Plan).filter_by(id=plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if user and plan.owner and plan.owner != user:
        raise HTTPException(status_code=403, detail="Access denied")
    return plan


def _get_step_for_plan(db, plan: Plan, step_id: str) -> PlanStep:
    """Load a PlanStep that belongs to *plan*. Raises 404 if not found."""
    step: Optional[PlanStep] = (
        db.query(PlanStep).filter_by(id=step_id, plan_id=plan.id).first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


# ---------------------------------------------------------------------------
# POST /api/plans — create plan from goal
# ---------------------------------------------------------------------------

@router.post("/api/plans", status_code=201)
async def create_plan_endpoint(body: CreatePlanRequest, request: Request):
    """
    Decompose a goal into steps via LLM and persist the plan.

    Requirements: 5.1, 5.2, 5.3, 5.4
    """
    user = get_current_user(request)

    try:
        plan = await create_plan(
            owner=user or "",
            goal=body.goal,
            endpoint_url=body.endpoint_url,
            model=body.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Plan creation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Plan creation failed")

    # Re-fetch with steps so step_count / done_count are correct.
    db = SessionLocal()
    try:
        fresh = db.query(Plan).filter_by(id=plan.id).first()
        if fresh is None:
            raise HTTPException(status_code=500, detail="Plan not found after creation")
        return _plan_dict(fresh)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/plans/from-document — turn an editor document into an executable plan
# ---------------------------------------------------------------------------

@router.post("/api/plans/from-document", status_code=201)
async def create_plan_from_document(body: FromDocumentRequest, request: Request):
    """
    Create a plan whose goal is the current content of a document, resolving
    the owner's default task model/endpoint server-side. Optionally starts
    execution immediately (202 semantics handled by the caller via the plan id).

    Requirements: 5.1-5.6 (doc-to-action bridge)
    """
    from core.database import Document as _DocModel
    from src.task_endpoint import resolve_task_endpoint

    user = get_current_user(request)
    db = SessionLocal()
    try:
        query = db.query(_DocModel).filter(_DocModel.id == body.document_id)
        if user:
            from src.auth_helpers import owner_filter
            query = owner_filter(query, _DocModel, user)
        doc = query.first()
    finally:
        db.close()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        url, model, headers = resolve_task_endpoint(
            endpoint_url=None, model=None, headers=None, owner=user or "",
        )
    except Exception:
        url, model, headers = None, None, None
    if not url or not model:
        raise HTTPException(
            status_code=400,
            detail="No default model endpoint configured — add one in Settings first",
        )

    raw_content = (getattr(doc, "current_content", None) or "").strip()
    if not raw_content:
        raise HTTPException(status_code=422, detail="Document is empty — nothing to plan")

    title = (getattr(doc, "title", None) or "").strip() or "Untitled document"
    goal = (
        f"Execute the plan described in the document \"{title}\" step by step.\n\n"
        f"--- Document content ---\n{raw_content[:6000]}"
    )

    try:
        plan = await create_plan(
            owner=user or "",
            goal=goal,
            endpoint_url=url,
            model=model,
            headers=headers or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Plan-from-document creation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Plan creation failed")

    if body.auto_execute:
        asyncio.create_task(plan_executor.execute(
            plan_id=plan.id,
            owner=user or "",
            endpoint_url=url,
            model=model,
            headers=headers or {},
        ))

    db = SessionLocal()
    try:
        fresh = db.query(Plan).filter_by(id=plan.id).first()
        if fresh is None:
            raise HTTPException(status_code=500, detail="Plan not found after creation")
        result = _plan_dict(fresh)
        result["auto_executed"] = body.auto_execute
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/plans — list user's plans
# ---------------------------------------------------------------------------

@router.get("/api/plans")
def list_plans(request: Request):
    """
    Return all plans owned by the current user, most recent first.

    Requirements: 5.5
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        query = db.query(Plan).order_by(Plan.created_at.desc())
        if user:
            query = query.filter(Plan.owner == user)
        plans = query.all()
        return [_plan_dict(p) for p in plans]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/plans/{plan_id} — full plan with steps
# ---------------------------------------------------------------------------

@router.get("/api/plans/{plan_id}")
def get_plan(plan_id: str, request: Request):
    """
    Return a plan and all its steps.

    Requirements: 5.5
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)
        return _plan_full_dict(plan)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# PUT /api/plans/{plan_id} — update plan metadata
# ---------------------------------------------------------------------------

@router.put("/api/plans/{plan_id}")
def update_plan(plan_id: str, body: UpdatePlanRequest, request: Request):
    """
    Update mutable metadata fields on a plan.

    Requirements: 5.5
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)

        if body.title is not None:
            plan.title = body.title
        if body.goal is not None:
            plan.goal = body.goal
        if body.model is not None:
            plan.model = body.model
        if body.endpoint_url is not None:
            plan.endpoint_url = body.endpoint_url

        db.commit()
        db.refresh(plan)
        return _plan_dict(plan)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Plan update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Plan update failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# DELETE /api/plans/{plan_id} — owner only
# ---------------------------------------------------------------------------

@router.delete("/api/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str, request: Request):
    """
    Delete a plan and all its steps (cascade).

    Requirements: 5.6
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)
        db.delete(plan)
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Plan deletion failed: %s", exc)
        raise HTTPException(status_code=500, detail="Plan deletion failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/plans/{plan_id}/execute — start / resume execution (202)
# ---------------------------------------------------------------------------

@router.post("/api/plans/{plan_id}/execute", status_code=202)
async def execute_plan(plan_id: str, request: Request):
    """
    Fire-and-forget execution of the plan's steps.

    Uses model / endpoint_url stored on the plan record.

    Requirements: 6.1, 6.4
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)
        model = plan.model or ""
        endpoint_url = plan.endpoint_url or ""
        owner = plan.owner or user or ""
    finally:
        db.close()

    # Resume: clear any lingering pause/cancel flags before starting.
    plan_executor.resume(plan_id)

    asyncio.create_task(
        plan_executor.execute(
            plan_id=plan_id,
            owner=owner,
            endpoint_url=endpoint_url,
            model=model,
        )
    )

    return {"ok": True, "plan_id": plan_id, "status": "running"}


# ---------------------------------------------------------------------------
# POST /api/plans/{plan_id}/pause — pause execution
# ---------------------------------------------------------------------------

@router.post("/api/plans/{plan_id}/pause")
def pause_plan(plan_id: str, request: Request):
    """
    Signal the executor to pause after the current step completes.

    Requirements: 6.6
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        _get_plan_for_user(db, plan_id, user)
    finally:
        db.close()

    plan_executor.pause(plan_id)
    return {"ok": True, "plan_id": plan_id, "status": "paused"}


# ---------------------------------------------------------------------------
# POST /api/plans/{plan_id}/cancel — cancel execution
# ---------------------------------------------------------------------------

@router.post("/api/plans/{plan_id}/cancel")
def cancel_plan(plan_id: str, request: Request):
    """
    Signal the executor to cancel the plan at the next loop iteration.

    Requirements: 6.7
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        _get_plan_for_user(db, plan_id, user)
    finally:
        db.close()

    plan_executor.cancel(plan_id)
    return {"ok": True, "plan_id": plan_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# GET /api/plans/{plan_id}/steps — list steps
# ---------------------------------------------------------------------------

@router.get("/api/plans/{plan_id}/steps")
def list_steps(plan_id: str, request: Request):
    """
    Return all steps for a plan ordered by order_index.

    Requirements: 5.5
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)
        steps = (
            db.query(PlanStep)
            .filter_by(plan_id=plan.id)
            .order_by(PlanStep.order_index)
            .all()
        )
        return [_step_dict(s) for s in steps]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/plans/{plan_id}/steps — add a step
# ---------------------------------------------------------------------------

@router.post("/api/plans/{plan_id}/steps", status_code=201)
def create_step(plan_id: str, body: CreateStepRequest, request: Request):
    """
    Append (or insert) a new step into the plan.

    If order_index is not supplied, the step is appended after the last
    existing step.

    Requirements: 5.2
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)

        # Determine order_index
        if body.order_index is not None:
            order_index = body.order_index
        else:
            last = (
                db.query(PlanStep)
                .filter_by(plan_id=plan.id)
                .order_by(PlanStep.order_index.desc())
                .first()
            )
            order_index = (last.order_index + 1) if last else 0

        step = PlanStep(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            order_index=order_index,
            title=body.title[:120],
            description=body.description,
            status="pending",
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        return _step_dict(step)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Step creation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Step creation failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# PUT /api/plans/{plan_id}/steps/{step_id} — update step
# ---------------------------------------------------------------------------

@router.put("/api/plans/{plan_id}/steps/{step_id}")
def update_step(plan_id: str, step_id: str, body: UpdateStepRequest, request: Request):
    """
    Update title, description, or status of a step.

    Requirements: 5.5
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)
        step = _get_step_for_plan(db, plan, step_id)

        if body.title is not None:
            step.title = body.title[:120]
        if body.description is not None:
            step.description = body.description
        if body.status is not None:
            step.status = body.status

        db.commit()
        db.refresh(step)
        return _step_dict(step)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Step update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Step update failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/plans/{plan_id}/steps/document — create document-aware step
# ---------------------------------------------------------------------------

@router.post("/api/plans/{plan_id}/steps/document", status_code=201)
def create_document_step(plan_id: str, body: CreateDocumentStepRequest, request: Request):
    """
    Create a document-aware step that will execute document operations
    (create/update/edit/suggest/read) using existing document tools.

    Requirements: Document-to-action pipeline support
    """
    from core.database import Document as _DocModel

    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)

        # Verify document ownership
        doc = db.query(_DocModel).filter(_DocModel.id == body.doc_id).first()
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if user and doc.owner and doc.owner != user:
            raise HTTPException(status_code=403, detail="Document access denied")

        # Validate doc_action
        valid_actions = ("create", "update", "edit", "suggest", "read")
        if body.doc_action not in valid_actions:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid doc_action. Must be one of: {', '.join(valid_actions)}",
            )

        # Determine order_index
        if body.order_index is not None:
            order_index = body.order_index
        else:
            last = (
                db.query(PlanStep)
                .filter_by(plan_id=plan.id)
                .order_by(PlanStep.order_index.desc())
                .first()
            )
            order_index = (last.order_index + 1) if last else 0

        step = PlanStep(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            order_index=order_index,
            title=body.title[:120],
            description=body.description,
            doc_id=body.doc_id,
            doc_action=body.doc_action,
            session_id=body.session_id,
            status="pending",
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        return _step_dict(step)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Document step creation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Document step creation failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# DELETE /api/plans/{plan_id}/steps/{step_id} — delete step
# ---------------------------------------------------------------------------

@router.delete("/api/plans/{plan_id}/steps/{step_id}", status_code=204)
def delete_step(plan_id: str, step_id: str, request: Request):
    """
    Delete a step. Guard: cannot delete a step that is currently running.

    Requirements: 5.6
    """
    user = get_current_user(request)
    db = SessionLocal()
    try:
        plan = _get_plan_for_user(db, plan_id, user)
        step = _get_step_for_plan(db, plan, step_id)

        if step.status == "running":
            raise HTTPException(status_code=409, detail="Cannot delete a running step")

        db.delete(step)
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Step deletion failed: %s", exc)
        raise HTTPException(status_code=500, detail="Step deletion failed")
    finally:
        db.close()
