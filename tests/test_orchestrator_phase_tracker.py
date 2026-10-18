from src.orchestrator.phase_tracker import PhaseTracker, tracker_enabled


class _FakeRegistry:
    """Records set_phase calls without touching the real singleton."""

    def __init__(self):
        self.calls = []

    def set_phase(self, session_id, phase):
        self.calls.append((session_id, phase))


def test_tracker_enabled_by_default(monkeypatch):
    """Palier 0 (FND-4 option C): PHASE_TRACKER is ON by default again.

    The OFF polarity is still covered right below: a kill-switch nobody
    can turn off is not a kill-switch.
    """
    monkeypatch.delenv("ODYSSEUS_PHASE_TRACKER", raising=False)
    assert tracker_enabled() is True


def test_tracker_can_be_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "off")
    assert tracker_enabled() is False


def test_tracker_enabled_when_env_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    assert tracker_enabled() is True


def test_tracker_enabled_accepts_truthy_values(monkeypatch):
    for val in ("1", "true", "yes", "ON"):
        monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", val)
        assert tracker_enabled() is True


def test_infer_phase_normal_is_build():
    assert PhaseTracker.infer_phase(round_num=1) == "BUILD"
    assert PhaseTracker.infer_phase(round_num=5) == "BUILD"


def test_infer_phase_plan_mode_is_plan():
    assert PhaseTracker.infer_phase(round_num=1, plan_mode=True) == "PLAN"


def test_on_round_start_returns_inferred_phase():
    reg = _FakeRegistry()
    tracker = PhaseTracker("sess-1", registry=reg, enabled=True)
    assert tracker.on_round_start(1) == "BUILD"


def test_disabled_tracker_never_sets_phase():
    reg = _FakeRegistry()
    tracker = PhaseTracker("sess-1", registry=reg, enabled=False)
    tracker.on_round_start(1)
    assert reg.calls == []


def test_enabled_tracker_sets_phase():
    reg = _FakeRegistry()
    tracker = PhaseTracker("sess-1", registry=reg, enabled=True)
    tracker.on_round_start(1)
    assert reg.calls == [("sess-1", "BUILD")]


def test_enabled_tracker_plan_mode_sets_plan():
    reg = _FakeRegistry()
    tracker = PhaseTracker("sess-2", registry=reg, enabled=True)
    tracker.on_round_start(1, plan_mode=True)
    assert reg.calls == [("sess-2", "PLAN")]


def test_exported_from_package():
    from src.orchestrator import PhaseTracker as PT
    from src.orchestrator import tracker_enabled as te

    assert PT is PhaseTracker
    assert te is tracker_enabled
