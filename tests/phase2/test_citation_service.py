"""
tests/phase2/test_citation_service.py

Property and unit tests for CitationService (RAG + research citations,
metadata merge, references injection).
Requirements: 5.1-5.3 (phase 2)

# Feature: phase-2-knowledge-memory, Property: Citation Confidence Bounds
"""
import json

from hypothesis import given, settings, strategies as st

from services.citations.citation_service import CitationService, _normalise_score, _dedup_citations


def _svc():
    return CitationService()


# ── Property: confidence clamps to [0, 1] ────────────────────────────────────

@given(st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False))
@settings(max_examples=60)
def test_confidence_clamped_to_unit_interval(raw):
    score = _normalise_score(raw)
    assert 0.0 <= score <= 1.0


# ── RAG citations ────────────────────────────────────────────────────────────

def test_build_rag_citations_maps_fields():
    hits = [{
        "id": "c1",
        "document": "Odysseus is a self-hosted AI workspace. " * 30,
        "metadata": {"source_url": "https://docs.example.com/odysseus", "source_title": "Docs"},
        "distance": 0.2,
    }]
    out = _svc().build_rag_citations(hits)
    assert len(out) == 1
    c = out[0]
    assert c["chunk_id"] == "c1"
    assert c["source_url"] == "https://docs.example.com/odysseus"
    assert c["source_title"] == "Docs"
    assert abs(c["confidence_score"] - 0.8) < 1e-6
    assert len(c["snippet"]) <= 300


def test_build_rag_citations_metadata_fallback_keys():
    hits = [{"id": "x", "document": "text", "metadata": {"url": "https://u", "title": "T"}, "distance": 0.5}]
    out = _svc().build_rag_citations(hits)
    assert out[0]["source_url"] == "https://u"
    assert out[0]["source_title"] == "T"


def test_build_rag_citations_dedups_by_chunk():
    hits = [
        {"id": "c1", "document": "a", "metadata": {"url": "https://1"}, "distance": 0.5},
        {"id": "c1", "document": "a", "metadata": {"url": "https://1"}, "distance": 0.1},
    ]
    out = _svc().build_rag_citations(hits)
    assert len(out) == 1
    assert abs(out[0]["confidence_score"] - 0.9) < 1e-6


def test_dedup_keeps_highest_confidence():
    cit = [
        {"chunk_id": "a", "confidence_score": 0.4},
        {"chunk_id": "a", "confidence_score": 0.9},
    ]
    out = _dedup_citations(cit)
    assert len(out) == 1 and out[0]["confidence_score"] == 0.9


# ── Research citations ───────────────────────────────────────────────────────

def test_build_research_citations():
    sources = [
        {"url": "https://a.example.com", "title": "A", "content": "long content here", "confidence": 0.9},
        {"url": "https://b.example.com", "title": "B"},
    ]
    out = _svc().build_research_citations(sources)
    assert len(out) == 2
    assert out[0]["source_url"] == "https://a.example.com"
    assert out[1]["confidence_score"] == 1.0  # default when absent


# ── Metadata merge ───────────────────────────────────────────────────────────

def test_attach_to_message_metadata_merges_preserving_keys():
    existing = json.dumps({"rag_sources": [{"filename": "f"}]})
    merged = _svc().attach_to_message_metadata(existing, [{"chunk_id": "c"}])
    meta = json.loads(merged)
    assert meta["rag_sources"] == [{"filename": "f"}]
    assert meta["citations"] == [{"chunk_id": "c"}]


def test_attach_to_message_metadata_none_existing():
    merged = _svc().attach_to_message_metadata(None, [{"chunk_id": "c"}])
    assert json.loads(merged)["citations"] == [{"chunk_id": "c"}]


def test_attach_empty_citations_merges_empty_array():
    merged = json.loads(_svc().attach_to_message_metadata('{"k": 1}', []))
    assert merged == {"k": 1, "citations": []}


# ── References section ───────────────────────────────────────────────────────

def test_inject_references_section_appends():
    report = "Some report text."
    out = _svc().inject_references_section(report, [{"source_url": "https://u", "source_title": "T"}])
    assert "## References" in out
    assert "https://u" in out
    assert report in out


def test_inject_references_empty_citations_unchanged():
    assert _svc().inject_references_section("report", []) == "report"
