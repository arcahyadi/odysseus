"""ancestry_tracker — kill-switched bridge that makes governance ancestry live (M3.4).

The native GovernanceManager.create_task_with_ancestry() builds a full
mission>goal>project>task ancestry path, but the live loop (stream_agent_loop)
never called it — ancestry was a route-only feature. This module lets the loop
record a run's ancestry at MEMORY_OBSERVE through one shared, kill-switched call
site (same shape as phase_tracker.py).

SAFETY: OFF by default (ODYSSEUS_GOVERNANCE_ANCESTRY). When OFF, or when the run
has no orchestrated goal context (no project_id), nothing is written and live
behaviour is unchanged. When ON and a project_id is present, one GoalTask with
its ancestry_path is created via the native manager. Best-effort: any fault is
swallowed so it can never break the loop.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def ancestry_enabled() -> bool:
    """OFF unless ODYSSEUS_GOVERNANCE_ANCESTRY is set to a truthy value."""
    val = os.getenv("ODYSSEUS_GOVERNANCE_ANCESTRY", "off").strip().lower()
    return val in {"on", "1", "true", "yes"}


def record_run_ancestry(
    *,
    project_id: str | None,
    task_name: str,
    description: str,
    agent_id: str,
    enabled: bool | None = None,
    manager=None,
) -> dict | None:
    """Record this run's ancestry via the native GovernanceManager.

    No-op (returns None) when the kill-switch is OFF or when there is no
    orchestrated goal context (project_id falsy). Otherwise creates a GoalTask
    carrying its full ancestry_path and returns the manager's result dict.

    Never raises — governance is observational and must not break the loop.
    """
    is_enabled = ancestry_enabled() if enabled is None else bool(enabled)
    if not is_enabled or not project_id:
        return None

    try:
        mgr = manager
        if mgr is None:
            from core.database import SessionLocal
            from src.governance import GovernanceManager

            mgr = GovernanceManager(db_session_factory=SessionLocal)
        result = mgr.create_task_with_ancestry(
            project_id=project_id,
            task_name=task_name,
            description=description,
            agent_id=agent_id,
        )
        if isinstance(result, dict) and result.get("ok"):
            logger.info(
                "[ancestry] recorded project=%s agent=%s path=%s",
                project_id,
                agent_id,
                result.get("ancestry_path", ""),
            )
        return result
    except Exception as exc:
        logger.debug("[ancestry] record ignoré : %s", exc)
        return None
