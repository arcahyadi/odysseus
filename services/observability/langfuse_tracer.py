"""
langfuse_tracer.py

LangFuse LLM tracing integration for Odysseus.
Kill-switch: ODYSSEUS_LANGFUSE=off (default).

When OFF: zero overhead, no imports, no network calls.
When ON:  @observe() decorators capture LLM calls, tool usage, agent rounds
          with input/output, token counts, latency, and cost.

Usage:
    from services.observability.langfuse_tracer import observe, trace_langfuse

    @observe()
    async def my_llm_call(...):
        ...

    async with trace_langfuse("my_operation", session_id=sid, user_id=uid) as t:
        t.update(metadata={"key": "value"})
        ...
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kill-switch: ODYSSEUS_LANGFUSE=off by default
# ---------------------------------------------------------------------------
def _check_langfuse_enabled() -> bool:
    """Read the kill-switch at import time.  Returns True when tracing is on."""
    val = os.getenv("ODYSSEUS_LANGFUSE", "off").strip().lower()
    return val in {"on", "1", "true", "yes"}


_LANGFUSE_ENABLED = _check_langfuse_enabled()


# ---------------------------------------------------------------------------
# Lazy LangFuse singleton
# ---------------------------------------------------------------------------
_client: Any = None  # langfuse.Langfuse instance, or None


def _get_client():
    """Return the LangFuse client, initialising once on first call."""
    global _client
    if _client is not None:
        return _client
    try:
        from langfuse import Langfuse

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        if not public_key or not secret_key:
            logger.warning("[langfuse] LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set — tracing disabled")
            return None
        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("[langfuse] Client initialised (host=%s)", host)
        return _client
    except ImportError:
        logger.warning("[langfuse] langfuse package not installed — tracing disabled")
        return None
    except Exception as exc:
        logger.warning("[langfuse] Failed to initialise client: %s", exc)
        return None


# ---------------------------------------------------------------------------
# observe() decorator — drop-in for langfuse.decorators.observe
# When enabled: wraps the function with LangFuse tracing.
# When disabled: returns the original function unchanged (zero overhead).
# ---------------------------------------------------------------------------
def observe(name: str | None = None, **kwargs):
    """Decorator that traces an async/sync function via LangFuse.

    Handles regular functions, coroutines, and async generators.
    When the LangFuse kill-switch is OFF or the client is unavailable,
    the decorator is a transparent pass-through.
    """
    if not _LANGFUSE_ENABLED:

        def _passthrough(fn):
            return fn

        return _passthrough

    try:
        from langfuse.decorators import observe as _lf_observe

        return _lf_observe(name=name, **kwargs)
    except ImportError:

        def _passthrough(fn):
            return fn

        return _passthrough


# ---------------------------------------------------------------------------
# trace_langfuse — manual trace context manager
# For code paths where @observe() isn't practical (e.g. tool_execution.py).
# ---------------------------------------------------------------------------
@asynccontextmanager
async def trace_langfuse(
    name: str,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list | None = None,
    metadata: dict | None = None,
):
    """Async context manager for a LangFuse trace.

    When the kill-switch is OFF or the client is unavailable, yields a
    no-op span so callers never need an ``if enabled`` guard.

    Usage::

        async with trace_langfuse("my_op", session_id="abc", tags=["agent"]) as t:
            t.update(metadata={"round": 3})
            ...
    """
    if not _LANGFUSE_ENABLED:
        yield _NoOpSpan()
        return

    client = _get_client()
    if client is None:
        yield _NoOpSpan()
        return

    try:
        t = client.trace(
            name=name,
            session_id=session_id,
            user_id=user_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        yield t
    except Exception as exc:
        logger.warning("[langfuse] trace '%s' failed: %s", name, exc)
        yield _NoOpSpan()


class _NoOpSpan:
    """Placeholder returned when LangFuse is disabled."""

    def update(self, **kwargs):
        pass

    def generation(self, **kwargs):
        return self

    def span(self, **kwargs):
        return self

    def score(self, **kwargs):
        pass

    def end(self, **kwargs):
        pass
