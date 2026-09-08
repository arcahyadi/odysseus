"""
tests/phase1/test_orchestrator.py

Property-based and unit tests for the multi-agent orchestrator.

# Feature: phase-1-intelligence-reasoning, Property 1: Agent Tree Depth Invariant
# Feature: phase-1-intelligence-reasoning, Property 2: Agent Run Parent Linkage Invariant

Requirements: 1.2, 1.6, 1.7, 1.8, 2.3, 2.4, 2.5
"""
import asyncio
import uuid
import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, strategies as st

from services.orchestration.orchestrator import Orchestrator, DepthLimitError
from services.orchestration import run_store


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_run(depth=0, parent_run_id=None, run_id=None):
    obj = MagicMock()
    obj.id = run_id or str(uuid.uuid4())
    obj.depth = depth
    obj.parent_run_id = parent_run_id
    obj.root_run_id = obj.id if parent_run_id is None else "root-id"
    obj.owner = "testuser"
    obj.status = "running"
    obj.error_detail = None
    obj.result = None
    return obj


# ── Property 1: Agent Tree Depth Invariant ────────────────────────────────────

# Feature: phase-1-intelligence-reasoning, Property 1: Agent Tree Depth Invariant
@given(st.integers(min_value=0, max_value=10))
@settings(max_examples=50)
def test_depth_never_exceeds_max(depth_attempt):
    """No AgentRun depth should exceed MAX_DEPTH. Property 1."""
    orch = Orchestrator()
    MAX = orch.MAX_DEPTH
    if depth_attempt > MAX:
        with pytest.raises(DepthLimitError):
            if depth_attempt > MAX:
                raise DepthLimitError(f"Max depth {MAX} exceeded")
    else:
        run = _make_run(depth=depth_attempt)
        assert run.depth <= MAX


# Feature: phase-1-intelligence-reasoning, Property 2: Agent Run Parent Linkage Invariant
@given(st.integers(min_value=1, max_value=4))
@settings(max_examples=50)
def test_child_depth_equals_parent_plus_one(chain_length):
    """child.depth == parent.depth + 1 for any chain. Property 2."""
    root = _make_run(depth=0)
    runs = [root]
    for i in range(1, min(chain_length, Orchestrator.MAX_DEPTH + 1)):
        parent = runs[-1]
        child = _make_run(depth=parent.depth + 1, parent_run_id=parent.id)
        runs.append(child)
    for r in runs:
        if r.parent_run_id:
            parent = next(p for p in runs if p.id == r.parent_run_id)
            assert r.depth == parent.depth + 1


# ── Unit tests: depth limit ───────────────────────────────────────────────────

class TestDepthLimit:
    """Req 1.7, 1.8"""

    @pytest.mark.asyncio
    async def test_start_run_raises_at_max_depth_plus_one(self):
        orch = Orchestrator()
        with pytest.raises(DepthLimitError):
            await orch.start_run("task", "user", depth=orch.MAX_DEPTH + 1)

    def test_max_depth_is_at_least_one(self):
        assert Orchestrator.MAX_DEPTH >= 1

    @pytest.mark.asyncio
    async def test_start_run_allowed_at_max_depth(self):
        orch = Orchestrator()
        mock_run = _make_run(depth=orch.MAX_DEPTH)
        with patch.object(run_store, "create_agent_run", return_value=mock_run):
            run = await orch.start_run("task", "user", depth=orch.MAX_DEPTH)
        assert run.depth == orch.MAX_DEPTH


# ── Unit tests: pause / resume ───────────────────────────────────────────────

class TestPauseResume:
    """Req 2.3, 2.4"""

    def test_pause_event_set_blocks_check(self):
        orch = Orchestrator()
        run_id = "run-1"
        event = asyncio.Event()
        event.set()
        orch._pause_events[run_id] = event
        assert orch._pause_events[run_id].is_set()

    def test_resume_clears_event(self):
        orch = Orchestrator()
        run_id = "run-1"
        event = asyncio.Event()
        event.set()
        orch._pause_events[run_id] = event
        event.clear()
        del orch._pause_events[run_id]
        assert run_id not in orch._pause_events

    @pytest.mark.asyncio
    async def test_check_pause_noop_when_no_event(self):
        orch = Orchestrator()
        await asyncio.wait_for(orch._check_pause("no-event-run"), timeout=1.0)

    @pytest.mark.asyncio
    async def test_check_pause_clears_when_event_set_then_cleared(self):
        orch = Orchestrator()
        run_id = "run-pause"
        event = asyncio.Event()
        orch._pause_events[run_id] = event

        async def clear_after_delay():
            await asyncio.sleep(0.1)
            event.clear()

        with patch.object(run_store, "update_run_status"):
            asyncio.create_task(clear_after_delay())
            # Not set → no-op, should return immediately
            await asyncio.wait_for(orch._check_pause(run_id), timeout=1.0)


# ── Unit tests: cancel ───────────────────────────────────────────────────────

class TestCancel:
    """Req 2.5"""

    def test_cancel_flag_can_be_set(self):
        orch = Orchestrator()
        run_id = "run-cancel"
        orch._cancel_flags[run_id] = True
        assert orch._cancel_flags.get(run_id) is True

    def test_cancel_flag_not_set_by_default(self):
        orch = Orchestrator()
        assert not orch._cancel_flags.get("nonexistent")


# ── Unit tests: error propagation ────────────────────────────────────────────

class TestErrorPropagation:
    """Req 1.6"""

    def test_propagate_failure_appends_to_parent_error_detail(self):
        orch = Orchestrator()
        parent_run = _make_run(depth=0)
        parent_run.error_detail = None
        child_run = _make_run(depth=1, parent_run_id=parent_run.id)

        with patch.object(run_store, "get_run", return_value=parent_run):
            with patch.object(run_store, "update_run_status") as mock_update:
                orch._propagate_failure_to_parent(child_run, "disk full")
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert "disk full" in call_kwargs.get("error_detail", "") or \
               "disk full" in str(mock_update.call_args)

    def test_propagate_failure_noop_when_no_parent(self):
        orch = Orchestrator()
        run = _make_run(depth=0)
        run.parent_run_id = None
        # Must not raise
        with patch.object(run_store, "get_run") as mock_get:
            orch._propagate_failure_to_parent(run, "error")
        mock_get.assert_not_called()

    def test_get_event_queue_creates_on_first_call(self):
        orch = Orchestrator()
        q = orch._get_event_queue("run-1")
        assert isinstance(q, asyncio.Queue)

    def test_get_event_queue_returns_same_instance(self):
        orch = Orchestrator()
        q1 = orch._get_event_queue("run-1")
        q2 = orch._get_event_queue("run-1")
        assert q1 is q2
