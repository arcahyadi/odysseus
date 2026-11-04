"""
services/orchestration/oversight.py

Pause, resume, and cancel operations for multi-agent runs.
These are called from route handlers in routes/agent_routes.py.

Each function operates on the entire subtree rooted at `root_run_id`
by querying run_store for the full set of descendant AgentRun records,
then signalling the orchestrator's in-memory control structures.

Requirements: 2.3, 2.4, 2.5
"""

import asyncio
import logging

from services.orchestration import run_store
from services.orchestration.orchestrator import orchestrator

logger = logging.getLogger(__name__)


async def pause_run(root_run_id: str) -> bool:
    """Signal all running sub-agents in the given tree to pause.

    For each run in the subtree with status "running", creates and immediately
    sets an asyncio.Event on the orchestrator. The running _execute_run
    coroutine checks this event after every agent loop chunk via _check_pause(),
    which blocks while the event is set — suspending the agent at the next safe
    yield point.

    Args:
        root_run_id: The ID of the root AgentRun whose subtree should be paused.

    Returns:
        True on success, False if an error occurred.

    Requirements: 2.3
    """
    try:
        runs = run_store.get_subtree(root_run_id)
        if not runs:
            logger.warning(
                "pause_run: no runs found in subtree for root_run_id=%s", root_run_id
            )
            return True  # nothing to pause is not an error

        paused = 0
        for run in runs:
            if run.status == "running":
                event = asyncio.Event()
                event.set()  # set = paused; _check_pause blocks while set
                orchestrator._pause_events[run.id] = event
                paused += 1

        logger.info(
            "pause_run: signalled pause for %d running run(s) in subtree of %s",
            paused,
            root_run_id,
        )
        return True

    except Exception:
        logger.exception("pause_run failed for root_run_id=%s", root_run_id)
        return False


async def resume_run(root_run_id: str) -> bool:
    """Unblock all paused sub-agents in the given tree.

    Clears each pause event so that _check_pause() unblocks and the agent
    continues from its last checkpoint. The event is then removed from
    _pause_events so subsequent _check_pause() calls are no-ops.

    Args:
        root_run_id: The ID of the root AgentRun whose subtree should be resumed.

    Returns:
        True on success, False if an error occurred.

    Requirements: 2.4
    """
    try:
        runs = run_store.get_subtree(root_run_id)
        if not runs:
            logger.warning(
                "resume_run: no runs found in subtree for root_run_id=%s", root_run_id
            )
            return True

        resumed = 0
        for run in runs:
            event = orchestrator._pause_events.get(run.id)
            if event is not None:
                event.clear()  # unblocks any coroutine spinning in _check_pause
                del orchestrator._pause_events[run.id]
                resumed += 1

        logger.info(
            "resume_run: resumed %d run(s) (of %d in subtree) for root_run_id=%s",
            resumed,
            len(runs),
            root_run_id,
        )
        return True

    except Exception:
        logger.exception("resume_run failed for root_run_id=%s", root_run_id)
        return False


async def cancel_run(root_run_id: str) -> dict:
    """Immediately cancel all agents in the given tree.

    Cancel is unconditional: it sets the cancel flag for every run in the
    subtree (regardless of status) and bulk-updates their DB status to
    'cancelled' in one operation. The running coroutines will detect the flag
    at their next cancel-flag check and exit without waiting for a graceful
    pause.

    Args:
        root_run_id: The ID of the root AgentRun whose subtree should be cancelled.

    Returns:
        A dict with keys:
            - "cancelled": int — number of run IDs targeted.
            - "run_ids": list[str] — the IDs that were cancelled.
        Returns {"cancelled": 0, "run_ids": []} on failure.

    Requirements: 2.5
    """
    try:
        runs = run_store.get_subtree(root_run_id)
        if not runs:
            logger.warning(
                "cancel_run: no runs found in subtree for root_run_id=%s", root_run_id
            )
            return {"cancelled": 0, "run_ids": []}

        run_ids = [run.id for run in runs]

        # Set in-memory cancel flags so running coroutines self-terminate
        for run_id in run_ids:
            orchestrator._cancel_flags[run_id] = True

        # Bulk-update DB status synchronously — non-blocking, no graceful pause
        run_store.bulk_update_status(run_ids, "cancelled")

        logger.info(
            "cancel_run: cancelled %d run(s) in subtree of %s",
            len(run_ids),
            root_run_id,
        )
        return {"cancelled": len(run_ids), "run_ids": run_ids}

    except Exception:
        logger.exception("cancel_run failed for root_run_id=%s", root_run_id)
        return {"cancelled": 0, "run_ids": []}
