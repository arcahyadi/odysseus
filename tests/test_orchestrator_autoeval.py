"""Tests for the AUTOEVAL keep/revert verifier (M3.3).

SAFETY: the git revert path is NEVER exercised for real here. Every test
injects a fake git-runner and asserts on calls. `apply_autoeval` must be a
no-op (byte-identical to today) whenever the kill-switch is OFF.
"""

from src.observer import DriftLevel
from src.orchestrator.autoeval import (
    AutoevalDecision,
    apply_autoeval,
    autoeval_enabled,
    decide_keep_or_revert,
    destructive_revert_allowed,
)


class _FakeGitRunner:
    """Records revert requests instead of touching the working tree."""

    def __init__(self, ok: bool = True, raises: bool = False):
        self.calls = []
        self._ok = ok
        self._raises = raises

    def __call__(self):
        self.calls.append("reset_hard")
        if self._raises:
            raise RuntimeError("boom — this must be swallowed")
        return self._ok


# ── kill-switch ─────────────────────────────────────────────────────────


def test_autoeval_enabled_by_default(monkeypatch):
    """Palier 0 (FND-4 option C): AUTOEVAL decides by default again.

    The default was flipped off->on; the OFF polarity is still tested below,
    because a kill-switch nobody can turn off is not a kill-switch.
    """
    monkeypatch.delenv("ODYSSEUS_AUTOEVAL", raising=False)
    assert autoeval_enabled() is True


def test_autoeval_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "off")
    assert autoeval_enabled() is False


# ── destructive-action gate (2nd, independent switch) ───────────────────


def test_destructive_revert_denied_by_default(monkeypatch):
    """AUTOEVAL deciding "revert" must NOT by itself authorise `git reset --hard`.

    Regression guard: with AUTOEVAL on and ALLOW_RESET unset, a real test run
    used to hard-reset the working tree and silently destroy uncommitted work.
    """
    monkeypatch.delenv("ODYSSEUS_AUTOEVAL_ALLOW_RESET", raising=False)
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    assert autoeval_enabled() is True
    assert destructive_revert_allowed() is False


def test_destructive_revert_allowed_on_explicit_optin(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL_ALLOW_RESET", "on")
    assert destructive_revert_allowed() is True


def test_destructive_revert_gate_independent_of_decision_switch(monkeypatch):
    """The two switches must not shadow each other."""
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "off")
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL_ALLOW_RESET", "on")
    assert autoeval_enabled() is False
    assert destructive_revert_allowed() is True


def test_autoeval_enabled_when_env_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    assert autoeval_enabled() is True


def test_autoeval_enabled_accepts_truthy_values(monkeypatch):
    for val in ("1", "true", "yes", "ON"):
        monkeypatch.setenv("ODYSSEUS_AUTOEVAL", val)
        assert autoeval_enabled() is True


def test_autoeval_off_for_falsey_values(monkeypatch):
    for val in ("off", "0", "false", "no", ""):
        monkeypatch.setenv("ODYSSEUS_AUTOEVAL", val)
        assert autoeval_enabled() is False


# ── pure decision function ──────────────────────────────────────────────


def test_decide_keep_when_verifier_passes():
    # empty verifier reasons == SUCCESS
    assert decide_keep_or_revert([]) == "keep"


def test_decide_keep_when_verifier_none():
    assert decide_keep_or_revert(None) == "keep"


def test_decide_revert_on_verifier_failure():
    assert decide_keep_or_revert(["missing deliverable"]) == "revert"


def test_decide_revert_on_high_drift():
    assert decide_keep_or_revert([], drift_level=DriftLevel.HIGH) == "revert"


def test_decide_keep_on_medium_drift():
    # conservative: only clear failures revert. MEDIUM/LOW keep.
    assert decide_keep_or_revert([], drift_level=DriftLevel.MEDIUM) == "keep"
    assert decide_keep_or_revert([], drift_level=DriftLevel.LOW) == "keep"


def test_decide_verifier_failure_dominates_low_drift():
    assert decide_keep_or_revert(["bad"], drift_level=DriftLevel.LOW) == "revert"


# ── apply_autoeval: gating + injected git runner ────────────────────────


def test_apply_noop_when_disabled_even_on_failure(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "off")
    runner = _FakeGitRunner()
    d = apply_autoeval(["failed"], drift_level=DriftLevel.HIGH, git_runner=runner)
    assert runner.calls == []  # NO destructive path when OFF
    assert d.reverted is False
    assert d.decision == "keep"  # forced keep when disabled
    assert d.enabled is False


def test_apply_decides_revert_by_default_but_action_is_callers_choice(monkeypatch):
    """Default is ON: the decision flips to "revert"...

    ...but whether a real `git reset --hard` runs is the CALLER's choice. Here
    the caller passes no runner, which is what langgraph_loop now does unless
    ODYSSEUS_AUTOEVAL_ALLOW_RESET is explicitly set. The decision is still
    reported, so the signal stays observable.
    """
    monkeypatch.delenv("ODYSSEUS_AUTOEVAL", raising=False)
    d = apply_autoeval(["failed"], drift_level=DriftLevel.HIGH, git_runner=None)
    assert d.enabled is True
    assert d.decision == "revert"
    assert d.reverted is False
    assert d.error == "no git_runner injected"


def test_apply_reverts_on_failure_when_enabled(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    runner = _FakeGitRunner(ok=True)
    d = apply_autoeval(["failed"], drift_level=None, git_runner=runner)
    assert runner.calls == ["reset_hard"]
    assert d.decision == "revert"
    assert d.reverted is True
    assert d.enabled is True


def test_apply_keeps_on_success_when_enabled(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    runner = _FakeGitRunner()
    d = apply_autoeval([], drift_level=DriftLevel.LOW, git_runner=runner)
    assert runner.calls == []  # keep never calls git
    assert d.decision == "keep"
    assert d.reverted is False


def test_apply_reverts_on_high_drift_when_enabled(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    runner = _FakeGitRunner(ok=True)
    d = apply_autoeval([], drift_level=DriftLevel.HIGH, git_runner=runner)
    assert runner.calls == ["reset_hard"]
    assert d.decision == "revert"
    assert d.reverted is True


def test_apply_never_raises_when_git_runner_throws(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    runner = _FakeGitRunner(raises=True)
    # must swallow the exception and report revert failure, not crash the loop
    d = apply_autoeval(["failed"], drift_level=None, git_runner=runner)
    assert runner.calls == ["reset_hard"]
    assert d.decision == "revert"
    assert d.reverted is False  # runner blew up → not reverted
    assert d.error is not None


def test_apply_revert_reports_false_when_runner_returns_false(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    runner = _FakeGitRunner(ok=False)
    d = apply_autoeval(["failed"], drift_level=None, git_runner=runner)
    assert runner.calls == ["reset_hard"]
    assert d.reverted is False


def test_apply_without_git_runner_never_reverts(monkeypatch):
    # defensive: enabled + revert decision but no runner injected → no crash
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    d = apply_autoeval(["failed"], drift_level=None, git_runner=None)
    assert d.decision == "revert"
    assert d.reverted is False


def test_decision_is_dataclass_with_expected_fields():
    d = AutoevalDecision(enabled=False, decision="keep", reverted=False, error=None)
    assert d.enabled is False
    assert d.decision == "keep"
    assert d.reverted is False
    assert d.error is None


def test_exported_from_package():
    from src.orchestrator import (
        apply_autoeval as ap,
    )
    from src.orchestrator import (
        autoeval_enabled as ae,
    )
    from src.orchestrator import (
        decide_keep_or_revert as dk,
    )

    assert ae is autoeval_enabled
    assert dk is decide_keep_or_revert
    assert ap is apply_autoeval
