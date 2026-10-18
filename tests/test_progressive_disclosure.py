"""Tests for P5 progressive disclosure (Palier 0 switch).

Why this file exists at all
---------------------------
The M6.8 call site in `archive/legacy/agent_loop.py` referenced a bare free
name `phase`. It raised `NameError`, and the surrounding blanket
`except Exception` swallowed it at debug level — so the block had **never
executed once**, and `ruff` had been reporting `F821 Undefined name 'phase'`
the whole time. No test covered the module, so nothing noticed.

That combination — zero coverage on a module whose call site was dead — is
what these tests exist to prevent from recurring. The switch flipped to ON by
default with Palier 0, so the module is now on the default path and its
behaviour is part of the contract.
"""

import pathlib
import re

import pytest

from src.orchestrator.phases import Phase
from src.progressive_disclosure import (
    DisclosureLevel,
    ProgressiveDisclosure,
    get_progressive_disclosure,
    progressive_disclosure_enabled,
)
from src.risk_classifier import RiskLevel

# ── kill-switch ─────────────────────────────────────────────────────────


def test_enabled_by_default(monkeypatch):
    """Palier 0 (FND-4 option C): the switch is ON by default."""
    monkeypatch.delenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", raising=False)
    assert progressive_disclosure_enabled() is True


def test_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", "off")
    assert progressive_disclosure_enabled() is False


@pytest.mark.parametrize("val", ["on", "1", "true", "yes", "ON", " true "])
def test_truthy_values(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", val)
    assert progressive_disclosure_enabled() is True


@pytest.mark.parametrize("val", ["off", "0", "false", "no", ""])
def test_falsey_values(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", val)
    assert progressive_disclosure_enabled() is False


# ── phase → level mapping ───────────────────────────────────────────────


def test_dangerous_phases_get_minimal_disclosure():
    """CLASSIFY / AUTOEVAL / MEMORY_OBSERVE must not expose the full catalogue."""
    pd = ProgressiveDisclosure()
    for phase in (Phase.CLASSIFY, Phase.AUTOEVAL, Phase.MEMORY_OBSERVE):
        assert pd.resolve_level(phase) is DisclosureLevel.MINIMAL, phase


def test_build_and_quality_get_full_disclosure():
    pd = ProgressiveDisclosure()
    for phase in (Phase.BUILD, Phase.QUALITY):
        assert pd.resolve_level(phase) is DisclosureLevel.FULL, phase


def test_every_canonical_phase_resolves():
    """The mapping must cover the whole enum, not just the phases we remember."""
    pd = ProgressiveDisclosure()
    for phase in Phase:
        assert isinstance(pd.resolve_level(phase), DisclosureLevel), phase


# ── risk only ever narrows, never widens ───────────────────────────────


def test_risk_caps_disclosure_but_never_widens_it():
    """Higher risk must shrink the surface; it must never grow it.

    The principle is one-directional on purpose: a low-risk phase can be
    capped by risk, but a risky phase must not be widened back to FULL by a
    permissive phase mapping.
    """
    pd = ProgressiveDisclosure()
    for phase in Phase:
        base = pd.resolve_level(phase)
        for risk in RiskLevel:
            capped = pd.resolve_level(phase, risk)
            order = [DisclosureLevel.MINIMAL, DisclosureLevel.STANDARD, DisclosureLevel.FULL]
            assert order.index(capped) <= order.index(base), (phase, risk)


@pytest.mark.parametrize("risk", [RiskLevel.EXEC, RiskLevel.DESTRUCTIVE])
def test_execution_and_destructive_risk_force_minimal_whatever_the_phase(risk):
    pd = ProgressiveDisclosure()
    for phase in Phase:
        assert pd.resolve_level(phase, risk) is DisclosureLevel.MINIMAL, (phase, risk)


# ── allowed set ─────────────────────────────────────────────────────────


def test_allowed_set_shrinks_as_disclosure_narrows():
    pd = ProgressiveDisclosure()
    minimal = pd.get_allowed_tools(DisclosureLevel.MINIMAL)
    standard = pd.get_allowed_tools(DisclosureLevel.STANDARD)
    full = pd.get_allowed_tools(DisclosureLevel.FULL)
    assert minimal < standard < full


def test_is_tool_allowed_follows_the_resolved_level():
    pd = ProgressiveDisclosure()
    full_tools = pd.get_allowed_tools(DisclosureLevel.FULL)
    tool = sorted(full_tools)[0]
    assert pd.is_tool_allowed(tool, Phase.BUILD) is True


def test_minimal_surface_is_a_strict_subset_of_full():
    pd = ProgressiveDisclosure()
    assert pd.get_allowed_tools(DisclosureLevel.MINIMAL) < pd.get_allowed_tools(DisclosureLevel.FULL)


# ── summary (the shape the live M6.8 block actually consumes) ──────────


def test_summary_shape_matches_what_the_loop_logs():
    """M6.8 reads disclosure_level and allowed_tool_count; keep those keys."""
    pd = ProgressiveDisclosure()
    s = pd.get_disclosure_summary(Phase.BUILD)
    assert set(s) >= {"phase", "risk_level", "disclosure_level", "allowed_tool_count", "allowed_tools"}
    assert s["phase"] == Phase.BUILD.value
    assert s["risk_level"] == "none"
    assert s["allowed_tool_count"] == len(s["allowed_tools"])


def test_summary_reports_the_real_risk_when_given():
    pd = ProgressiveDisclosure()
    s = pd.get_disclosure_summary(Phase.BUILD, RiskLevel.DESTRUCTIVE)
    assert s["risk_level"] == RiskLevel.DESTRUCTIVE.value
    assert s["disclosure_level"] == DisclosureLevel.MINIMAL.value


def test_summary_rejects_a_bare_string_phase():
    """The live call site passes an enum. A string must not silently "work".

    get_disclosure_summary does `phase.value`, so a string used to reach it
    and blow up with an AttributeError at runtime — the exact class of defect
    that made the M6.8 block dead. Pin the requirement explicitly.
    """
    pd = ProgressiveDisclosure()
    with pytest.raises(AttributeError):
        pd.get_disclosure_summary("BUILD")  # type: ignore[arg-type]


# ── singleton ───────────────────────────────────────────────────────────


def test_singleton_is_stable():
    assert get_progressive_disclosure() is get_progressive_disclosure()


# ── the call site that was dead ─────────────────────────────────────────


def test_live_call_site_does_not_pass_a_free_name():
    """Regression guard for the M6.8 defect, pinned in the suite itself.

    The live block used to call `get_disclosure_summary(phase)` with `phase`
    an undefined free name. `ruff` flagged it as F821 the entire time, but no
    *test* did, so nothing failed and the block silently never ran. This
    assertion keeps the defect class out even if the lint config is relaxed.
    """
    src = pathlib.Path(__file__).resolve().parent.parent / "archive" / "legacy" / "agent_loop.py"
    text = src.read_text(encoding="utf-8")

    # Every call must receive something that is defined in that scope.
    calls = re.findall(r"get_disclosure_summary\(([^)]*)\)", text)
    assert calls, "the M6.8 call site disappeared — re-check this guard"
    for raw_arg in calls:
        arg = raw_arg.strip()
        assert arg.startswith("_m68_phase"), (
            f"get_disclosure_summary({arg!r}) does not use the resolved phase; "
            f"a bare name here is exactly how the block became dead code"
        )
        assert "_m68_phase =" in text, "the resolved phase is never assigned"


def test_resolved_phase_falls_back_to_build_when_absent():
    """The loop must degrade to BUILD, not raise, when no phase was resolved.

    Mirrors the live coercion: any non-Phase input, including None, becomes a
    real Phase.BUILD so `get_disclosure_summary` can do `phase.value`.
    """
    for candidate in (None, "build", "PLAN", 42):
        phase = candidate
        if not isinstance(phase, Phase):
            try:
                phase = Phase(str(getattr(phase, "value", phase) or "BUILD"))
            except ValueError:
                phase = Phase.BUILD
        assert isinstance(phase, Phase)
        assert ProgressiveDisclosure().get_disclosure_summary(phase)["phase"] == phase.value

