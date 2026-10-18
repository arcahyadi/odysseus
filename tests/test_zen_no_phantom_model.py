"""M3.1 — kill the phantom Zen model id.

zen_router hardcoded `deepseek-v4-flash-free` as the last-resort fallback in
four places. That id is a phantom: it is NOT in model-routing.json's confirmed
catalog ("tous testés sur /zen/go/v1") and appears nowhere else in the tree, so
if the config lookup ever falls through the router would POST a non-existent
model to the Zen API. These tests pin a single confirmed default constant and
prove neither candidate builder can emit a `-free` phantom.
"""

import json
from pathlib import Path

import src.zen_router as zr

_CATALOG = json.loads((Path(zr.__file__).parent.parent / "model-routing.json").read_text(encoding="utf-8"))
_CONFIRMED_IDS = {m["model_id"] for m in _CATALOG["models"].values()}


def test_default_model_constant_is_confirmed_and_not_free():
    assert hasattr(zr, "_DEFAULT_ZEN_MODEL")
    assert not zr._DEFAULT_ZEN_MODEL.endswith("-free")
    assert zr._DEFAULT_ZEN_MODEL in _CONFIRMED_IDS


def test_get_zen_candidate_falls_back_to_confirmed_id_when_model_missing(monkeypatch):
    # Tier dict with NO model_id → the innermost .get default kicks in.
    cfg = {
        "providers": {
            "opencode_zen": {"enabled": True, "base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"}
        },
        "models": {"fast": {"fallback": []}},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: None)
    monkeypatch.setenv("OPENCODE_API_KEY", "env-key")
    zr._zen_blacklist.clear()

    out = zr.get_zen_candidate("fast")
    assert out is not None
    _url, model, _headers = out
    assert not model.endswith("-free")
    assert model == zr._DEFAULT_ZEN_MODEL


def test_build_zen_candidates_never_emits_free_phantom(monkeypatch):
    cfg = {
        "providers": {
            "opencode_zen": {"enabled": True, "base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"}
        },
        "stages": {"chat": "standard"},
        # standard has no model_id; a fallback tier also lacks one.
        "models": {"standard": {"fallback": ["fast"]}, "fast": {"fallback": []}},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: None)
    monkeypatch.setattr(zr, "classify_complexity", lambda p: ("standard", 0.5))
    monkeypatch.setenv("OPENCODE_API_KEY", "env-key")

    cands = zr.build_zen_candidates([{"role": "user", "content": "hi"}], stage="chat")
    assert cands, "expected at least one candidate"
    for _url, model, _headers in cands:
        assert not model.endswith("-free")
        assert model == zr._DEFAULT_ZEN_MODEL
