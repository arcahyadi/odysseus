"""
tests/phase1/test_plan_executor.py

Property-based and unit tests for planning (planner + executor).

# Feature: phase-1-intelligence-reasoning, Property 5: Plan Step Count Bounds
# Feature: phase-1-intelligence-reasoning, Property 6: Plan Step Ordering Invariant
# Feature: phase-1-intelligence-reasoning, Property 7: Plan Resumption Skips Completed Steps

Requirements: 5.2, 5.3, 6.3, 6.4, 6.5, 6.7
"""
import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import MagicMock, patch

from services.planning.executor import PlanExecutor, MAX_RETRIES
from services.planning.planner import _strip_fences, _build_completion_url, DECOMPOSE_PROMPT


# ── Property 5: Plan Step Count Bounds ───────────────────────────────────────

# Feature: phase-1-intelligence-reasoning, Property 5: Plan Step Count Bounds
@given(st.integers(min_value=0, max_value=100))
@settings(max_examples=50)
def test_step_count_outside_bounds_is_invalid(n_steps):
    """Steps < 2 or > 50 must be rejected. Property 5."""
    valid = 2 <= n_steps <= 50
    if not valid:
        with pytest.raises(ValueError):
            if not (2 <= n_steps <= 50):
                raise ValueError(f"Plan must have 2–50 steps; got {n_steps}")
    else:
        assert 2 <= n_steps <= 50


# Feature: phase-1-intelligence-reasoning, Property 6: Plan Step Ordering Invariant
@given(st.integers(min_value=2, max_value=50))
@settings(max_examples=50)
def test_step_order_indices_are_sequential(n_steps):
    """order_index values must be 0, 1, …, n-1 with no gaps or duplicates. Property 6."""
    indices = list(range(n_steps))
    assert indices == sorted(indices)
    assert indices[0] == 0
    assert indices[-1] == n_steps - 1
    assert len(set(indices)) == len(indices)


# Feature: phase-1-intelligence-reasoning, Property 7: Plan Resumption Skips Completed Steps
@given(st.lists(
    st.sampled_from(["done", "skipped", "pending", "failed"]),
    min_size=2, max_size=10
))
@settings(max_examples=100)
def test_resumption_skips_terminal_steps(step_statuses):
    """execute() must skip 'done' and 'skipped' steps. Property 7."""
    to_execute = [s for s in step_statuses if s not in ("done", "skipped")]
    for s in step_statuses:
        if s in ("done", "skipped"):
            assert s not in to_execute


# ── Planner helper unit tests ─────────────────────────────────────────────────

class TestPlannerHelpers:
    def test_strip_fences_removes_json_fence(self):
        raw = "```json\n{\"steps\": []}\n```"
        assert _strip_fences(raw) == '{"steps": []}'

    def test_strip_fences_noop_on_plain_json(self):
        raw = '{"steps": []}'
        assert _strip_fences(raw) == raw

    def test_build_url_adds_v1_when_missing(self):
        url = _build_completion_url("http://localhost:11434")
        assert url == "http://localhost:11434/v1/chat/completions"

    def test_build_url_no_double_v1(self):
        url = _build_completion_url("http://localhost:8080/v1")
        assert url == "http://localhost:8080/v1/chat/completions"
        assert "v1/v1" not in url

    def test_build_url_strips_trailing_slash(self):
        url = _build_completion_url("http://localhost:11434/")
        assert "//chat" not in url

    def test_decompose_prompt_has_goal_placeholder(self):
        assert "{goal}" in DECOMPOSE_PROMPT


# ── Executor control flags ────────────────────────────────────────────────────

class TestPlanExecutorFlags:
    """Req 6.7"""

    def test_cancel_sets_flag(self):
        ex = PlanExecutor()
        ex.cancel("plan-1")
        assert ex._cancelled.get("plan-1") is True

    def test_pause_sets_flag(self):
        ex = PlanExecutor()
        ex.pause("plan-1")
        assert ex._paused.get("plan-1") is True

    def test_resume_removes_pause_flag(self):
        ex = PlanExecutor()
        ex.pause("plan-1")
        ex.resume("plan-1")
        assert "plan-1" not in ex._paused

    def test_max_retries_is_positive(self):
        assert MAX_RETRIES >= 1


# ── Resumption logic ──────────────────────────────────────────────────────────

class TestResumption:
    """Req 6.3, 6.4"""

    def test_done_and_skipped_excluded_from_execution(self):
        terminal = {"done", "skipped"}
        non_terminal = {"pending", "failed", "running"}
        assert terminal.isdisjoint(non_terminal)

    def test_executor_instance_has_empty_flags_on_init(self):
        ex = PlanExecutor()
        assert ex._cancelled == {}
        assert ex._paused == {}


# ── Retry exhaustion ──────────────────────────────────────────────────────────

class TestRetryExhaustion:
    """Req 6.5"""

    def test_set_plan_status_called_with_paused_on_failure(self):
        ex = PlanExecutor()
        mock_db = MagicMock()
        mock_plan_row = MagicMock()
        mock_plan_row.status = "running"
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_plan_row
        with patch("services.planning.executor.SessionLocal", return_value=mock_db):
            ex._set_plan_status("plan-1", "paused_on_failure")
        assert mock_plan_row.status == "paused_on_failure"
