"""M3.4 governance ancestry — kill-switched bridge for the live loop.

The native GovernanceManager can build a mission>goal>project>task ancestry
path, but the live agent loop never called it, so ancestry stayed a
route-only feature. These tests pin the bridge that lets the loop record a
run's ancestry at MEMORY_OBSERVE — but only when it runs inside an
orchestrated goal (a project_id is present) AND the kill-switch is ON.
Default OFF means live behaviour is unchanged.
"""

from src.orchestrator import ancestry_tracker


class _FakeManager:
    """Records calls to create_task_with_ancestry."""

    def __init__(self, result=None, raises=False):
        self.calls = []
        self._result = result or {"ok": True, "task_id": "t1", "ancestry_path": "m > g > p > task"}
        self._raises = raises

    def create_task_with_ancestry(self, *, project_id, task_name, description, agent_id):
        self.calls.append(
            {"project_id": project_id, "task_name": task_name, "description": description, "agent_id": agent_id}
        )
        if self._raises:
            raise RuntimeError("db down")
        return self._result


def test_ancestry_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_GOVERNANCE_ANCESTRY", raising=False)
    assert ancestry_tracker.ancestry_enabled() is False


def test_ancestry_enabled_when_flag_truthy(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_GOVERNANCE_ANCESTRY", "on")
    assert ancestry_tracker.ancestry_enabled() is True


def test_noop_when_disabled_even_with_project(monkeypatch):
    mgr = _FakeManager()
    out = ancestry_tracker.record_run_ancestry(
        project_id="proj-1",
        task_name="run",
        description="d",
        agent_id="a",
        enabled=False,
        manager=mgr,
    )
    assert out is None
    assert mgr.calls == []


def test_noop_when_no_project_even_if_enabled():
    mgr = _FakeManager()
    out = ancestry_tracker.record_run_ancestry(
        project_id=None,
        task_name="run",
        description="d",
        agent_id="a",
        enabled=True,
        manager=mgr,
    )
    assert out is None
    assert mgr.calls == []


def test_records_ancestry_when_enabled_and_project_present():
    mgr = _FakeManager()
    out = ancestry_tracker.record_run_ancestry(
        project_id="proj-1",
        task_name="turn-abc",
        description="last user msg",
        agent_id="agent-x",
        enabled=True,
        manager=mgr,
    )
    assert out == {"ok": True, "task_id": "t1", "ancestry_path": "m > g > p > task"}
    assert mgr.calls == [
        {
            "project_id": "proj-1",
            "task_name": "turn-abc",
            "description": "last user msg",
            "agent_id": "agent-x",
        }
    ]


def test_manager_exception_is_isolated():
    mgr = _FakeManager(raises=True)
    out = ancestry_tracker.record_run_ancestry(
        project_id="proj-1",
        task_name="run",
        description="d",
        agent_id="a",
        enabled=True,
        manager=mgr,
    )
    assert out is None
    assert len(mgr.calls) == 1  # attempted, then swallowed
