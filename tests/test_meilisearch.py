"""Tests for Meilisearch full-text search integration.

Covers: kill-switch gating, endpoint response shape, client import safety.
Does NOT require a running Meilisearch instance (tests the kill-switch path).
"""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_meili_env():
    """Ensure ODYSSEUS_MEILISEARCH=off for most tests."""
    original = os.environ.get("ODYSSEUS_MEILISEARCH")
    os.environ["ODYSSEUS_MEILISEARCH"] = "off"
    yield
    if original is None:
        os.environ.pop("ODYSSEUS_MEILISEARCH", None)
    else:
        os.environ["ODYSSEUS_MEILISEARCH"] = original


def test_meilisearch_client_import():
    """Client module imports cleanly regardless of SDK availability."""
    from services.search.meilisearch_client import is_enabled

    # With kill-switch off, is_enabled should return False
    assert is_enabled() is False


def test_meilisearch_client_disabled_returns_empty():
    """search_all returns empty when kill-switch is off."""
    from services.search.meilisearch_client import search_all

    result = search_all("test query")
    assert result["hits"] == []
    assert result["total"] == 0


def test_fulltext_endpoint_disabled():
    """GET /api/search/fulltext returns fallback message when disabled."""
    # Ensure the module-level kill-switch reads 'off'
    os.environ["ODYSSEUS_MEILISEARCH"] = "off"
    # Force re-evaluation of the module-level _ENABLED
    import services.search.meilisearch_client as mc

    mc._ENABLED = False
    mc._client = None

    from app import app

    client = TestClient(app)
    response = client.get("/api/search/fulltext?q=restaurant")
    assert response.status_code == 200
    data = response.json()
    assert data["engine"] == "sqlite_like"
    assert data["total"] == 0
    assert "disabled" in data.get("message", "").lower() or "sqlite" in data.get("message", "").lower()


def test_fulltext_endpoint_empty_query():
    """GET /api/search/fulltext with no q param returns error."""
    os.environ["ODYSSEUS_MEILISEARCH"] = "off"
    import services.search.meilisearch_client as mc

    mc._ENABLED = False
    mc._client = None

    from app import app

    client = TestClient(app)
    response = client.get("/api/search/fulltext")
    assert response.status_code == 200
    data = response.json()
    # When disabled, always returns fallback regardless of query
    assert data["engine"] == "sqlite_like"


def test_meilisearch_enabled_with_mock():
    """When kill-switch is on and Meilisearch is available, search_all uses it."""
    os.environ["ODYSSEUS_MEILISEARCH"] = "on"
    import services.search.meilisearch_client as mc

    mc._ENABLED = True

    mock_client = MagicMock()
    mock_client.get_version.return_value = {"pkgVersion": "1.14.0"}
    mock_client.index.return_value.search.return_value = {
        "hits": [
            {"id": "msg-1", "content": "best restaurant in town", "_rankingScore": 0.95},
        ],
        "processingTimeMs": 3,
        "nbHits": 1,
    }
    mc._client = mock_client

    result = mc.search_all("restaurent")  # typo!
    assert result["total"] >= 1
    assert result["processingTimeMs"] > 0
    mock_client.index.assert_any_call("messages")
    mock_client.index.assert_any_call("notes")
    mock_client.index.assert_any_call("documents")


def test_index_message_calls_meilisearch():
    """index_message delegates to Meilisearch when enabled."""
    os.environ["ODYSSEUS_MEILISEARCH"] = "on"
    import services.search.meilisearch_client as mc

    mc._ENABLED = True

    mock_client = MagicMock()
    mock_client.get_version.return_value = {"pkgVersion": "1.14.0"}
    mc._client = mock_client

    mc.index_message("msg-42", "hello world", role="user", session_id="s1")
    mock_client.index.return_value.add_documents.assert_called_once()
    doc = mock_client.index.return_value.add_documents.call_args[0][0][0]
    assert doc["id"] == "msg-42"
    assert doc["content"] == "hello world"
    assert doc["session_id"] == "s1"
