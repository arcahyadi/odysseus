"""M3.2 — Trinité checkpoint: delegate semantic doc search to native VectorRAG.

The knowledge routes queried a phantom Graphify service (port 9750, never
running per STATE) for the semantic leg. The roadmap says: delegate semantic
doc search to the native VectorRAG instead of Graphify. These tests pin that
the semantic legs (``/graph/search`` and the checkpoint) use the native RAG and
that the dead Graphify references are gone.
"""

import asyncio


def run(coro):
    return asyncio.run(coro)


class _FakeRAG:
    def __init__(self, results):
        self._results = results
        self.calls = []

    def search(self, query, k=5):
        self.calls.append((query, k))
        return self._results


def test_graph_search_uses_native_rag(monkeypatch):
    import routes.knowledge_routes as kr

    fake = _FakeRAG([{"id": "d1", "content": "hello world"}])
    monkeypatch.setattr(kr, "get_rag_manager", lambda: fake)

    out = run(kr.search_graph_semantic("hello", limit=3))

    # Post-Graphify integration: search returns merged rag+graphify result
    assert "rag" in out
    assert out["rag"]["results"] == [{"id": "d1", "content": "hello world"}]
    assert fake.calls == [("hello", 3)]


def test_graph_search_native_unavailable_returns_empty(monkeypatch):
    import routes.knowledge_routes as kr

    monkeypatch.setattr(kr, "get_rag_manager", lambda: None)

    out = run(kr.search_graph_semantic("x"))

    assert "rag" in out
    assert out["rag"]["results"] == []
    assert "error" in out["rag"]


def test_checkpoint_semantic_leg_uses_native_rag(monkeypatch):
    import routes.knowledge_routes as kr

    fake = _FakeRAG([{"id": "d9", "content": "auth middleware"}])
    monkeypatch.setattr(kr, "get_rag_manager", lambda: fake)

    out = run(kr.trinite_checkpoint("auth flow"))

    assert "semantic" in out
    assert out["semantic"]["results"] == [{"id": "d9", "content": "auth middleware"}]
    # phantom Graphify leg is gone
    assert "graphify" not in out
    assert fake.calls and fake.calls[0][0] == "auth flow"


def test_status_reports_native_rag_not_graphify(monkeypatch):
    import routes.knowledge_routes as kr

    monkeypatch.setattr(kr, "get_rag_manager", lambda: object())  # available

    out = run(kr.knowledge_status())

    assert "graphify" not in out["trinite"]
    assert out["trinite"]["rag"] == "online"


def test_dead_graphify_references_removed():
    import routes.knowledge_routes as kr

    assert not hasattr(kr, "GRAPHIFY_URL")
    # the phantom Graphify indexing endpoint is gone
    assert not hasattr(kr, "index_project")
