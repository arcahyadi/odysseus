"""Characterization tests for the live loop's two phase-inference systems.

These pin the CURRENT observable behavior of PhaseTracker and CanonicalLoop
(and, in Task 2, resolve_current_phase). They are behavior snapshots: if one
fails after a change, the change altered runtime behavior — suspect the change,
not the test.
"""

from __future__ import annotations

from src.orchestrator.loop import CanonicalLoop
from src.orchestrator.phase_resolver import resolve_current_phase
from src.orchestrator.phase_tracker import PhaseTracker, tracker_enabled
from src.orchestrator.phases import (
    CANONICAL_SEQUENCE,
    Phase,
    forced_tools,
    phase_lock_name,
)


class _FakeRegistry:
    """Records set_phase calls so tests can assert on them without the singleton."""

    def __init__(self):
        self.calls = []

    def set_phase(self, session_id, phase):
        self.calls.append((session_id, phase))


# --- PhaseTracker -----------------------------------------------------------


def test_infer_phase_defaults_to_build():
    assert PhaseTracker.infer_phase(1, plan_mode=False) == "BUILD"
    assert PhaseTracker.infer_phase(99, plan_mode=False) == "BUILD"


def test_infer_phase_plan_mode_returns_plan():
    assert PhaseTracker.infer_phase(1, plan_mode=True) == "PLAN"


def test_tracker_enabled_defaults_on(monkeypatch):
    """Palier 0 (FND-4 option C): PHASE_TRACKER is ON by default again.

    The OFF polarity is still covered right below: a kill-switch nobody
    can turn off is not a kill-switch.
    """
    monkeypatch.delenv("ODYSSEUS_PHASE_TRACKER", raising=False)
    assert tracker_enabled() is True


def test_tracker_can_be_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "off")
    assert tracker_enabled() is False


def test_tracker_enabled_truthy_env(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    assert tracker_enabled() is True


def test_on_round_start_sets_phase_when_enabled():
    reg = _FakeRegistry()
    tracker = PhaseTracker("sess", registry=reg, enabled=True)
    tracker.on_round_start(1, plan_mode=True)
    assert reg.calls == [("sess", "PLAN")]


def test_on_round_start_noop_when_disabled():
    reg = _FakeRegistry()
    tracker = PhaseTracker("sess", registry=reg, enabled=False)
    tracker.on_round_start(1, plan_mode=True)
    assert reg.calls == []


# --- CanonicalLoop ----------------------------------------------------------


def test_canonical_loop_starts_at_classify():
    loop = CanonicalLoop("sess")
    assert loop.current == Phase.CLASSIFY


def test_canonical_loop_advances_to_memory_observe():
    loop = CanonicalLoop("sess")
    for _ in range(len(CANONICAL_SEQUENCE) - 1):
        assert loop.advance() is True
    assert loop.current == Phase.MEMORY_OBSERVE


def test_canonical_loop_advance_past_end_is_bounded():
    loop = CanonicalLoop("sess")
    for _ in range(len(CANONICAL_SEQUENCE) - 1):
        loop.advance()
    assert loop.advance() is False
    assert loop.current == Phase.MEMORY_OBSERVE


def test_canonical_loop_goto_applies_to_registry():
    reg = _FakeRegistry()
    loop = CanonicalLoop("sess", registry=reg)
    loop.goto(Phase.QUALITY)
    assert loop.current == Phase.QUALITY
    assert reg.calls == [("sess", "QUALITY")]


def test_canonical_loop_apply_without_registry_is_noop():
    loop = CanonicalLoop("sess")
    loop.apply()  # must not raise


# --- phases.py data helpers -------------------------------------------------


def test_seven_canonical_phases_in_order():
    assert [p.name for p in CANONICAL_SEQUENCE] == [
        "CLASSIFY",
        "KNOW",
        "PLAN",
        "BUILD",
        "QUALITY",
        "AUTOEVAL",
        "MEMORY_OBSERVE",
    ]


def test_each_phase_maps_to_a_phaselock_name():
    for p in CANONICAL_SEQUENCE:
        name = phase_lock_name(p)
        assert isinstance(name, str) and name
        assert name == name.upper()


def test_classify_maps_to_readonly_enforcement():
    assert phase_lock_name(Phase.CLASSIFY) == "CLASSIFY"


def test_build_maps_to_build():
    assert phase_lock_name(Phase.BUILD) == "BUILD"


def test_forced_tools_are_lists():
    for p in CANONICAL_SEQUENCE:
        assert isinstance(forced_tools(p), list)


def test_classify_forces_risk_classifier():
    assert "risk_classifier" in forced_tools(Phase.CLASSIFY)


# --- resolve_current_phase (the extracted seam) -----------------------------


class _FakeTracker:
    """Minimal PhaseTracker stand-in returning a fixed infer_phase result."""

    def __init__(self, phase_name):
        self._phase_name = phase_name

    def infer_phase(self, round_num, intent=None, plan_mode=False):
        return self._phase_name


def test_resolve_prefers_canonical_when_active():
    loop = CanonicalLoop("sess")
    loop.goto(Phase.PLAN)
    result = resolve_current_phase(True, loop, None, round_num=1)
    assert result == Phase.PLAN


def test_resolve_uses_tracker_plan_mode():
    tracker = _FakeTracker("PLAN")
    result = resolve_current_phase(False, None, tracker, round_num=1, plan_mode=True)
    assert result == Phase.PLAN


def test_resolve_uses_tracker_build_default():
    tracker = _FakeTracker("BUILD")
    result = resolve_current_phase(False, None, tracker, round_num=1, plan_mode=False)
    assert result == Phase.BUILD


def test_resolve_returns_none_when_no_system():
    result = resolve_current_phase(False, None, None, round_num=1)
    assert result is None


def test_resolve_coerces_out_of_enum_to_none():
    tracker = _FakeTracker("WAT")  # not a valid Phase value
    result = resolve_current_phase(False, None, tracker, round_num=1)
    assert result is None
