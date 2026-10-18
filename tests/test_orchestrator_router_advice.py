"""Tests for advisory routing (M3.1, retargeted to NATIVE roles).

After the native-capability mapping (.planning/intel/INDEX.md), the grafted
ModelRouter was verdict REDUNDANT (phantom catalog, no dispatch call-site). The
advisory now suggests a NATIVE role (default/utility/research/vision) that the
native resolve_endpoint already understands — no phantom model catalog.
"""

from src.orchestrator.router_advice import advise, intent_to_role, router_enabled


def test_router_enabled_by_default(monkeypatch):
    """Palier 0 (FND-4 option C): MODEL_ROUTER is ON by default again.

    The OFF polarity is still covered right below: a kill-switch nobody
    can turn off is not a kill-switch.
    """
    monkeypatch.delenv("ODYSSEUS_MODEL_ROUTER", raising=False)
    assert router_enabled() is True


def test_router_can_be_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_MODEL_ROUTER", "off")
    assert router_enabled() is False


def test_router_enabled_when_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_MODEL_ROUTER", "on")
    assert router_enabled() is True


def test_router_enabled_accepts_truthy(monkeypatch):
    for val in ("1", "true", "yes", "ON"):
        monkeypatch.setenv("ODYSSEUS_MODEL_ROUTER", val)
        assert router_enabled() is True


def test_intent_to_role_maps_every_category_to_native_role():
    # Native roles known to resolve_endpoint: default/utility/research/vision.
    assert intent_to_role("quick") == "utility"
    assert intent_to_role("utility") == "utility"
    assert intent_to_role("deep") == "research"
    assert intent_to_role("code") == "default"
    assert intent_to_role("creative") == "default"
    assert intent_to_role("vision") == "vision"


def test_intent_to_role_unknown_defaults_to_default():
    assert intent_to_role("something-else") == "default"


def test_advise_deep_intent_suggests_research_role():
    out = advise("implement a distributed consensus algorithm with strong security")
    assert out["intent"] == "deep"
    assert out["suggested_role"] == "research"


def test_advise_passes_stage_through():
    out = advise("hello", stage="planning")
    assert out["stage"] == "planning"


def test_advise_empty_text_is_utility_role():
    out = advise("")
    assert out["intent"] == "utility"
    assert out["suggested_role"] == "utility"


def test_advise_returns_no_phantom_model_key():
    # The old phantom-catalog "suggested_model" must be gone.
    out = advise("anything")
    assert "suggested_model" not in out
    assert out["suggested_role"] in {"default", "utility", "research", "vision"}


def test_advise_never_raises():
    # Advisory must never break the loop regardless of input.
    out = advise(None)  # type: ignore[arg-type]
    assert out["intent"]
    assert out["suggested_role"]


def test_exported_from_package():
    from src.orchestrator import advise as a
    from src.orchestrator import router_enabled as re_

    assert a is advise
    assert re_ is router_enabled
