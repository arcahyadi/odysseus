"""Regression guard for the ODYSSEUS_INTERNAL_TOKEN hardening.

Before 2026-10-03 `require_admin()` accepted any value an operator put in
ODYSSEUS_INTERNAL_TOKEN — including short example strings copied from
READMEs — which silently opened every admin-gated route to any request
carrying the matching X-Odysseus-Internal-Token header.
`_resolve_internal_tool_token` now rejects values shorter than 32 chars
or with <4 distinct characters, falling back to a random per-process
token so the bypass cannot be opened by an accidental weak value.
"""
import importlib
import secrets


def _reload_middleware(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ODYSSEUS_INTERNAL_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ODYSSEUS_INTERNAL_TOKEN", value)
    from core import middleware
    return importlib.reload(middleware)


def test_no_env_value_yields_random_token(monkeypatch):
    mw = _reload_middleware(monkeypatch, None)
    assert len(mw.INTERNAL_TOOL_TOKEN) == 64  # secrets.token_hex(32)
    assert mw._looks_weak(mw.INTERNAL_TOOL_TOKEN) is None
    assert mw._INTERNAL_TOKEN_REJECT_REASON is None


def test_short_operator_value_is_rejected_and_replaced(monkeypatch):
    weak = "changeme"
    mw = _reload_middleware(monkeypatch, weak)
    assert mw.INTERNAL_TOOL_TOKEN != weak
    assert mw._INTERNAL_TOKEN_REJECT_REASON == "shorter than 32 chars"


def test_low_char_variety_is_rejected(monkeypatch):
    # 40 zeros: long enough but only one distinct char.
    mw = _reload_middleware(monkeypatch, "0" * 40)
    assert mw._INTERNAL_TOKEN_REJECT_REASON == "insufficient character variety"
    assert mw.INTERNAL_TOOL_TOKEN != "0" * 40


def test_three_distinct_chars_is_rejected(monkeypatch):
    # "aB1" repeated 11 times = 33 chars, 3 distinct.
    mw = _reload_middleware(monkeypatch, "aB1" * 11)
    assert mw._INTERNAL_TOKEN_REJECT_REASON == "insufficient character variety"


def test_strong_operator_value_is_accepted(monkeypatch):
    good = secrets.token_hex(32)
    mw = _reload_middleware(monkeypatch, good)
    assert mw.INTERNAL_TOOL_TOKEN == good
    assert mw._INTERNAL_TOKEN_REJECT_REASON is None


def test_looks_weak_helper_covers_all_branches():
    from core.middleware import _looks_weak
    assert _looks_weak("") == "empty"
    assert _looks_weak("   ") == "empty"
    assert _looks_weak("x" * 8) == "shorter than 32 chars"
    assert _looks_weak("ab" * 20) == "insufficient character variety"
    assert _looks_weak(secrets.token_hex(32)) is None


def teardown_module(_module):
    # Reload one more time so subsequent tests see the pristine
    # no-env-value state.
    import os
    os.environ.pop("ODYSSEUS_INTERNAL_TOKEN", None)
    from core import middleware
    importlib.reload(middleware)
