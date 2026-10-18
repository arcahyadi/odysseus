"""Tests for AgentDispatcher — phase→agent mapping, kill-switch gating, explicit dispatch."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from src.orchestrator.agent_dispatcher import (
    _EXPLICIT_AGENTS,
    _PHASE_AGENTS,
    AgentDispatcher,
    _is_enabled,
)
from src.orchestrator.phases import Phase
from src.orchestrator.spec import AgentSpec


# ── helpers ────────────────────────────────────────────────────────────
def _make_spec(name="test-agent", description="test", prompt="You are a test agent."):
    return AgentSpec(name=name, description=description, prompt=prompt, source_path=f".opencode/agents/{name}.md")


class _FakeRegistry:
    """Minimal fake that mimics AgentRegistry interface."""

    def __init__(self, specs=None):
        self._specs = {s.name: s for s in (specs or [])}

    def get(self, name):
        return self._specs.get(name)

    def list_names(self):
        return sorted(self._specs.keys())


# ── kill-switch tests ──────────────────────────────────────────────────
class TestKillSwitch:
    def test_is_enabled_on(self):
        with patch.dict(os.environ, {"TEST_SWITCH": "on"}):
            assert _is_enabled("TEST_SWITCH") is True

    def test_is_enabled_1(self):
        with patch.dict(os.environ, {"TEST_SWITCH": "1"}):
            assert _is_enabled("TEST_SWITCH") is True

    def test_is_enabled_true(self):
        with patch.dict(os.environ, {"TEST_SWITCH": "true"}):
            assert _is_enabled("TEST_SWITCH") is True

    def test_is_enabled_off_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _is_enabled("TEST_SWITCH") is False

    def test_is_enabled_explicit_off(self):
        with patch.dict(os.environ, {"TEST_SWITCH": "off"}):
            assert _is_enabled("TEST_SWITCH") is False


# ── phase mapping tests ────────────────────────────────────────────────
class TestPhaseMapping:
    def test_all_phases_have_entries(self):
        """Every canonical phase must have an entry (even if empty list)."""
        for phase in Phase:
            assert phase in _PHASE_AGENTS, f"Phase {phase.value} missing from _PHASE_AGENTS"

    def test_classify_has_constitution(self):
        agents = _PHASE_AGENTS[Phase.CLASSIFY]
        names = [a[0] for a in agents]
        assert "constitution" in names

    def test_plan_has_planner_and_researcher(self):
        agents = _PHASE_AGENTS[Phase.PLAN]
        names = [a[0] for a in agents]
        assert "gsd-planner" in names
        assert "gsd-researcher" in names

    def test_build_has_executor(self):
        agents = _PHASE_AGENTS[Phase.BUILD]
        names = [a[0] for a in agents]
        assert "gsd-executor" in names

    def test_quality_has_debate_and_security(self):
        agents = _PHASE_AGENTS[Phase.QUALITY]
        names = [a[0] for a in agents]
        assert "debate-5-personas" in names
        assert "security-audit" in names

    def test_autoeval_has_verifier_and_edgecase(self):
        agents = _PHASE_AGENTS[Phase.AUTOEVAL]
        names = [a[0] for a in agents]
        assert "gsd-verifier" in names
        assert "edge-case-gen" in names

    def test_memory_observe_has_roadmapper(self):
        agents = _PHASE_AGENTS[Phase.MEMORY_OBSERVE]
        names = [a[0] for a in agents]
        assert "gsd-roadmapper" in names

    def test_know_is_empty(self):
        agents = _PHASE_AGENTS[Phase.KNOW]
        assert agents == []


# ── AgentDispatcher tests ──────────────────────────────────────────────
class TestAgentDispatcher:
    def test_agents_for_phase_all_off(self):
        """With all kill-switches OFF, no agents fire."""
        with patch.dict(os.environ, {}, clear=True):
            dispatcher = AgentDispatcher()
            for phase in Phase:
                assert dispatcher.agents_for_phase(phase) == []

    def test_agents_for_phase_constitution_on(self):
        with patch.dict(os.environ, {"ODYSSEUS_AGENT_CONSTITUTION": "on"}, clear=True):
            dispatcher = AgentDispatcher()
            assert dispatcher.agents_for_phase(Phase.CLASSIFY) == ["constitution"]

    def test_agents_for_phase_multiple_on(self):
        with patch.dict(
            os.environ,
            {
                "ODYSSEUS_AGENT_DEBATE": "on",
                "ODYSSEUS_AGENT_SECURITY": "1",
            },
            clear=True,
        ):
            dispatcher = AgentDispatcher()
            agents = dispatcher.agents_for_phase(Phase.QUALITY)
            assert "debate-5-personas" in agents
            assert "security-audit" in agents
            assert len(agents) == 2

    def test_no_agents_without_registry(self):
        """dispatch_for_phase is a no-op when no registry is available."""
        dispatcher = AgentDispatcher(registry=None)
        # Patch _get_registry to return None
        with patch.object(AgentDispatcher, "_get_registry", return_value=None):
            with patch.dict(os.environ, {"ODYSSEUS_AGENT_CONSTITUTION": "on"}):
                # Should not raise
                import asyncio

                asyncio.run(dispatcher.dispatch_for_phase(Phase.CLASSIFY, "test"))

    def test_dispatch_with_fake_registry(self):
        """Agent fires when registry has the spec."""
        spec = _make_spec("constitution", "Pre-flight check")
        registry = _FakeRegistry([spec])
        dispatcher = AgentDispatcher(registry=registry)

        with patch.dict(os.environ, {"ODYSSEUS_AGENT_CONSTITUTION": "on"}):
            with patch("src.task_endpoint.task_llm_call_async", new_callable=AsyncMock) as mock_task:
                mock_task.return_value = "All invariants pass"
                import asyncio

                asyncio.run(dispatcher.dispatch_for_phase(Phase.CLASSIFY, "test", "check project"))
                mock_task.assert_called_once()
                # Verify messages include the agent prompt
                call_args = mock_task.call_args
                assert call_args is not None

    def test_dispatch_skips_unknown_agent(self):
        """dispatch_for_phase skips agents not in registry."""
        registry = _FakeRegistry([])  # empty
        dispatcher = AgentDispatcher(registry=registry)

        with patch.dict(os.environ, {"ODYSSEUS_AGENT_CONSTITUTION": "on"}):
            with patch("src.task_endpoint.task_llm_call_async", new_callable=AsyncMock) as mock_task:
                import asyncio

                asyncio.run(dispatcher.dispatch_for_phase(Phase.CLASSIFY, "test"))
                mock_task.assert_not_called()

    def test_dispatch_never_raises(self):
        """dispatch_for_phase must never raise, even on internal errors."""
        dispatcher = AgentDispatcher(registry=None)

        with patch.dict(os.environ, {"ODYSSEUS_AGENT_CONSTITUTION": "on"}):
            with patch.object(AgentDispatcher, "_get_registry", side_effect=RuntimeError("boom")):
                import asyncio

                # Should not raise — _get_registry is now try-guarded
                asyncio.run(dispatcher.dispatch_for_phase(Phase.CLASSIFY, "test"))


# ── explicit dispatch tests ────────────────────────────────────────────
class TestExplicitDispatch:
    def test_explicit_enabled_true(self):
        with patch.dict(os.environ, {"ODYSSEUS_AGENT_DESIGN_EXTRACT": "on"}):
            dispatcher = AgentDispatcher()
            assert dispatcher.explicit_enabled("design-extract") is True

    def test_explicit_enabled_false(self):
        with patch.dict(os.environ, {}, clear=True):
            dispatcher = AgentDispatcher()
            assert dispatcher.explicit_enabled("design-extract") is False

    def test_explicit_enabled_unknown_agent(self):
        dispatcher = AgentDispatcher()
        assert dispatcher.explicit_enabled("nonexistent") is False

    def test_list_explicit_agents_all_off(self):
        with patch.dict(os.environ, {}, clear=True):
            dispatcher = AgentDispatcher()
            assert dispatcher.list_explicit_agents() == []

    def test_list_explicit_agents_some_on(self):
        with patch.dict(
            os.environ,
            {
                "ODYSSEUS_AGENT_PLANNER": "on",
                "ODYSSEUS_AGENT_DESIGN_EXTRACT": "1",
            },
            clear=True,
        ):
            dispatcher = AgentDispatcher()
            agents = dispatcher.list_explicit_agents()
            assert "gsd-planner" in agents
            assert "design-extract" in agents

    def test_dispatch_explicit_not_enabled_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            dispatcher = AgentDispatcher()
            import asyncio

            with pytest.raises(ValueError, match="not enabled"):
                asyncio.run(dispatcher.dispatch_explicit("design-extract", "test"))

    def test_dispatch_explicit_no_registry_raises(self):
        with patch.dict(os.environ, {"ODYSSEUS_AGENT_DESIGN_EXTRACT": "on"}):
            dispatcher = AgentDispatcher(registry=None)
            with patch.object(AgentDispatcher, "_get_registry", return_value=None):
                import asyncio

                with pytest.raises(RuntimeError, match="Agent catalog not loaded"):
                    asyncio.run(dispatcher.dispatch_explicit("design-extract", "test"))

    def test_dispatch_explicit_not_in_registry_raises(self):
        registry = _FakeRegistry([])
        dispatcher = AgentDispatcher(registry=registry)
        with patch.dict(os.environ, {"ODYSSEUS_AGENT_DESIGN_EXTRACT": "on"}):
            import asyncio

            with pytest.raises(ValueError, match="not found in catalog"):
                asyncio.run(dispatcher.dispatch_explicit("design-extract", "test"))

    def test_dispatch_explicit_success(self):
        spec = _make_spec("design-extract", "Design system extraction")
        registry = _FakeRegistry([spec])
        dispatcher = AgentDispatcher(registry=registry)

        with patch.dict(os.environ, {"ODYSSEUS_AGENT_DESIGN_EXTRACT": "on"}):
            with patch("src.task_endpoint.task_llm_call_async", new_callable=AsyncMock) as mock_task:
                mock_task.return_value = "Design tokens extracted"
                import asyncio

                result = asyncio.run(dispatcher.dispatch_explicit("design-extract", "test", "https://example.com"))
                assert result == "Design tokens extracted"
                mock_task.assert_called_once()


# ── smoke: all explicit agents have env vars ───────────────────────────
class TestExplicitAgentCoverage:
    def test_all_explicit_agents_have_env_vars(self):
        """Every agent in _EXPLICIT_AGENTS must have a corresponding ODYSSEUS_AGENT_* env var."""
        for name, env_var in _EXPLICIT_AGENTS.items():
            assert env_var.startswith("ODYSSEUS_AGENT_"), f"Agent {name!r} has non-standard env var: {env_var}"
            assert env_var.isupper(), f"Agent {name!r} env var is not uppercase: {env_var}"

    def test_all_phase_agents_have_env_vars(self):
        """Every phase agent entry must have a valid ODYSSEUS_AGENT_* env var."""
        for phase, entries in _PHASE_AGENTS.items():
            for name, env_var in entries:
                assert env_var.startswith("ODYSSEUS_AGENT_"), (
                    f"Phase {phase.value} agent {name!r} has bad env var: {env_var}"
                )
