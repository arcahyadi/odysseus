"""Tests for src/orchestrator/loop.py — CanonicalLoop state machine."""

from src.orchestrator.loop import CanonicalLoop
from src.orchestrator.phases import Phase


class _FakeRegistry:
    def __init__(self):
        self.calls = []

    def set_phase(self, session_id, phase):
        self.calls.append((session_id, phase))


def test_starts_at_classify():
    loop = CanonicalLoop(session_id="s1")
    assert loop.current is Phase.CLASSIFY


def test_advance_walks_the_sequence():
    loop = CanonicalLoop(session_id="s1")
    seen = [loop.current]
    while loop.advance():
        seen.append(loop.current)
    assert [p.name for p in seen] == [
        "CLASSIFY",
        "KNOW",
        "PLAN",
        "BUILD",
        "QUALITY",
        "AUTOEVAL",
        "MEMORY_OBSERVE",
    ]


def test_advance_returns_false_at_end():
    loop = CanonicalLoop(session_id="s1")
    for _ in range(6):
        assert loop.advance() is True
    assert loop.current is Phase.MEMORY_OBSERVE
    assert loop.advance() is False
    assert loop.current is Phase.MEMORY_OBSERVE  # stays put


def test_apply_calls_registry_set_phase_with_lock_name():
    reg = _FakeRegistry()
    loop = CanonicalLoop(session_id="s1", registry=reg)
    loop.apply()  # applies current (CLASSIFY)
    loop.advance()
    loop.apply()  # applies KNOW
    assert reg.calls == [("s1", "CLASSIFY"), ("s1", "KNOW")]


def test_apply_without_registry_is_noop():
    loop = CanonicalLoop(session_id="s1", registry=None)
    loop.apply()  # must not raise
    assert loop.current is Phase.CLASSIFY


def test_goto_jumps_to_named_phase_and_applies():
    reg = _FakeRegistry()
    loop = CanonicalLoop(session_id="s1", registry=reg)
    loop.goto(Phase.BUILD)
    assert loop.current is Phase.BUILD
    assert reg.calls == [("s1", "BUILD")]
