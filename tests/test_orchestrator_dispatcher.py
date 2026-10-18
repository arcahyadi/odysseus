"""Tests for src/orchestrator/dispatcher.py::resolve_model."""

from src.orchestrator.dispatcher import resolve_model
from src.orchestrator.spec import AgentSpec


class _FakeRouter:
    def __init__(self, answer="openai/deepseek-v4-flash"):
        self.answer = answer
        self.calls = []

    def route(self, intent_category, stage=None):
        self.calls.append((intent_category, stage))
        return self.answer


def test_explicit_spec_model_wins_and_router_not_called():
    spec = AgentSpec(name="x", model="openai/kimi-k2.7-code")
    router = _FakeRouter()
    result = resolve_model(spec, router=router, stage="execution")
    assert result == "openai/kimi-k2.7-code"
    assert router.calls == []  # explicit model short-circuits the router


def test_falls_back_to_router_when_no_model():
    spec = AgentSpec(name="x", model=None)
    router = _FakeRouter(answer="openai/glm-5.2")
    result = resolve_model(spec, router=router, stage="planning")
    assert result == "openai/glm-5.2"
    assert router.calls == [("utility", "planning")]


def test_router_stage_defaults_to_none():
    spec = AgentSpec(name="x", model=None)
    router = _FakeRouter()
    resolve_model(spec, router=router)
    assert router.calls == [("utility", None)]


def test_no_router_and_no_model_returns_none():
    spec = AgentSpec(name="x", model=None)
    assert resolve_model(spec, router=None) is None
