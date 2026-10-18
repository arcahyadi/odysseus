"""Meilisearch full-text search client — async, typo-tolerant, faceted.

Kill-switch: ODYSSEUS_MEILISEARCH=off (default) → client disabled,
search routes fall back to SQLite LIKE. When "on", full-text search
across messages, notes, and documents uses Meilisearch.

Indices:
  - messages: chat messages (role, content, session_id, timestamp)
  - notes: user notes (title, content, tags, timestamp)
  - documents: uploaded documents (title, content, filename, timestamp)
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── Kill-switch ──────────────────────────────────────────────────
_ENABLED = os.getenv("ODYSSEUS_MEILISEARCH", "off").lower() in ("on", "1", "true")
_HOST = os.getenv("MEILI_HOST", "meilisearch")
_PORT = os.getenv("MEILI_PORT", "7700")
_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "odysseus-meili-key")
_URL = f"http://{_HOST}:{_PORT}"

# Lazy singleton — only imported when needed
_client = None


def _get_client():
    """Return a Meilisearch client or None if disabled / unavailable."""
    if not _ENABLED:
        return None
    global _client
    if _client is not None:
        return _client
    try:
        import meilisearch

        _client = meilisearch.Client(_URL, _MASTER_KEY)
        # Verify connectivity
        _client.get_version()
        logger.info(f"Meilisearch connected at {_URL}")
    except ImportError:
        logger.warning("meilisearch Python SDK not installed — pip install meilisearch")
        return None
    except Exception as e:
        logger.warning(f"Meilisearch not reachable at {_URL}: {e}")
        _client = None
    return _client


def is_enabled() -> bool:
    """Check if Meilisearch is enabled AND reachable."""
    return _get_client() is not None


# ── Index setup ──────────────────────────────────────────────────

_INDEX_SETTINGS: dict[str, dict] = {
    "messages": {
        "primaryKey": "id",
        "searchableAttributes": ["content", "role"],
        "filterableAttributes": ["session_id", "role", "timestamp"],
        "sortableAttributes": ["timestamp"],
        "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypos": 2, "twoTypos": 5}},
    },
    "notes": {
        "primaryKey": "id",
        "searchableAttributes": ["title", "content", "tags"],
        "filterableAttributes": ["tags", "timestamp"],
        "sortableAttributes": ["timestamp"],
        "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypos": 2, "twoTypos": 5}},
    },
    "documents": {
        "primaryKey": "id",
        "searchableAttributes": ["title", "content", "filename"],
        "filterableAttributes": ["filename", "timestamp"],
        "sortableAttributes": ["timestamp"],
        "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypos": 2, "twoTypos": 5}},
    },
}


def ensure_indices():
    """Create/update indices with proper settings. Called on first index."""
    client = _get_client()
    if client is None:
        return
    for name, settings in _INDEX_SETTINGS.items():
        try:
            index = client.index(name)
            index.update_settings(settings)
            logger.debug(f"Meilisearch index '{name}' configured")
        except Exception as e:
            logger.warning(f"Failed to configure index '{name}': {e}")


# ── Indexing methods ─────────────────────────────────────────────


def index_message(
    message_id: str,
    content: str,
    role: str = "user",
    session_id: str = "",
    timestamp: str | None = None,
):
    """Index a chat message into Meilisearch."""
    client = _get_client()
    if client is None:
        return
    ts = timestamp or datetime.now(UTC).isoformat()
    doc = {
        "id": message_id,
        "content": content,
        "role": role,
        "session_id": session_id,
        "timestamp": ts,
    }
    try:
        client.index("messages").add_documents([doc])
    except Exception as e:
        logger.warning(f"Meilisearch index_message failed: {e}")


def index_note(
    note_id: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    timestamp: str | None = None,
):
    """Index a note into Meilisearch."""
    client = _get_client()
    if client is None:
        return
    ts = timestamp or datetime.now(UTC).isoformat()
    doc = {
        "id": note_id,
        "title": title,
        "content": content,
        "tags": tags or [],
        "timestamp": ts,
    }
    try:
        client.index("notes").add_documents([doc])
    except Exception as e:
        logger.warning(f"Meilisearch index_note failed: {e}")


def index_document(
    doc_id: str,
    title: str,
    content: str,
    filename: str = "",
    timestamp: str | None = None,
):
    """Index an uploaded document into Meilisearch."""
    client = _get_client()
    if client is None:
        return
    ts = timestamp or datetime.now(UTC).isoformat()
    doc = {
        "id": doc_id,
        "title": title,
        "content": content,
        "filename": filename,
        "timestamp": ts,
    }
    try:
        client.index("documents").add_documents([doc])
    except Exception as e:
        logger.warning(f"Meilisearch index_document failed: {e}")


def delete_message(message_id: str):
    """Remove a message from the index."""
    client = _get_client()
    if client is None:
        return
    try:
        client.index("messages").delete_document(message_id)
    except Exception as e:
        logger.warning(f"Meilisearch delete_message failed: {e}")


def delete_note(note_id: str):
    """Remove a note from the index."""
    client = _get_client()
    if client is None:
        return
    try:
        client.index("notes").delete_document(note_id)
    except Exception as e:
        logger.warning(f"Meilisearch delete_note failed: {e}")


def delete_document(doc_id: str):
    """Remove a document from the index."""
    client = _get_client()
    if client is None:
        return
    try:
        client.index("documents").delete_document(doc_id)
    except Exception as e:
        logger.warning(f"Meilisearch delete_document failed: {e}")


# ── Search ───────────────────────────────────────────────────────


def search_all(
    query: str,
    type_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search across all indices with typo tolerance.

    Args:
        query: Search query (typo-tolerant by default)
        type_filter: Optional filter — "message", "note", or "document"
        limit: Max results per index
        offset: Pagination offset

    Returns:
        {
            "query": str,
            "hits": [...],
            "total": int,
            "processingTimeMs": int,
            "facets": {...}
        }
    """
    client = _get_client()
    if client is None:
        return {"query": query, "hits": [], "total": 0, "processingTimeMs": 0, "error": "Meilisearch not available"}

    indices_to_search = ["messages", "notes", "documents"]
    if type_filter == "message":
        indices_to_search = ["messages"]
    elif type_filter == "note":
        indices_to_search = ["notes"]
    elif type_filter == "document":
        indices_to_search = ["documents"]

    all_hits = []
    total_time = 0

    for idx_name in indices_to_search:
        try:
            result = client.index(idx_name).search(
                query,
                {
                    "limit": limit,
                    "offset": offset,
                    "attributesToHighlight": ["content", "title"],
                    "highlightPreTag": "<mark>",
                    "highlightPostTag": "</mark>",
                },
            )
            hits = result.get("hits", [])
            # Tag each hit with its source type
            for hit in hits:
                hit["_type"] = idx_name.rstrip("s")  # messages→message, notes→note, documents→document
                hit["_index"] = idx_name
            all_hits.extend(hits)
            total_time += result.get("processingTimeMs", 0)
        except Exception as e:
            logger.warning(f"Meilisearch search on '{idx_name}' failed: {e}")

    # Sort by relevance (Meilisearch returns ranked results per index)
    # We do a simple merge — interleaving by processing order is fine
    # for a first pass; true cross-index ranking would require a hybrid approach.
    all_hits.sort(key=lambda h: h.get("_rankingScore", 0), reverse=True)

    return {
        "query": query,
        "hits": all_hits[:limit],
        "total": len(all_hits),
        "processingTimeMs": total_time,
    }
