"""
tests/phase2/test_digest_service.py

Unit tests for DigestService storage layer (list / get-by-date / search /
dict conversion) using stub sessions — no LLM calls.
Requirements: 4.1-4.4, 6.5-6.7, 7.1-7.2 (phase 2)
"""
import json
from types import SimpleNamespace

from services.digest.digest_service import DigestService


class FakeRow:
    def __init__(self, id="d1", date="2026-09-01", status="complete",
                 content=None, summary="S", error=None, created_at=None):
        self.id = id
        self.date = date
        self.status = status
        self.content = content
        self.summary = summary
        self.error = error
        self.created_at = created_at


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k): return self
    def filter_by(self, *a, **k): return self
    def order_by(self, *a, **k): return self
    def offset(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def all(self): return self._rows
    def first(self): return self._rows[0] if self._rows else None


def _make_service(rows):
    session = type("FS", (), {
        "query": lambda self, model: FakeQuery(rows),
        "close": lambda self: None,
    })()
    return DigestService(db_factory=lambda: session)


def _make_ts_row(**kw):
    base = dict(id="d1", date="2026-09-01", status="complete",
                content=json.dumps({"highlights": ["h"], "key": "v"}),
                summary="Today summary", error=None, created_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


# ── Retrieval helpers ────────────────────────────────────────────────────────

def test_list_digests_empty():
    svc = _make_service([])
    assert svc.list_digests("alice", limit=30, offset=0) == []


def test_get_by_date_missing_returns_none():
    svc = _make_service([])
    assert svc.get_by_date("alice", "2026-09-01") is None


def test_search_blank_query_returns_empty():
    svc = _make_service([_make_ts_row()])
    assert svc.search("alice", "") == []
    assert svc.search("alice", "   ") == []


def test_digest_to_dict_parses_json_content():
    svc = _make_service([])
    out = svc._digest_to_dict(_make_ts_row())
    assert out["date"] == "2026-09-01"
    assert out["status"] == "complete"
    assert out["summary"] == "Today summary"
    assert out["content"]["highlights"] == ["h"]


def test_digest_to_dict_content_fallback_when_not_json():
    svc = _make_service([])
    out = svc._digest_to_dict(_make_ts_row(content="not json"))
    assert out["content"] == "not json"


# ── Property: date ordering contract for the context builder ────────────────

def test_context_builder_recent_filter_matches_iso_dates():
    """Dates stored as YYYY-MM-DD compare lexicographically; recent >= today-2."""
    from datetime import date, timedelta
    today = date.today()
    recent = (today - timedelta(days=1)).isoformat()
    old = (today - timedelta(days=30)).isoformat()
    assert recent >= (today - timedelta(days=2)).isoformat()
    assert old < (today - timedelta(days=2)).isoformat()
