"""
tests/phase3/test_email_rules.py

Unit tests for the email automation rules engine and action execution.
Requirement: email automation rules (#6 gap analysis).

# Feature: email-rules, Property: Rule Matcher Substring Semantics
"""
import json

from hypothesis import given, settings, strategies as st

from services.email_rules import (
    RuleEngine,
    rule_matches,
    parse_actions,
    execute_rule_actions,
)


def _rule(**over):
    base = {"id": "r1", "name": "Test", "enabled": True, "matchers": {}, "actions": []}
    base.update(over)
    return base


def _email(**over):
    base = {"sender": "alerts@example.com", "subject": "Build failed", "body": "The nightly build broke.", "folder": "INBOX"}
    base.update(over)
    return base


# ── Rule matcher semantics ───────────────────────────────────────────────────

@given(st.text(min_size=1, max_size=40))
@settings(max_examples=40)
def test_sender_match_is_case_insensitive_substring(fragment):
    email = _email(sender=f"Something {fragment} @EXAMPLE.com")
    assert rule_matches(_rule(matchers={"sender_contains": fragment.lower()}), email)


def test_all_matchers_required():
    rule = _rule(matchers={
        "sender_contains": "alerts",
        "subject_contains": "build",
        "body_contains": "nightly",
        "folder": "inbox",
    })
    assert rule_matches(rule, _email())
    assert not rule_matches(rule, _email(sender="other@example.com"))
    assert not rule_matches(rule, _email(subject="Hello"))
    assert not rule_matches(rule, _email(body="nothing relevant at all here"))
    assert not rule_matches(rule, _email(folder="Junk"))


def test_empty_matchers_match_anything():
    assert rule_matches(_rule(matchers={}), _email(sender="", subject="", body=""))


def test_parse_actions_filters_vocabulary():
    assert parse_actions(["create_task", "summarize", "fly_to_moon", "draft_reply"]) == [
        "create_task", "summarize", "draft_reply",
    ]
    assert parse_actions("not-json") == []
    assert parse_actions(42) == []


# ── Engine ───────────────────────────────────────────────────────────────────

def test_engine_skips_disabled_rules_and_unions_actions():
    rules = [
        _rule(id="a", enabled=True, matchers={"sender_contains": "alerts"}, actions=["summarize", "create_task"]),
        _rule(id="b", enabled=False, matchers={"sender_contains": "alerts"}, actions=["add_event"]),
        _rule(id="c", enabled=True, matchers={"sender_contains": "alerts"}, actions=["summarize"]),
    ]
    engine = RuleEngine(rules_loader=lambda owner: rules)
    matched = engine.matching_rules("alice", _email())
    assert {r["id"] for r in matched} == {"a", "c"}
    assert engine.matching_actions("alice", _email()) == ["summarize", "create_task"]


def test_engine_no_match():
    engine = RuleEngine(rules_loader=lambda owner: [_rule(matchers={"sender_contains": "nope"})])
    assert engine.matching_rules("alice", _email()) == []
    assert engine.matching_actions("alice", _email()) == []


# ── Action execution (create_task) ──────────────────────────────────────────

def test_execute_create_task_inserts_note():
    added = []

    class FakeSession:
        def add(self, obj): added.append(obj)
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    results = execute_rule_actions("alice", _email(subject="Build failed"),
                                   ["create_task"], db_factory=lambda: FakeSession())
    assert results[0]["action"] == "create_task"
    assert results[0]["ok"] is True
    note = added[0]
    assert note.note_type == "checklist"
    assert note.source == "email-rule"
    assert "Build failed" in note.title
    assert json.loads(note.items)[0]["done"] is False


def test_execute_advisory_actions_reported_without_notes():
    results = execute_rule_actions("alice", _email(), ["add_event"], db_factory=lambda: _FakeEmpty())
    assert results[0]["action"] == "add_event"
    assert results[0]["ok"] is True
    assert "advisory" in results[0]["detail"]


class _FakeEmpty:
    def add(self, obj): pass
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
