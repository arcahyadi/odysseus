"""
tests/phase2/test_namespace.py

Property and unit tests for NamespaceResolver (persona memory isolation).
Requirements: 5.1-5.8 (phase 2)

# Feature: phase-2-knowledge-memory, Property: Namespace Visibility
"""
import pytest
from hypothesis import given, settings, strategies as st

from services.memory.namespace import NamespaceResolver, GLOBAL_NS


def _make_resolver(entries):
    def _save(_self, new_entries):
        snapshot = list(new_entries)  # may alias `entries`; snapshot before mutating
        entries[:] = snapshot

    mm = type("MM", (), {
        "load_all": lambda self: entries,
        "save": _save,
    })()
    return NamespaceResolver(mm), mm


# ── write_entry ──────────────────────────────────────────────────────────────

@given(st.one_of(st.none(), st.text(min_size=1, max_size=40)))
@settings(max_examples=40)
def test_write_entry_namespace_tags(crew_id):
    resolver, _ = _make_resolver([])
    entry = resolver.write_entry({"text": "x", "owner": "alice"}, crew_id)
    expected = crew_id if crew_id else GLOBAL_NS
    assert entry["namespace"] == expected


# ── filter_for_session ───────────────────────────────────────────────────────

def test_filter_for_session_persona_sees_persona_and_global():
    resolver, _ = _make_resolver([])
    entries = [
        {"id": "1", "owner": "alice", "namespace": "crew-a", "text": "persona"},
        {"id": "2", "owner": "alice", "namespace": GLOBAL_NS, "text": "global"},
        {"id": "3", "owner": "alice", "text": "legacy-no-ns"},
        {"id": "4", "owner": "bob", "namespace": GLOBAL_NS, "text": "other"},
        {"id": "5", "owner": "alice", "namespace": "crew-b", "text": "other-persona"},
    ]
    visible = resolver.filter_for_session(entries, owner="alice", crew_member_id="crew-a")
    ids = {e["id"] for e in visible}
    assert ids == {"1", "2", "3"}  # own persona + global + legacy-no-ns


def test_filter_for_session_global_only_global():
    resolver, _ = _make_resolver([])
    entries = [
        {"id": "1", "owner": "alice", "namespace": "crew-a"},
        {"id": "2", "owner": "alice", "namespace": GLOBAL_NS},
    ]
    visible = resolver.filter_for_session(entries, owner="alice", crew_member_id=None)
    assert [e["id"] for e in visible] == ["2"]


# ── promote_to_global ────────────────────────────────────────────────────────

def test_promote_to_global_moves_entry():
    entries = [{"id": "1", "owner": "alice", "namespace": "crew-a", "text": "t"}]
    resolver, _ = _make_resolver(entries)
    out = resolver.promote_to_global("1", "alice")
    assert out["namespace"] == GLOBAL_NS
    assert entries[0]["namespace"] == GLOBAL_NS


def test_promote_missing_entry_raises_keyerror():
    resolver, _ = _make_resolver([])
    with pytest.raises(KeyError):
        resolver.promote_to_global("missing", "alice")


def test_promote_other_owner_raises_keyerror():
    entries = [{"id": "1", "owner": "alice", "namespace": "crew-a"}]
    resolver, _ = _make_resolver(entries)
    with pytest.raises(KeyError):
        resolver.promote_to_global("1", "bob")


def test_promote_already_global_raises_valueerror():
    entries = [{"id": "1", "owner": "alice", "namespace": GLOBAL_NS}]
    resolver, _ = _make_resolver(entries)
    with pytest.raises(ValueError):
        resolver.promote_to_global("1", "alice")
