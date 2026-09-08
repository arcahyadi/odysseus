"""
services/orchestration/run_store.py

Database helper functions for AgentRun persistence.

All functions open and close their own DB session via SessionLocal —
no ORM session is passed in from outside. Errors are logged with
logger.warning and swallowed; each function returns a sensible
default (None / False / 0 / []) on failure so callers can proceed
without try/except boilerplate.

Requirements: 1.2, 12.1, 12.2, 12.3, 12.4, 12.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, or_

from core.database import AgentRun, SessionLocal, utcnow_naive

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _naive_utc(dt: datetime) -> datetime:
    """Strip timezone info so SQLite DateTime columns accept the value."""
    if dt is None:
        return dt
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_agent_run(
    id: str,
    owner: Optional[str],
    task_description: str,
    persona_id: Optional[str] = None,
    session_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    depth: int = 0,
    root_run_id: Optional[str] = None,
) -> Optional[AgentRun]:
    """
    Persist a new AgentRun record in *running* status.

    Sets started_at = utcnow_naive() and status = "running".
    Returns the freshly created AgentRun or None on failure.

    Requirements: 1.2, 12.1
    """
    # Derive root_run_id: a root run points to itself; a child inherits the
    # root_run_id passed by its parent (which must always be set by the caller).
    effective_root_run_id = id if parent_run_id is None else root_run_id

    db = SessionLocal()
    try:
        run = AgentRun(
            id=id,
            owner=owner,
            task_description=task_description,
            persona_id=persona_id,
            session_id=session_id,
            parent_run_id=parent_run_id,
            depth=depth,
            root_run_id=effective_root_run_id,
            status="running",
            started_at=utcnow_naive(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        db.rollback()
        logger.warning("create_agent_run failed for id=%s: %s", id, exc)
        return None
    finally:
        db.close()


def update_run_status(
    run_id: str,
    status: str,
    result: Optional[str] = None,
    error_detail: Optional[str] = None,
    ended_at: Optional[datetime] = None,
) -> bool:
    """
    Update the status (and optional result / error_detail / ended_at) of an
    existing AgentRun.

    Returns True on success, False on failure.

    Requirements: 12.1, 12.2
    """
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run is None:
            logger.warning("update_run_status: run_id=%s not found", run_id)
            return False

        run.status = status
        if result is not None:
            run.result = result
        if error_detail is not None:
            run.error_detail = error_detail
        if ended_at is not None:
            run.ended_at = _naive_utc(ended_at)
        elif status in ("completed", "failed", "cancelled") and run.ended_at is None:
            run.ended_at = utcnow_naive()

        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        logger.warning("update_run_status failed for run_id=%s: %s", run_id, exc)
        return False
    finally:
        db.close()


def get_run(run_id: str) -> Optional[AgentRun]:
    """
    Return the AgentRun with the given id, or None if it doesn't exist.

    Requirements: 12.3
    """
    db = SessionLocal()
    try:
        return db.query(AgentRun).filter(AgentRun.id == run_id).first()
    except Exception as exc:
        logger.warning("get_run failed for run_id=%s: %s", run_id, exc)
        return None
    finally:
        db.close()


def list_runs_for_owner(
    owner: str,
    status: Optional[str] = None,
    root_run_id: Optional[str] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
) -> List[AgentRun]:
    """
    Return AgentRun records owned by *owner*, optionally filtered by status,
    root_run_id, and/or a created_at date range.

    Results are ordered by created_at descending (newest first).

    Requirements: 12.2
    """
    db = SessionLocal()
    try:
        q = db.query(AgentRun).filter(AgentRun.owner == owner)

        if status is not None:
            q = q.filter(AgentRun.status == status)

        if root_run_id is not None:
            q = q.filter(AgentRun.root_run_id == root_run_id)

        if from_dt is not None:
            q = q.filter(AgentRun.created_at >= _naive_utc(from_dt))

        if to_dt is not None:
            q = q.filter(AgentRun.created_at <= _naive_utc(to_dt))

        return q.order_by(AgentRun.created_at.desc()).all()
    except Exception as exc:
        logger.warning("list_runs_for_owner failed for owner=%s: %s", owner, exc)
        return []
    finally:
        db.close()


def get_subtree(root_run_id: str) -> List[AgentRun]:
    """
    Return all AgentRun records whose root_run_id matches the given value,
    plus the root run itself (which has root_run_id = its own id OR
    root_run_id IS NULL but id = root_run_id).

    Uses the denormalised root_run_id column for a single-query O(1) lookup.
    Ordered by depth asc, created_at asc so the tree can be rendered top-down.

    Requirements: 12.3
    """
    db = SessionLocal()
    try:
        runs = (
            db.query(AgentRun)
            .filter(
                or_(
                    AgentRun.root_run_id == root_run_id,
                    AgentRun.id == root_run_id,
                )
            )
            .order_by(AgentRun.depth.asc(), AgentRun.created_at.asc())
            .all()
        )
        # Deduplicate in case root's root_run_id == its own id (both clauses match).
        seen: set[str] = set()
        unique: List[AgentRun] = []
        for r in runs:
            if r.id not in seen:
                seen.add(r.id)
                unique.append(r)
        return unique
    except Exception as exc:
        logger.warning("get_subtree failed for root_run_id=%s: %s", root_run_id, exc)
        return []
    finally:
        db.close()


def bulk_update_status(run_ids: List[str], status: str) -> int:
    """
    Set *status* on every AgentRun whose id is in run_ids in a single UPDATE.

    Returns the number of rows actually updated, or 0 on failure.

    Requirements: 12.1, 12.4
    """
    if not run_ids:
        return 0
    db = SessionLocal()
    try:
        updated = (
            db.query(AgentRun)
            .filter(AgentRun.id.in_(run_ids))
            .update({"status": status}, synchronize_session="fetch")
        )
        db.commit()
        return updated
    except Exception as exc:
        db.rollback()
        logger.warning("bulk_update_status failed: %s", exc)
        return 0
    finally:
        db.close()


def prune_expired_runs(retention_days: int = 90) -> int:
    """
    Delete root AgentRun records (parent_run_id IS NULL) whose created_at is
    older than *retention_days* days.

    FK ON DELETE CASCADE propagates the delete to all child AgentRun rows in
    the same tree automatically.

    Returns the number of root rows deleted, or 0 on failure.

    Requirements: 12.4, 12.5
    """
    db = SessionLocal()
    try:
        cutoff = utcnow_naive() - timedelta(days=retention_days)
        roots = (
            db.query(AgentRun)
            .filter(
                and_(
                    AgentRun.parent_run_id.is_(None),
                    AgentRun.created_at < cutoff,
                )
            )
            .all()
        )
        count = len(roots)
        for root in roots:
            db.delete(root)
        db.commit()
        return count
    except Exception as exc:
        db.rollback()
        logger.warning("prune_expired_runs failed: %s", exc)
        return 0
    finally:
        db.close()
