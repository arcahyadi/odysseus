"""
event_bus.py

Lightweight event bus for triggering automation tasks based on events
like session creation, message sends, etc.

Also provides a pub/sub EventBus with SSE/JSONL/WS transports
for the cockpit UI, decision engine, and audit trails.
"""

import asyncio
import json
import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from fnmatch import fnmatch

from src.constants import AUTH_FILE
from src.app_context import app_context


logger = logging.getLogger(__name__)

app_context.caches.task_scheduler = None


def set_task_scheduler(scheduler):
    """Wire up the scheduler reference (called from app.py on startup)."""
    app_context.caches.task_scheduler = scheduler


def get_task_scheduler():
    """Return the current task scheduler instance."""
    return app_context.caches.task_scheduler


def fire_event(event_name: str, owner: str | None = None):
    """Fire an event — increments counters and triggers tasks that hit threshold.

    Safe to call from both sync and async contexts.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_handle_event(event_name, owner))
    except RuntimeError:
        # No running loop — run in a new one (shouldn't happen in FastAPI)
        asyncio.run(_handle_event(event_name, owner))


def _resolve_event_owner(owner: str | None) -> str | None:
    """Resolve ownerless app events to the primary configured user.

    Some event sources run from localhost/internal code paths where request
    middleware is not present, so they cannot pass a username. Treating that as
    "all owners" made built-in tasks run once per account. Instead, route those
    events to the first admin account, matching the legacy-owner migration.
    """
    owner = (owner or "").strip()
    if owner:
        return owner

    try:
        auth_path = AUTH_FILE
        with open(auth_path, encoding="utf-8") as f:
            users = json.load(f).get("users") or {}
        for username, data in users.items():
            if data.get("is_admin") is True:
                return username
        if users:
            return next(iter(users))
    except Exception:
        logger.debug("Could not resolve ownerless event owner", exc_info=True)
    return None


async def _handle_event(event_name: str, owner: str | None = None):
    """Process an event: increment counters, fire tasks that hit their threshold."""
    from core.database import ScheduledTask, SessionLocal

    resolved_owner = _resolve_event_owner(owner)
    db = SessionLocal()
    try:
        filters = [
            ScheduledTask.trigger_type == "event",
            ScheduledTask.trigger_event == event_name,
            ScheduledTask.status == "active",
        ]
        if resolved_owner:
            filters.append(ScheduledTask.owner == resolved_owner)
        else:
            filters.append(ScheduledTask.owner == None)  # noqa: E711

        tasks = db.query(ScheduledTask).filter(*filters).all()
        if not tasks:
            return

        for task in tasks:
            threshold = task.trigger_count or 1
            task.trigger_counter = (task.trigger_counter or 0) + 1

            if task.trigger_counter >= threshold:
                task.trigger_counter = 0
                # Persist the trigger before handing off to the in-memory
                # scheduler. If the process restarts while the task is queued
                # behind a model call, `next_run <= now` makes the trigger
                # survive reboot instead of losing the event after the counter
                # has already reset.
                task.next_run = datetime.utcnow()
                db.commit()
                # Fire the task
                if app_context.caches.task_scheduler:
                    logger.info(f"Event '{event_name}' triggered task '{task.name}' (every {threshold})")
                    await app_context.caches.task_scheduler.run_task_now(task.id)
                else:
                    logger.warning(f"Event triggered task '{task.name}' but no scheduler available")
            else:
                db.commit()
                logger.debug(f"Event '{event_name}': task '{task.name}' counter {task.trigger_counter}/{threshold}")

    except Exception:
        logger.exception(f"Error handling event '{event_name}'")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  NEW: EventBus — pub/sub with SSE / JSONL / WS, pattern matching, 62 types
# ═══════════════════════════════════════════════════════════════════════════════

# 15 families, 62 event types
EVENT_FAMILIES: dict[str, tuple[str, ...]] = {
    "phase": ("phase_enter", "phase_exit", "phase_skip", "phase_error"),
    "tool": ("tool_start", "tool_output", "tool_error", "tool_blocked", "tool_retry"),
    "agent": ("agent_spawn", "agent_report", "agent_error", "agent_done"),
    "model": ("model_info", "model_fallback", "model_error", "model_blacklisted"),
    "memory": ("memory_read", "memory_write", "memory_recall", "memory_forget"),
    "budget": ("budget_update", "budget_alert", "budget_exhausted"),
    "security": ("security_block", "security_allow", "security_warn", "security_audit"),
    "workflow": ("workflow_start", "workflow_checkpoint", "workflow_resume", "workflow_complete"),
    "discovery": ("discovery_register", "discovery_suggest", "discovery_connect"),
    "search": ("search_web_start", "search_web_result", "search_rag_start", "search_rag_result"),
    "session": ("session_created", "session_compacted", "session_archived"),
    "system": ("system_health", "system_error", "system_deploy", "system_config"),
    "user": ("user_message", "user_feedback", "user_preference"),
    "preference": ("preference_set", "preference_apply", "preference_conflict"),
    "mcp": ("mcp_connect", "mcp_disconnect", "mcp_error", "mcp_discover"),
}


class EventBus:
    """Central event bus — publish/subscribe with pattern matching.

    Transports:
      - SSE:   async generator yielding `data: {json}\\n\\n` for cockpit UI
      - JSONL: append one JSON line per event for audit trails
      - WS:    (placeholder) broadcast to registered WebSocket clients
    """

    def __init__(self):
        self._subscribers: list[tuple[str, Callable]] = []
        self._ws_clients: list = []
        self._jsonl_path: str | None = None
        self._jsonl_lock = threading.Lock()
        self._lock = threading.Lock()

    # ── pub/sub ──────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, callback: Callable) -> None:
        """Subscribe to events matching *pattern* (fnmatch, e.g. 'phase.*')."""
        with self._lock:
            self._subscribers.append((pattern, callback))

    def unsubscribe(self, pattern: str, callback: Callable) -> None:
        """Remove a subscription."""
        with self._lock:
            self._subscribers = [(p, cb) for p, cb in self._subscribers if not (p == pattern and cb == callback)]

    def emit(self, family: str, event_type: str, data: dict) -> dict:
        """Emit an event to all matching subscribers. Thread-safe.

        Returns the full event dict (same as logged to JSONL).
        """
        event = {
            "event_id": uuid.uuid4().hex,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "agentos",
            "type": f"{family}.{event_type}",
            "data": data,
            "trace_id": uuid.uuid4().hex,
        }
        full_type = event["type"]

        # Notify matching subscribers
        with self._lock:
            for pattern, cb in self._subscribers:
                if fnmatch(full_type, pattern) or fnmatch(f"{family}.*", pattern):
                    try:
                        cb(event)
                    except Exception:
                        pass  # subscriber errors must never break the bus

        # JSONL audit
        self._write_jsonl(event)

        # WS broadcast (placeholder)
        for ws in self._ws_clients:
            try:
                ws(event)
            except Exception:
                pass

        return event

    # ── JSONL audit ──────────────────────────────────────────────────────

    def enable_jsonl(self, path: str) -> None:
        """Start writing events to a JSONL file."""
        self._jsonl_path = path

    def disable_jsonl(self) -> None:
        """Stop JSONL logging."""
        self._jsonl_path = None

    def _write_jsonl(self, event: dict) -> None:
        if not self._jsonl_path:
            return
        try:
            with self._jsonl_lock:
                with open(self._jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, default=str) + "\n")
        except Exception:
            pass

    # ── SSE generator (for cockpit) ──────────────────────────────────────

    async def sse_generator(self):
        """Async generator yielding SSE `data:` lines for all events."""
        queue: asyncio.Queue = asyncio.Queue()

        def _cb(event):
            try:
                queue.put_nowait(event)
            except Exception:
                pass

        self.subscribe("*.*", _cb)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.unsubscribe("*.*", _cb)

    # ── WebSocket (placeholder) ──────────────────────────────────────────

    def register_ws_client(self, callback: Callable) -> None:
        """Register a WebSocket callback."""
        self._ws_clients.append(callback)

    def unregister_ws_client(self, callback: Callable) -> None:
        """Remove a WebSocket callback."""
        if callback in self._ws_clients:
            self._ws_clients.remove(callback)


# ── Singleton ────────────────────────────────────────────────────────────────

app_context.caches.bus: EventBus | None = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Return the process-wide singleton EventBus."""
    if app_context.caches.bus is None:
        with _bus_lock:
            if app_context.caches.bus is None:
                app_context.caches.bus = EventBus()
    return app_context.caches.bus


def list_families() -> list[str]:
    """Return names of all 15 event families."""
    return list(EVENT_FAMILIES)


def list_types(family: str) -> tuple[str, ...]:
    """Return event types for a given family."""
    return EVENT_FAMILIES.get(family, ())
