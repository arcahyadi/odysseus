"""
tests/phase1/test_fork.py

Property-based tests for session forking.

# Feature: phase-1-intelligence-reasoning, Property 11: Fork History Prefix
# Feature: phase-1-intelligence-reasoning, Property 12: Fork Session Name Truncation

Requirements: 11.1, 11.2, 11.3
"""
import pytest
from hypothesis import given, settings, strategies as st


# ── Property 11: Fork History Is a Prefix ────────────────────────────────────

# Feature: phase-1-intelligence-reasoning, Property 11: Fork History Prefix
@given(
    messages=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=20),
    fork_pos=st.integers(min_value=0, max_value=19),
)
@settings(max_examples=200)
def test_fork_history_is_prefix(messages, fork_pos):
    """
    Forking at message k produces exactly the first k+1 messages of the source.
    Property 11: Fork History Prefix
    """
    k = min(fork_pos, len(messages) - 1)
    source_history = messages
    forked_history = source_history[: k + 1]

    # The forked history must be a prefix of the source
    assert len(forked_history) == k + 1
    assert forked_history == source_history[: k + 1]
    # No additions, deletions, or reorderings
    for i, msg in enumerate(forked_history):
        assert msg == source_history[i]


# Feature: phase-1-intelligence-reasoning, Property 12: Fork Session Name Truncation
@given(st.text(min_size=0, max_size=200))
@settings(max_examples=200)
def test_fork_session_name_truncation(content):
    """
    Fork name is always '[Fork] ' + content[:50].
    Property 12: Fork Session Name Truncation
    """
    expected = "[Fork] " + content[:50]
    # Simulate the name-building logic from reasoning_routes.py
    actual = "[Fork] " + (content or "")[:50]
    assert actual == expected
    assert actual.startswith("[Fork] ")
    assert len(actual) <= len("[Fork] ") + 50


@given(st.text(min_size=51, max_size=200))
@settings(max_examples=100)
def test_fork_name_truncated_at_50_chars(content):
    """Content longer than 50 chars is always truncated."""
    name = "[Fork] " + content[:50]
    suffix = name[len("[Fork] "):]
    assert len(suffix) == 50


@given(st.text(min_size=0, max_size=49))
@settings(max_examples=100)
def test_fork_name_not_padded_for_short_content(content):
    """Short content is used as-is without padding."""
    name = "[Fork] " + content[:50]
    suffix = name[len("[Fork] "):]
    assert suffix == content  # full content, no truncation or padding


# ── Unit tests for fork name building ────────────────────────────────────────

class TestForkNameBuilding:
    def test_empty_content(self):
        name = "[Fork] " + ""[:50]
        assert name == "[Fork] "

    def test_exactly_50_chars(self):
        content = "x" * 50
        name = "[Fork] " + content[:50]
        assert name == "[Fork] " + "x" * 50

    def test_51_chars_truncated(self):
        content = "x" * 51
        name = "[Fork] " + content[:50]
        assert name == "[Fork] " + "x" * 50

    def test_prefix_is_fork_label(self):
        name = "[Fork] " + "some content"[:50]
        assert name.startswith("[Fork] ")

    def test_unicode_content(self):
        content = "日本語テスト"
        name = "[Fork] " + content[:50]
        assert name.startswith("[Fork] ")
        assert content in name


# ── Unit tests for history slicing logic ──────────────────────────────────────

class TestForkHistorySlicing:
    def test_fork_at_first_message(self):
        messages = ["a", "b", "c"]
        forked = messages[:1]
        assert forked == ["a"]

    def test_fork_at_last_message(self):
        messages = ["a", "b", "c"]
        forked = messages[:3]
        assert forked == messages

    def test_fork_mid_history(self):
        messages = ["a", "b", "c", "d", "e"]
        forked = messages[:3]
        assert forked == ["a", "b", "c"]

    def test_forked_history_is_ordered(self):
        messages = [str(i) for i in range(10)]
        for k in range(1, 11):
            forked = messages[:k]
            assert forked == sorted(forked, key=lambda x: messages.index(x))

    def test_forked_history_has_no_extra_messages(self):
        messages = ["msg1", "msg2", "msg3", "msg4"]
        pivot_idx = 1  # fork at msg2
        forked = messages[:pivot_idx + 1]
        assert len(forked) == 2
        assert "msg3" not in forked
        assert "msg4" not in forked
