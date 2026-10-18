"""M3 zero-redundancy slice — dedup the OpenCode Zen provider config.

The Zen provider's base_url + key live in model-routing.json (providers.
opencode_zen) AND, once an admin registers one, in the native ModelEndpoint
DB table. That is two sources of truth for one endpoint. zen_router's UNIQUE
value is the complexity classifier + tier routing; only the provider *config*
is redundant (verdict PARTIEL → repair in place).

These tests pin an additive resolver: `_zen_provider_conn` prefers a native
ModelEndpoint row (single source of truth) and falls back to exactly today's
JSON + env path. When no row exists — the current state for every user who
configures Zen via env only — behavior is byte-identical to before, so the
live chat path (llm_core.stream_llm_with_fallback) is unchanged.
"""

import src.zen_router as zr


def test_conn_falls_back_to_json_and_env(monkeypatch):
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: None)
    monkeypatch.setenv("OPENCODE_API_KEY", "env-key")
    url, key, from_endpoint = zr._zen_provider_conn({"base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"})
    assert url == "https://json/zen"
    assert key == "env-key"
    assert from_endpoint is False


def test_conn_prefers_native_endpoint_row(monkeypatch):
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: ("https://db/zen", "db-key"))
    monkeypatch.setenv("OPENCODE_API_KEY", "env-key")
    url, key, from_endpoint = zr._zen_provider_conn({"base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"})
    assert url == "https://db/zen"
    assert key == "db-key"
    assert from_endpoint is True


def test_build_candidates_uses_db_row_url_and_key(monkeypatch):
    cfg = {
        "providers": {
            "opencode_zen": {"enabled": True, "base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"}
        },
        "stages": {"chat": "standard"},
        "models": {"standard": {"model_id": "m-standard", "fallback": []}},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: ("https://db/zen", "db-key"))
    monkeypatch.setattr(zr, "classify_complexity", lambda p: ("standard", 0.5))
    cands = zr.build_zen_candidates([{"role": "user", "content": "hi"}], stage="chat")
    assert cands, "expected at least one Zen candidate"
    url, model, headers = cands[0]
    assert url == "https://db/zen"
    assert model == "m-standard"
    assert headers["Authorization"] == "Bearer db-key"


def test_build_candidates_empty_when_no_key_anywhere(monkeypatch):
    cfg = {
        "providers": {
            "opencode_zen": {"enabled": True, "base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"}
        },
        "stages": {},
        "models": {},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: None)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert zr.build_zen_candidates([{"role": "user", "content": "hi"}]) == []


def test_get_zen_candidate_uses_db_row(monkeypatch):
    cfg = {
        "providers": {
            "opencode_zen": {"enabled": True, "base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"}
        },
        "models": {"fast": {"model_id": "m-fast", "fallback": []}},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: ("https://db/zen", "db-key"))
    zr._zen_blacklist.clear()
    out = zr.get_zen_candidate("fast")
    assert out is not None
    url, model, headers = out
    assert url == "https://db/zen"
    assert model == "m-fast"
    assert headers["Authorization"] == "Bearer db-key"


def test_resolve_row_is_best_effort_never_raises():
    result = zr._resolve_zen_endpoint_row()
    assert result is None or (isinstance(result, tuple) and len(result) == 2)
