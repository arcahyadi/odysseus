"""
tests/phase2/test_graph.py

Property and unit tests for GraphMemoryStore: extraction parsing, retrieval
and the empty-store short-circuits.
Requirements: 3.1-3.8, 4.1-4.7 (phase 2)

# Feature: phase-2-knowledge-memory, Property: Extraction Parse Never Raises
"""
from types import SimpleNamespace

from services.memory.graph import GraphMemoryStore, VALID_ENTITY_TYPES


def _make_store(query_map):
    """query_map: {ModelClass: FakeQuery} served by the fake session."""
    fake_session = type("FS", (), {
        "query": lambda self, model: query_map[model],
        "close": lambda self: None,
        "commit": lambda self: None,
        "rollback": lambda self: None,
        "add": lambda self, *a, **k: None,
    })()
    return GraphMemoryStore(db_factory=lambda: fake_session)


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


# ── Extraction parsing ───────────────────────────────────────────────────────

def _store():
    return GraphMemoryStore(db_factory=lambda: None)


def test_parse_extraction_fenced_json():
    raw = '```json\n{"entities": [{"name": "Alice", "type": "person"}], "relationships": []}\n```'
    parsed = _store()._parse_extraction(raw)
    assert parsed["entities"] == [{"name": "Alice", "type": "person"}]
    assert parsed["relationships"] == []


def test_parse_extraction_bare_json():
    raw = '{"entities": [{"name": "Proj X", "type": "project"}], "relationships": [{"source": "Alice", "target": "Proj X", "type": "works-on"}]}'
    parsed = _store()._parse_extraction(raw)
    assert parsed["entities"][0]["name"] == "Proj X"
    assert parsed["relationships"][0]["type"] == "works-on"


def test_parse_extraction_filters_invalid_types():
    raw = '{"entities": [{"name": "Alice", "type": "person"}, {"name": "Bad", "type": "alien"}, {"name": ""}], "relationships": []}'
    parsed = _store()._parse_extraction(raw)
    assert len(parsed["entities"]) == 1
    assert parsed["entities"][0]["name"] == "Alice"


def test_parse_extraction_invalid_returns_empty():
    assert _store()._parse_extraction("this is not json {{") == {"entities": [], "relationships": []}
    assert _store()._parse_extraction("") == {"entities": [], "relationships": []}


# ── Retrieval ────────────────────────────────────────────────────────────────

def _seed_entity(name="Alice"):
    return SimpleNamespace(
        id="e1", name=name, name_norm=name.lower(),
        type="person", mention_count=3,
        first_seen_at=None, last_seen_at=None,
    )


def test_get_2hop_context_empty_when_no_seed_match():
    from core.database import GraphEntity, GraphRelationship
    store = _make_store({
        GraphEntity: FakeQuery([]),
        GraphRelationship: FakeQuery([]),
    })
    assert store.get_2hop_context("alice", "something unrelated") == ""


def test_get_2hop_context_returns_entity_context():
    from core.database import GraphEntity, GraphRelationship
    seed = _seed_entity()
    store = _make_store({
        GraphEntity: FakeQuery([seed]),
        GraphRelationship: FakeQuery([]),
    })
    text = store.get_2hop_context("alice", "talked with alice about plans")
    assert "[Knowledge Graph Context]" in text
    assert "Alice" in text
    assert "seen 3x" in text


def test_export_graph_shape():
    from core.database import GraphEntity, GraphRelationship
    seed = _seed_entity()
    rel = SimpleNamespace(
        source_id="e1", target_id="e2", type="related-to", strength=2,
    )
    store = _make_store({
        GraphEntity: FakeQuery([seed]),
        GraphRelationship: FakeQuery([rel]),
    })
    # export queries both tables — return the seed + rel regardless of filters.
    out = store.export_graph("alice")
    assert out["nodes"] == [{
        "id": "e1", "name": "Alice", "type": "person", "mention_count": 3,
        "first_seen_at": None, "last_seen_at": None,
    }]
    assert out["edges"] == [{"source_id": "e1", "target_id": "e2", "type": "related-to", "strength": 2}]


# ── Type taxonomy property ───────────────────────────────────────────────────

def test_entity_types_match_spec():
    assert VALID_ENTITY_TYPES == {"person", "project", "concept", "tool", "organisation"}
