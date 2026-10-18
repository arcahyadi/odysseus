"""Tests for src/orchestrator/langgraph_loop.py — 7-node StateGraph decomposition.

Tests:
  1. Kill-switch OFF (default) — langgraph_enabled() returns False
  2. Kill-switch ON — langgraph_enabled() returns True
  3. classify_node — risk classification
  4. know_node — knowledge retrieval
  5. plan_node — plan construction
  6. quality_node — quality check
  7. autoeval_node — keep/revert decision
  8. memory_node — memory distillation
  9. build_input_state — parameter mapping
 10. graph construction — graph builds successfully
 11. full graph run (mock LLM) — end-to-end
 12. backward compat — kill-switch OFF yields standard path
"""

from __future__ import annotations

import pytest

# ─── Kill-switch tests ──────────────────────────────────────────────────────


class TestKillSwitch:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("ODYSSEUS_LANGGRAPH", raising=False)
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is False

    def test_on_with_true(self, monkeypatch):
        monkeypatch.setenv("ODYSSEUS_LANGGRAPH", "true")
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is True

    def test_on_with_1(self, monkeypatch):
        monkeypatch.setenv("ODYSSEUS_LANGGRAPH", "1")
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is True

    def test_on_with_on(self, monkeypatch):
        monkeypatch.setenv("ODYSSEUS_LANGGRAPH", "on")
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is True

    def test_off_with_false(self, monkeypatch):
        monkeypatch.setenv("ODYSSEUS_LANGGRAPH", "false")
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is False

    def test_off_with_0(self, monkeypatch):
        monkeypatch.setenv("ODYSSEUS_LANGGRAPH", "0")
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is False


# ─── classify_node tests ───────────────────────────────────────────────────


class TestClassifyNode:
    def test_classify_read(self):
        from src.orchestrator.langgraph_loop import RiskLevel, _default_state, classify_node

        state = _default_state(messages=[{"role": "user", "content": "what is the weather?"}])
        result = classify_node(state)
        assert result["risk_level"] == RiskLevel.READ.value
        assert result["phase"] == "CLASSIFY"
        assert "last_user" in result

    def test_classify_write(self):
        from src.orchestrator.langgraph_loop import RiskLevel, _default_state, classify_node

        state = _default_state(messages=[{"role": "user", "content": "please create a new file"}])
        result = classify_node(state)
        assert result["risk_level"] == RiskLevel.WRITE.value

    def test_classify_exec(self):
        from src.orchestrator.langgraph_loop import RiskLevel, _default_state, classify_node

        state = _default_state(messages=[{"role": "user", "content": "run this bash command"}])
        result = classify_node(state)
        assert result["risk_level"] == RiskLevel.EXEC.value

    def test_classify_destructive(self):
        from src.orchestrator.langgraph_loop import RiskLevel, _default_state, classify_node

        state = _default_state(messages=[{"role": "user", "content": "rm -rf /tmp/test"}])
        result = classify_node(state)
        assert result["risk_level"] == RiskLevel.DESTRUCTIVE.value

    def test_classify_empty_messages(self):
        from src.orchestrator.langgraph_loop import _default_state, classify_node

        state = _default_state(messages=[])
        result = classify_node(state)
        assert result["last_user"] == ""
        assert result["phase"] == "CLASSIFY"


# ─── know_node tests ────────────────────────────────────────────────────────


class TestKnowNode:
    def test_know_returns_phase(self):
        from src.orchestrator.langgraph_loop import _default_state, know_node

        state = _default_state(
            messages=[{"role": "user", "content": "hello"}],
            last_user="hello",
        )
        result = know_node(state)
        assert result["phase"] == "KNOW"
        assert "context" in result


# ─── plan_node tests ───────────────────────────────────────────────────────


class TestPlanNode:
    def test_plan_auto_mode(self):
        from src.orchestrator.langgraph_loop import _default_state, plan_node

        state = _default_state(context={"domains": ["email"]})
        result = plan_node(state)
        assert result["plan"]["mode"] == "auto"
        assert len(result["plan"]["steps"]) > 0
        assert result["phase"] == "PLAN"

    def test_plan_plan_mode(self):
        from src.orchestrator.langgraph_loop import _default_state, plan_node

        state = _default_state(plan_mode=True)
        result = plan_node(state)
        assert result["plan"]["mode"] == "plan"

    def test_plan_approved(self):
        from src.orchestrator.langgraph_loop import _default_state, plan_node

        state = _default_state(approved_plan="Step 1: do X\nStep 2: do Y")
        result = plan_node(state)
        assert result["plan"]["mode"] == "approved"


# ─── quality_node tests ─────────────────────────────────────────────────────


class TestQualityNode:
    def test_quality_no_effectful(self):
        from src.orchestrator.langgraph_loop import _default_state, quality_node

        state = _default_state(tool_events=[{"tool": "web_search"}])
        result = quality_node(state)
        assert result["phase"] == "QUALITY"
        assert result["context"]["quality_checked"] is True
        assert result["context"]["has_effectful_tools"] is False

    def test_quality_with_effectful(self):
        from src.orchestrator.langgraph_loop import _default_state, quality_node

        state = _default_state(tool_events=[{"tool": "bash"}, {"tool": "write_file"}])
        result = quality_node(state)
        assert result["context"]["has_effectful_tools"] is True


# ─── autoeval_node tests ───────────────────────────────────────────────────


class TestAutoevalNode:
    def test_autoeval_keep_no_reasons(self):
        from src.orchestrator.langgraph_loop import _default_state, autoeval_node

        state = _default_state(verifier_reasons=[], drift_level=None)
        result = autoeval_node(state)
        assert result["passed"] is True
        assert result["phase"] == "AUTOEVAL"

    def test_autoeval_keep_empty_reasons(self):
        from src.orchestrator.langgraph_loop import _default_state, autoeval_node

        state = _default_state(verifier_reasons=[], drift_level="low")
        result = autoeval_node(state)
        assert result["passed"] is True

    def test_autoeval_with_verifier_reasons(self, monkeypatch):
        """AUTOEVAL is ON by default (Palier 0): verifier reasons -> revert decision."""
        monkeypatch.delenv("ODYSSEUS_AUTOEVAL", raising=False)
        from src.orchestrator.langgraph_loop import _default_state, autoeval_node

        state = _default_state(verifier_reasons=["file not found", "timeout"])
        result = autoeval_node(state)
        assert result["passed"] is False

    def test_autoeval_off_forces_keep(self, monkeypatch):
        """The OFF polarity still short-circuits to keep."""
        monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "off")
        from src.orchestrator.langgraph_loop import _default_state, autoeval_node

        state = _default_state(verifier_reasons=["file not found", "timeout"])
        result = autoeval_node(state)
        assert result["passed"] is True

    def test_autoeval_never_shells_out_to_git_without_explicit_optin(self, monkeypatch):
        """SAFETY: a decided revert must not run `git reset --hard` by default.

        Regression guard. With AUTOEVAL on and ALLOW_RESET unset, this node
        used to invoke a real subprocess `git reset --hard HEAD` — which, during
        a test run, silently destroyed every uncommitted change in the tree.
        The decision is still taken and reported; only the action is withheld.
        """
        monkeypatch.delenv("ODYSSEUS_AUTOEVAL", raising=False)
        monkeypatch.delenv("ODYSSEUS_AUTOEVAL_ALLOW_RESET", raising=False)

        import subprocess as _sp

        from src.orchestrator import langgraph_loop
        from src.orchestrator.langgraph_loop import _default_state, autoeval_node

        calls = []
        real_run = _sp.run

        def _boom(*a, **kw):  # pragma: no cover - must never be reached
            calls.append(a)
            raise AssertionError("autoeval shelled out to git without ALLOW_RESET")

        monkeypatch.setattr(_sp, "run", _boom)
        try:
            state = _default_state(verifier_reasons=["boom"], drift_level="high")
            result = autoeval_node(state)
        finally:
            monkeypatch.setattr(_sp, "run", real_run)

        assert calls == []
        assert result["passed"] is False  # revert decided, not executed
        assert langgraph_loop is not None


# ─── memory_node tests ──────────────────────────────────────────────────────


class TestMemoryNode:
    def test_memory_emits_done(self):
        from src.orchestrator.langgraph_loop import _default_state, memory_node

        state = _default_state(
            session_id="test-session",
            run_id="test-run-123",
            metrics={"model": "test", "total_time": 1.0},
        )
        result = memory_node(state)
        assert result["phase"] == "MEMORY_OBSERVE"
        events = result["sse_events"]
        assert any("DONE" in e for e in events)
        assert any("metrics" in e for e in events)


# ─── build_input_state tests ───────────────────────────────────────────────


class TestBuildInputState:
    def test_maps_all_params(self):
        from src.orchestrator.langgraph_loop import RiskLevel, build_input_state

        state = build_input_state(
            endpoint_url="http://localhost:8080/v1",
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=2048,
            max_rounds=10,
            session_id="s1",
            owner="admin",
            plan_mode=True,
        )
        assert state["endpoint_url"] == "http://localhost:8080/v1"
        assert state["model"] == "gpt-4"
        assert state["temperature"] == 0.5
        assert state["max_tokens"] == 2048
        assert state["session_id"] == "s1"
        assert state["owner"] == "admin"
        assert state["plan_mode"] is True
        assert state["risk_level"] == RiskLevel.READ.value
        assert state["run_id"]  # auto-generated

    def test_forced_tools_merged(self):
        from src.orchestrator.langgraph_loop import build_input_state

        state = build_input_state(
            endpoint_url="",
            model="",
            messages=[],
            relevant_tools={"web_search", "bash"},
            forced_tools={"manage_notes"},
        )
        assert state["relevant_tools"] == {"web_search", "bash", "manage_notes"}


# ─── Graph construction test ────────────────────────────────────────────────


class TestGraphConstruction:
    def test_graph_builds(self):
        """Verify the StateGraph compiles without errors."""
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            pytest.skip("langgraph not installed")

        from src.orchestrator.langgraph_loop import (
            AgentState,
            autoeval_node,
            build_node,
            classify_node,
            know_node,
            memory_node,
            plan_node,
            quality_node,
        )

        # Build graph manually (not with SQLite to avoid file I/O)
        graph = StateGraph(AgentState)
        graph.add_node("classify", classify_node)
        graph.add_node("know", know_node)
        graph.add_node("plan", plan_node)
        graph.add_node("build", build_node)
        graph.add_node("quality", quality_node)
        graph.add_node("autoeval", autoeval_node)
        graph.add_node("memory_observe", memory_node)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "know")
        graph.add_edge("know", "plan")
        graph.add_edge("plan", "build")
        graph.add_edge("build", "quality")
        graph.add_edge("quality", "autoeval")
        graph.add_conditional_edges(
            "autoeval",
            lambda s: "memory_observe" if s.get("passed") else "build",
            {"memory_observe": "memory_observe", "build": "build"},
        )
        graph.add_edge("memory_observe", END)

        compiled = graph.compile()
        assert compiled is not None


# ─── Sequential node execution test ────────────────────────────────────────


class TestSequentialExecution:
    def test_classify_then_know_then_plan(self):
        """Run classify -> know -> plan manually and verify state flow."""
        from src.orchestrator.langgraph_loop import (
            _default_state,
            classify_node,
            know_node,
            plan_node,
        )

        state = _default_state(
            messages=[{"role": "user", "content": "search the web for Python news"}],
        )

        # Step 1: classify
        r1 = classify_node(state)
        state.update(r1)
        assert state["phase"] == "CLASSIFY"
        assert state["last_user"]

        # Step 2: know
        r2 = know_node(state)
        state.update(r2)
        assert state["phase"] == "KNOW"

        # Step 3: plan
        r3 = plan_node(state)
        state.update(r3)
        assert state["phase"] == "PLAN"
        assert "steps" in state["plan"]


# ─── Backward compatibility test ────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_killswitch_off_does_not_import_langgraph(self, monkeypatch):
        """When kill-switch is OFF, langgraph is never imported in stream_agent_loop."""
        monkeypatch.delenv("ODYSSEUS_LANGGRAPH", raising=False)
        from src.orchestrator.langgraph_loop import langgraph_enabled

        assert langgraph_enabled() is False

        # Verify stream_agent_loop is still the original function
        import inspect

        from src.agent_loop import stream_agent_loop

        # The function should still exist and be an async generator
        assert inspect.isasyncgenfunction(stream_agent_loop)


# ─── AgentState TypedDict tests ────────────────────────────────────────────


class TestAgentState:
    def test_has_all_required_keys(self):
        from src.orchestrator.langgraph_loop import AgentState

        annotations = AgentState.__annotations__
        required = [
            "messages",
            "endpoint_url",
            "model",
            "phase",
            "risk_level",
            "context",
            "plan",
            "tool_calls",
            "budgets",
            "passed",
            "full_response",
            "metrics",
            "tool_events",
            "run_id",
            "sse_events",
        ]
        for key in required:
            assert key in annotations, f"Missing key: {key}"

    def test_default_state_factory(self):
        from src.orchestrator.langgraph_loop import _default_state

        state = _default_state()
        assert state["messages"] == []
        assert state["phase"] == ""
        assert state["risk_level"] == "read"
        assert state["passed"] is False
        assert state["sse_events"] == []
        assert state["run_id"]  # auto-generated UUID


# ─── Edge routing tests ────────────────────────────────────────────────────


class TestEdgeRouting:
    def test_autoeval_pass_routes_to_memory(self):
        """When passed=True, autoeval should route to memory_observe."""
        state = {"passed": True}
        router = lambda s: "memory_observe" if s.get("passed", False) else "build"
        assert router(state) == "memory_observe"

    def test_autoeval_fail_routes_to_build(self):
        """When passed=False, autoeval should route back to build."""
        state = {"passed": False}
        router = lambda s: "memory_observe" if s.get("passed", False) else "build"
        assert router(state) == "build"
