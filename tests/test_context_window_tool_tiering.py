"""Context-window tool tiering: retrieval `k` and the always-available
baseline must scale to the discovered window so small local models don't
spend their entire budget on tool schemas.
"""
import pytest


def test_always_available_small_is_strict_subset_of_full_set():
    from src.tool_index import ALWAYS_AVAILABLE, ALWAYS_AVAILABLE_SMALL
    assert ALWAYS_AVAILABLE_SMALL <= ALWAYS_AVAILABLE, (
        "The small-context baseline must only drop tools from the full set, "
        "never introduce new ones (otherwise a tight window could see tools "
        "a normal window doesn't)."
    )
    # ask_user + update_plan stay: without them the agent loses the ability
    # to pause for clarification or tick plan steps mid-run.
    assert "ask_user" in ALWAYS_AVAILABLE_SMALL
    assert "update_plan" in ALWAYS_AVAILABLE_SMALL
    # manage_memory is the ambient tool we're willing to drop — RAG still
    # retrieves it on any "remember this" phrasing.
    assert "manage_memory" not in ALWAYS_AVAILABLE_SMALL


def test_compute_tool_retrieval_k_tiers_by_window():
    from src.context_budget import (
        compute_tool_retrieval_k,
        TIER_SMALL_K, TIER_TIGHT_K, TIER_DEFAULT_K, TIER_LARGE_K,
    )
    # Unknown / zero → conservative default (k=8).
    assert compute_tool_retrieval_k(0) == TIER_DEFAULT_K
    assert compute_tool_retrieval_k(-1) == TIER_DEFAULT_K
    # Sub-4K windows: minimal schemas.
    assert compute_tool_retrieval_k(2048) == TIER_SMALL_K
    assert compute_tool_retrieval_k(4095) == TIER_SMALL_K
    # 4K-8K windows: slightly wider.
    assert compute_tool_retrieval_k(4096) == TIER_TIGHT_K
    assert compute_tool_retrieval_k(8191) == TIER_TIGHT_K
    # 8K-32K: today's behaviour (8).
    assert compute_tool_retrieval_k(8192) == TIER_DEFAULT_K
    assert compute_tool_retrieval_k(16384) == TIER_DEFAULT_K
    assert compute_tool_retrieval_k(32767) == TIER_DEFAULT_K
    # 32K and up: room for a wider retrieval.
    assert compute_tool_retrieval_k(32768) == TIER_LARGE_K
    assert compute_tool_retrieval_k(131072) == TIER_LARGE_K


def test_compute_tool_retrieval_k_monotonic_across_tiers():
    """Retrieval width never shrinks as the window grows."""
    from src.context_budget import compute_tool_retrieval_k
    widths = [compute_tool_retrieval_k(c) for c in (
        1024, 4096, 8192, 16384, 32768, 65536, 131072, 1_000_000,
    )]
    assert widths == sorted(widths), widths


def test_is_small_context_window_flags_tight_windows_only():
    from src.context_budget import is_small_context_window
    # Zero / unknown → False (don't degrade unprobed endpoints).
    assert is_small_context_window(0) is False
    assert is_small_context_window(-1) is False
    # Under the tight threshold → True.
    assert is_small_context_window(2048) is True
    assert is_small_context_window(8191) is True
    # At or above → False.
    assert is_small_context_window(8192) is False
    assert is_small_context_window(131072) is False


def test_get_tools_for_query_honours_always_include_override():
    """The base argument must actually take effect — otherwise the tiering
    in agent_loop is dead code even though the imports succeed."""
    from src.tool_index import ALWAYS_AVAILABLE, ALWAYS_AVAILABLE_SMALL, ToolIndex
    idx = ToolIndex.__new__(ToolIndex)  # skip Chroma init; we only need the base path
    idx._KEYWORD_HINTS = {}
    idx._SCHEDULE_RE = __import__("re").compile(r"\bNEVERMATCHESx\b")
    idx._WEB_RE = __import__("re").compile(r"\bNEVERMATCHESx\b")
    idx.retrieve = lambda q, k: set()

    result = idx.get_tools_for_query("hello", k=4, always_include=ALWAYS_AVAILABLE_SMALL)
    # Only the small baseline should be present, not the full set.
    assert result == set(ALWAYS_AVAILABLE_SMALL)
    assert "manage_memory" not in result

    # And with the default arg the full baseline returns as before.
    result2 = idx.get_tools_for_query("hello", k=4)
    assert result2 == set(ALWAYS_AVAILABLE)
    assert "manage_memory" in result2
