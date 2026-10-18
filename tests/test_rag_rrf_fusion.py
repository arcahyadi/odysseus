"""M3.2 — repair the orphan RRF hybrid_search.

The shipped hybrid_search used a reflection hack that scanned module-level
functions for a `search`; the real search is a class *method*, so the loop
never found it, always fell to vector_results=[], and returned [] every time
(dead code). This repairs it to a pure, testable fusion: the caller passes the
ranked vector results in, and hybrid_search fuses them with BM25 (over the same
docs) via Reciprocal Rank Fusion. These tests pin the new contract.
"""

import pytest

from src.rag_vector import _rrf_score, hybrid_search


def _docs():
    return [
        {"id": "a", "content": "python programming language guide"},
        {"id": "b", "content": "docker container orchestration platform"},
        {"id": "c", "content": "python web framework tutorial"},
    ]


def test_empty_vector_results_returns_empty():
    assert hybrid_search("python", []) == []


def test_returns_same_doc_objects_capped_at_top_k():
    docs = _docs()
    out = hybrid_search("python framework", docs, top_k=2, alpha=0.5)
    assert len(out) <= 2
    # every returned object is one of the inputs (identity preserved)
    for r in out:
        assert any(r is d for d in docs)


def test_alpha_one_is_pure_vector_order():
    # alpha=1.0 → BM25 term is zero → fused order == input vector order.
    docs = _docs()
    out = hybrid_search("python framework", docs, top_k=3, alpha=1.0)
    assert [r["id"] for r in out] == ["a", "b", "c"]


def test_rrf_boosts_doc_matching_keywords():
    pytest.importorskip("rank_bm25")
    # Query terms hit 'a' and 'c' (python / framework), never 'b'.
    # Under pure vector order b sits at rank 1; RRF fusion with BM25 must push
    # the keyword-matching 'c' above the non-matching 'b'.
    docs = _docs()
    out = hybrid_search("python framework", docs, top_k=3, alpha=0.5)
    ids = [r["id"] for r in out]
    assert set(ids) == {"a", "b", "c"}
    assert ids.index("c") < ids.index("b")


def test_rrf_score_monotonic_decreasing():
    assert _rrf_score(0) > _rrf_score(1) > _rrf_score(5)


# ─── Step 2: live-search wiring behind the ODYSSEUS_RRF_FUSION kill-switch ──────


def test_rrf_fusion_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_RRF_FUSION", raising=False)
    from src.rag_vector import _rrf_fusion_enabled

    assert _rrf_fusion_enabled() is False


def test_rrf_fusion_enabled_by_env(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_RRF_FUSION", "on")
    from src.rag_vector import _rrf_fusion_enabled

    assert _rrf_fusion_enabled() is True


def _candidates():
    return [
        {"id": "a", "similarity": 0.9, "vector_similarity": 0.9, "content": "python programming language guide"},
        {"id": "b", "similarity": 0.8, "vector_similarity": 0.8, "content": "docker container orchestration platform"},
        {"id": "c", "similarity": 0.7, "vector_similarity": 0.7, "content": "python web framework tutorial"},
    ]


def test_rank_candidates_default_is_naive_similarity_order(monkeypatch):
    # Kill-switch OFF → identical to the shipped 0.7/0.3 blend order.
    monkeypatch.delenv("ODYSSEUS_RRF_FUSION", raising=False)
    from src.rag_vector import _rank_candidates

    out = _rank_candidates("python framework", _candidates(), k=3)
    assert [c["id"] for c in out] == ["a", "b", "c"]


def test_rank_candidates_rrf_reorders_when_enabled(monkeypatch):
    pytest.importorskip("rank_bm25")
    monkeypatch.setenv("ODYSSEUS_RRF_FUSION", "on")
    from src.rag_vector import _rank_candidates

    out = _rank_candidates("python framework", _candidates(), k=3)
    ids = [c["id"] for c in out]
    assert set(ids) == {"a", "b", "c"}
    # 'c' matches both query terms; RRF must lift it above non-matching 'b'
    # even though its naive similarity (0.7) is lowest.
    assert ids.index("c") < ids.index("b")
