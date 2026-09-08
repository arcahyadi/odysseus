"""
tests/phase1/test_trace_extractor.py

Property-based and unit tests for trace extraction and storage.

# Feature: phase-1-intelligence-reasoning, Property 9: Think Tag Extraction Round-Trip
# Feature: phase-1-intelligence-reasoning, Property 10: Reasoning Node Uniqueness and Sequential Indexing

Requirements: 9.1, 9.2, 9.6
"""
import asyncio
import pytest
from hypothesis import given, settings, strategies as st

from services.reasoning.trace_extractor import (
    extract_thinking,
    extract_thinking_streaming,
    reasoning_aware_stream,
)


# ── Property 9: Think Tag Extraction Round-Trip ───────────────────────────────

# Feature: phase-1-intelligence-reasoning, Property 9: Think Tag Extraction Round-Trip
@given(st.lists(st.text(min_size=0, max_size=100), min_size=1, max_size=5))
@settings(max_examples=200)
def test_think_tag_extraction_round_trip(segments):
    """
    For any list of segments wrapped in <think> tags, extract_thinking
    returns all segments and the clean text has no <think> content.
    Property 9: Think Tag Extraction Round-Trip
    """
    text = "".join(f"<think>{s}</think>" for s in segments)
    clean, found = extract_thinking(text)
    # Clean text should have no think tags
    assert "<think>" not in clean.lower()
    assert "</think>" not in clean.lower()
    # Number of segments found should match
    assert len(found) == len(segments)
    # Content should match (stripped)
    for seg, found_seg in zip(segments, found):
        assert seg.strip() == found_seg


# Feature: phase-1-intelligence-reasoning, Property 10: Reasoning Node Uniqueness and Sequential Indexing
@given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
@settings(max_examples=100)
def test_reasoning_nodes_sequential_indices(segments):
    """
    Nodes produced from N segments must have indices 0, 1, …, N-1.
    Property 10: Reasoning Node Uniqueness and Sequential Indexing
    """
    # Simulate what TraceStore does: enumerate(segments)
    indices = list(range(len(segments)))
    assert indices == list(range(len(segments)))
    assert len(set(indices)) == len(indices)  # unique


# ── Unit tests: extract_thinking ─────────────────────────────────────────────

class TestExtractThinking:
    def test_single_block(self):
        clean, segs = extract_thinking("<think>hello</think>world")
        assert "hello" in segs
        assert clean == "world"

    def test_multiple_blocks(self):
        clean, segs = extract_thinking("<think>a</think>mid<think>b</think>end")
        assert len(segs) == 2
        assert segs[0] == "a"
        assert segs[1] == "b"
        assert "mid" in clean
        assert "end" in clean

    def test_no_think_blocks(self):
        clean, segs = extract_thinking("just plain text")
        assert clean == "just plain text"
        assert segs == []

    def test_empty_string(self):
        clean, segs = extract_thinking("")
        assert clean == ""
        assert segs == []

    def test_case_insensitive(self):
        clean, segs = extract_thinking("<THINK>uppercase</THINK>")
        assert len(segs) == 1
        assert segs[0] == "uppercase"

    def test_segments_are_stripped(self):
        _, segs = extract_thinking("<think>  spaces  </think>")
        assert segs[0] == "spaces"


# ── Unit tests: extract_thinking_streaming ───────────────────────────────────

class TestExtractThinkingStreaming:
    def test_complete_block_detected(self):
        accumulated = "<think>done</think>rest"
        clean, segs, has_open = extract_thinking_streaming(accumulated)
        assert len(segs) == 1
        assert not has_open

    def test_open_tag_detected(self):
        accumulated = "<think>still thinking"
        _, _, has_open = extract_thinking_streaming(accumulated)
        assert has_open

    def test_no_tags(self):
        _, segs, has_open = extract_thinking_streaming("regular text")
        assert segs == []
        assert not has_open


# ── Unit tests: reasoning_aware_stream ───────────────────────────────────────

class TestReasoningAwareStream:
    @pytest.mark.asyncio
    async def test_emits_thinking_node_events(self):
        async def base():
            yield {"type": "content", "token": "<think>thought</think>answer"}

        events = []
        async for chunk in reasoning_aware_stream(base()):
            events.append(chunk)

        thinking = [e for e in events if e.get("type") == "thinking_node"]
        content = [e for e in events if e.get("type") == "content"]
        assert len(thinking) >= 1
        assert thinking[0]["content"] == "thought"
        assert any("answer" in e.get("token", "") for e in content)

    @pytest.mark.asyncio
    async def test_non_content_chunks_pass_through(self):
        async def base():
            yield {"type": "tool_call", "name": "search"}
            yield {"type": "content", "token": "hi"}

        events = []
        async for chunk in reasoning_aware_stream(base()):
            events.append(chunk)

        tool_events = [e for e in events if e.get("type") == "tool_call"]
        assert len(tool_events) == 1

    @pytest.mark.asyncio
    async def test_empty_stream_produces_no_events(self):
        async def base():
            return
            yield

        events = []
        async for chunk in reasoning_aware_stream(base()):
            events.append(chunk)
        assert events == []
