"""Zen->ModelEndpoint migration Task 1-3 — endpoint-triggered injection gate.

Task 1: cached "is a Zen endpoint registered?" check so the live gate never
hits the DB on every stream call.
Task 2: `zen_injection_enabled` — env key = today's behavior (unchanged); a
registered endpoint only enables Zen behind the default-OFF kill-switch
ODYSSEUS_ZEN_FROM_ENDPOINT, so the live chat path is byte-identical by default.
Task 3: the model-routing.json provider block is now optional (DB row supplies
url + key + enablement).
"""

import src.zen_router as zr

# ── Task 1: cached endpoint-existence check ──────────────────────────────────


def test_registered_true_when_row_present(monkeypatch):
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: ("https://db/zen", "k"))
    zr._reset_zen_endpoint_cache()
    assert zr.zen_endpoint_registered() is True


def test_registered_false_when_no_row(monkeypatch):
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: None)
    zr._reset_zen_endpoint_cache()
    assert zr.zen_endpoint_registered() is False


def test_result_is_cached_within_ttl(monkeypatch):
    calls = {"n": 0}

    def _row():
        calls["n"] += 1
        return ("https://db/zen", "k")

    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", _row)
    zr._reset_zen_endpoint_cache()
    assert zr.zen_endpoint_registered() is True
    assert zr.zen_endpoint_registered() is True
    assert calls["n"] == 1  # second call served from cache


# ── Task 2: injection gate ───────────────────────────────────────────────────


def test_injection_enabled_by_env_key(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "env-key")
    monkeypatch.delenv("ODYSSEUS_ZEN_FROM_ENDPOINT", raising=False)
    assert zr.zen_injection_enabled() is True


def test_injection_disabled_by_default_without_env(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.delenv("ODYSSEUS_ZEN_FROM_ENDPOINT", raising=False)
    monkeypatch.setattr(zr, "zen_endpoint_registered", lambda: True)
    # endpoint registered but kill-switch OFF → still disabled (byte-identical)
    assert zr.zen_injection_enabled() is False


def test_injection_enabled_by_endpoint_when_killswitch_on(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.setenv("ODYSSEUS_ZEN_FROM_ENDPOINT", "1")
    monkeypatch.setattr(zr, "zen_endpoint_registered", lambda: True)
    assert zr.zen_injection_enabled() is True


def test_endpoint_conn_bypasses_json_enabled_false(monkeypatch):
    cfg = {
        "providers": {
            "opencode_zen": {"enabled": False, "base_url": "https://json/zen", "api_key_env": "OPENCODE_API_KEY"}
        },
        "stages": {"chat": "standard"},
        "models": {"standard": {"model_id": "m-standard", "fallback": []}},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: ("https://db/zen", "db-key"))
    monkeypatch.setattr(zr, "classify_complexity", lambda p: ("standard", 0.5))
    cands = zr.build_zen_candidates([{"role": "user", "content": "hi"}], stage="chat")
    assert cands and cands[0][0] == "https://db/zen"  # enabled=false ignored: endpoint is the source


# ── Task 3: provider block optional ──────────────────────────────────────────


def test_candidates_work_with_no_provider_block(monkeypatch):
    cfg = {
        "stages": {"chat": "standard"},
        "models": {"standard": {"model_id": "m-standard", "fallback": []}},
    }
    monkeypatch.setattr(zr, "_load_routing_config", lambda: cfg)
    monkeypatch.setattr(zr, "_resolve_zen_endpoint_row", lambda: ("https://db/zen", "db-key"))
    monkeypatch.setattr(zr, "classify_complexity", lambda p: ("standard", 0.5))
    cands = zr.build_zen_candidates([{"role": "user", "content": "hi"}], stage="chat")
    assert cands and cands[0][0] == "https://db/zen" and cands[0][1] == "m-standard"
