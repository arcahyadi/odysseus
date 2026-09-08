"""
services/orchestration/orchestrator.py

Orchestrator — spawns sub-agents, enforces depth limits, wires pause/cancel
control, and delivers SSE events to callers via per-root-run asyncio queues.

Design notes
------------
* _pause_events[run_id] is an asyncio.Event used as a PAUSED flag:
    - set()   → run is paused  (_check_pause will spin until cleared)
    - clear() → run is running (_check_pause returns immediately)
* _cancel_flags[run_id] is a plain bool; True = cancel requested.
* _run_event_queues[root_run_id] is an asyncio.Queue(maxsize=500) feeding
  the SSE StreamingResponse for the tree rooted at root_run_id.
* _stream_agent_loop is an intentional STUB; real wiring arrives in task 11.1.

Requirements: 1.1–1.8
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Optional

from core.database import AgentRun, utcnow_naive
from services.orchestration import run_store

logger = logging.getLogger(__name__)


class DepthLimitError(Exception):
    """Raised when an agent delegation would exceed MAX_DEPTH."""


class Orchestrator:
    MAX_DEPTH = int(os.getenv("AGENT_MAX_DEPTH", "3"))

    def __init__(self, session_manager=None, memory_manager=None):
        self._session_manager = session_manager
        self._memory_manager = memory_manager
        # run_id -> asyncio.Event  (set = paused, clear = running)
        self._pause_events: dict[str, asyncio.Event] = {}
        # run_id -> bool  (True = cancel requested)
        self._cancel_flags: dict[str, bool] = {}
        # run_id -> asyncio.Queue  (SSE event delivery)
        self._run_event_queues: dict[str, asyncio.Queue] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_run(
        self,
        task: str,
        owner: str,
        persona_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        depth: int = 0,
        session_id: Optional[str] = None,
        root_run_id: Optional[str] = None,
    ) -> AgentRun:
        """
        Create a new AgentRun record and fire off its execution as an asyncio Task.

        Requirements: 1.1, 1.2, 1.7, 1.8
        """
        if depth > self.MAX_DEPTH:
            raise DepthLimitError(f"Max agent depth {self.MAX_DEPTH} exceeded")

        run_id = str(uuid.uuid4())
        # root_run_id: root points to itself; children inherit the parent's root.
        effective_root = run_id if parent_run_id is None else root_run_id

        run = run_store.create_agent_run(
            id=run_id,
            owner=owner,
            task_description=task,
            persona_id=persona_id,
            session_id=session_id,
            parent_run_id=parent_run_id,
            depth=depth,
            root_run_id=effective_root,
        )
        if run is None:
            raise RuntimeError(f"Failed to create AgentRun record for task: {task!r}")

        asyncio.create_task(self._execute_run(run, root_run_id=effective_root))
        return run

    # ------------------------------------------------------------------
    # Internal execution pipeline
    # ------------------------------------------------------------------

    async def _execute_run(self, run: AgentRun, root_run_id: str) -> None:
        """
        Drive one agent run to completion (or failure/cancellation).

        Requirements: 1.3, 1.5, 1.6
        """
        try:
            await self._emit_event(
                run.id,
                root_run_id,
                {"type": "agent_run_event", "run_id": run.id, "status": "running"},
            )
            async for _chunk in self._agent_loop_with_hooks(run):
                await self._check_pause(run.id)
                if self._cancel_flags.get(run.id):
                    run_store.update_run_status(run.id, "cancelled")
                    await self._emit_event(
                        run.id,
                        root_run_id,
                        {"type": "agent_run_event", "run_id": run.id, "status": "cancelled"},
                    )
                    return

            run_store.update_run_status(run.id, "completed")
            await self._emit_event(
                run.id,
                root_run_id,
                {"type": "agent_run_event", "run_id": run.id, "status": "completed"},
            )
        except DepthLimitError as exc:
            run_store.update_run_status(run.id, "failed", error_detail=str(exc))
            self._propagate_failure_to_parent(run, str(exc))
            await self._emit_event(
                run.id,
                root_run_id,
                {"type": "agent_run_event", "run_id": run.id, "status": "failed", "error": str(exc)},
            )
        except Exception as exc:
            logger.exception("AgentRun %s failed: %s", run.id, exc)
            run_store.update_run_status(run.id, "failed", error_detail=str(exc))
            self._propagate_failure_to_parent(run, str(exc))
            await self._emit_event(
                run.id,
                root_run_id,
                {"type": "agent_run_event", "run_id": run.id, "status": "failed", "error": str(exc)},
            )

    async def _agent_loop_with_hooks(self, run: AgentRun):
        """
        Async generator that wraps _stream_agent_loop.

        Intercepts ``delegate_to_subagent`` tool calls: spawns a sub-run,
        awaits its result, and injects it back as a tool_result chunk.
        All other chunks are forwarded unchanged.

        STUB — real agent-loop wiring is added in task 11.1.

        Requirements: 1.3, 1.4, 1.7, 1.8
        """
        async for chunk in self._stream_agent_loop(run):
            if isinstance(chunk, dict) and chunk.get("tool_name") == "delegate_to_subagent":
                sub_task = chunk.get("arguments", {}).get("task", "")
                sub_persona = chunk.get("arguments", {}).get("persona_id")
                try:
                    sub_run = await self.start_run(
                        task=sub_task,
                        owner=run.owner,
                        persona_id=sub_persona,
                        parent_run_id=run.id,
                        depth=run.depth + 1,
                        root_run_id=run.root_run_id,
                    )
                    result = await self._await_run_result(sub_run.id)
                    yield {"type": "tool_result", "content": result}
                except DepthLimitError as exc:
                    yield {"type": "tool_error", "content": str(exc)}
            else:
                yield chunk

    async def _stream_agent_loop(self, run: AgentRun):
        """
        STUB — yields nothing until task 11.1 wires in the real streaming loop.

        Replaced by wrapping the existing stream_agent_loop from
        routes/chat_helpers.py in the next phase.
        """
        return
        yield  # pragma: no cover — makes this an async generator

    async def _await_run_result(self, run_id: str, timeout: float = 300.0) -> str:
        """
        Poll until the given run reaches a terminal state, then return its
        result text.  Falls back to a timeout message after *timeout* seconds.

        Requirements: 1.5
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            run = run_store.get_run(run_id)
            if run and run.status in ("completed", "failed", "cancelled"):
                return run.result or run.error_detail or ""
            if asyncio.get_event_loop().time() > deadline:
                return "[timeout waiting for sub-agent]"
            await asyncio.sleep(0.5)

    # ------------------------------------------------------------------
    # Pause / cancel helpers
    # ------------------------------------------------------------------

    async def _check_pause(self, run_id: str) -> None:
        """
        Block while the pause event for *run_id* is set; no-op otherwise.

        The event acts as a PAUSED flag:
          set()   → paused  (we spin here)
          clear() → running (we return immediately)

        Uses poll-based sleep to avoid the race inherent in wait() on a
        set event (which would return immediately rather than blocking).

        Requirements: 1.6, 2.3, 2.4
        """
        event = self._pause_events.get(run_id)
        if event is None or not event.is_set():
            return

        run_store.update_run_status(run_id, "paused")
        while event.is_set():
            await asyncio.sleep(0.1)
        # Event was cleared — resumed
        run_store.update_run_status(run_id, "running")

    def _propagate_failure_to_parent(self, run: AgentRun, error: str) -> None:
        """
        Append sub-agent failure detail to the parent run's error_detail so
        the root caller can see a full failure trace.

        Requirements: 1.5
        """
        if not run.parent_run_id:
            return
        parent = run_store.get_run(run.parent_run_id)
        if parent:
            existing = parent.error_detail or ""
            run_store.update_run_status(
                parent.id,
                parent.status,
                error_detail=f"{existing}\n[subagent {run.id} failed] {error}".strip(),
            )

    # ------------------------------------------------------------------
    # SSE event queue helpers
    # ------------------------------------------------------------------

    def _get_event_queue(self, run_id: str) -> asyncio.Queue:
        """Return (creating if necessary) the SSE queue for *run_id*."""
        if run_id not in self._run_event_queues:
            self._run_event_queues[run_id] = asyncio.Queue(maxsize=500)
        return self._run_event_queues[run_id]

    async def _emit_event(self, run_id: str, root_run_id: str, event_data: dict) -> None:
        """
        Put *event_data* onto the root run's SSE queue.

        Drops the event (with a warning) if the queue is full to avoid
        blocking the agent execution path.

        Requirements: 2.1, 2.2
        """
        q = self._get_event_queue(root_run_id)
        try:
            q.put_nowait(event_data)
        except asyncio.QueueFull:
            logger.warning(
                "Event queue full for root_run=%s, dropping event", root_run_id
            )


# ---------------------------------------------------------------------------
# Module-level singleton — shared across the process
# ---------------------------------------------------------------------------

orchestrator = Orchestrator()
