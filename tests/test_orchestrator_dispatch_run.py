"""Tests for src/orchestrator/dispatcher.py::dispatch (orchestrated run)."""

from src.orchestrator.dispatcher import DispatchResult, dispatch
from src.orchestrator.spec import AgentSpec


class _FakeRegistry:
    def __init__(self):
        self.phase_calls = []

    def set_phase(self, session_id, phase):
        self.phase_calls.append((session_id, phase))


class _FakeRouter:
    def route(self, intent_category, stage=None):
        return "openai/deepseek-v4-flash"


def test_dispatch_walks_all_seven_phases_in_order():
    reg = _FakeRegistry()
    spec = AgentSpec(name="gsd-planner")
    calls = []

    def runner(phase, spec, objective, model):
        calls.append(phase.name)
        return f"did {phase.name}"

    result = dispatch(
        spec,
        "build feature X",
        session_id="run1",
        registry=reg,
        router=_FakeRouter(),
        runner=runner,
    )
    assert isinstance(result, DispatchResult)
    assert result.phases_run == [
        "CLASSIFY",
        "KNOW",
        "PLAN",
        "BUILD",
        "QUALITY",
        "AUTOEVAL",
        "MEMORY_OBSERVE",
    ]
    assert calls == result.phases_run
    assert result.completed is True


def test_dispatch_applies_phase_to_registry_each_step():
    reg = _FakeRegistry()
    spec = AgentSpec(name="a")
    dispatch(spec, "obj", session_id="run2", registry=reg, router=_FakeRouter(), runner=lambda **kw: None)
    assert [p for _, p in reg.phase_calls] == [
        "CLASSIFY",
        "KNOW",
        "PLAN",
        "BUILD",
        "QUALITY",
        "AUTOEVAL",
        "MEMORY_OBSERVE",
    ]
    assert all(sid == "run2" for sid, _ in reg.phase_calls)


def test_dispatch_resolves_model_via_router():
    spec = AgentSpec(name="a", model=None)
    result = dispatch(
        spec, "obj", session_id="r", registry=_FakeRegistry(), router=_FakeRouter(), runner=lambda **kw: None
    )
    assert result.model == "openai/deepseek-v4-flash"


def test_dispatch_uses_explicit_spec_model():
    spec = AgentSpec(name="a", model="openai/kimi-k2.7-code")
    result = dispatch(
        spec, "obj", session_id="r", registry=_FakeRegistry(), router=_FakeRouter(), runner=lambda **kw: None
    )
    assert result.model == "openai/kimi-k2.7-code"


def test_dispatch_collects_runner_outputs_per_phase():
    spec = AgentSpec(name="a")
    result = dispatch(
        spec,
        "obj",
        session_id="r",
        registry=_FakeRegistry(),
        router=_FakeRouter(),
        runner=lambda phase, **kw: f"out-{phase.name}",
    )
    assert result.outputs["CLASSIFY"] == "out-CLASSIFY"
    assert result.outputs["MEMORY_OBSERVE"] == "out-MEMORY_OBSERVE"


def test_dispatch_without_runner_still_walks_phases():
    reg = _FakeRegistry()
    spec = AgentSpec(name="a")
    result = dispatch(spec, "obj", session_id="r", registry=reg, router=_FakeRouter())
    assert len(result.phases_run) == 7
    assert result.outputs == {}


def test_runner_receives_resolved_model_and_objective():
    spec = AgentSpec(name="a", model="openai/glm-5.2")
    seen = {}

    def runner(phase, spec, objective, model):
        seen["model"] = model
        seen["objective"] = objective

    dispatch(spec, "ship it", session_id="r", registry=_FakeRegistry(), router=_FakeRouter(), runner=runner)
    assert seen["model"] == "openai/glm-5.2"
    assert seen["objective"] == "ship it"
