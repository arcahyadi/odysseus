"""Contract test for the Trinité status endpoint consumed by the knowledge panel."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.knowledge_routes import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_status_returns_trinite_three_legs():
    resp = _client().get("/api/knowledge/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "trinite" in body
    legs = body["trinite"]
    # The three legs the frontend renders.
    for leg in ("cbm", "rag", "obsidian"):
        assert leg in legs, f"missing leg: {leg}"
    # cbm/rag are health strings; obsidian is a descriptive string (never a bare "online").
    assert legs["cbm"] in ("online", "offline")
    assert legs["rag"] in ("online", "offline")
    assert isinstance(legs["obsidian"], str) and legs["obsidian"] != "online"
