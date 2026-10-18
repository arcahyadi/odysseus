"""RAG reindex pipeline — re-embeds all documents in ChromaDB.

Run standalone:   python -m services.pipelines.rag_pipeline
Scheduled via:    rag_reindex_flow.serve(name="rag-reindex", cron="0 2 * * *")
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── Kill-switch gate ──────────────────────────────────────────────────────
PREFECT_ENABLED = os.getenv("ODYSSEUS_PREFECT", "off").lower() in ("on", "1", "true")


def _lazy_import():
    """Import prefect decorators; raise a clear error if missing."""
    try:
        from prefect import flow as _flow
        from prefect import task as _task

        return _flow, _task
    except ImportError:
        raise ImportError(
            "Prefect is not installed. Install it with: pip install prefect  "
            "(see requirements-optional.txt). Set ODYSSEUS_PREFECT=off to "
            "use the built-in task_scheduler instead."
        )


# ── Tasks ─────────────────────────────────────────────────────────────────


def _reindex_documents_task():
    """Core reindex logic — works with or without Prefect."""
    from src.chroma_client import get_chroma_client

    logger.info("RAG reindex: connecting to ChromaDB …")
    client = get_chroma_client()

    # List all collections and trigger a re-embed of stale documents.
    # VectorRAG exposes a `reindex_collection` helper; fall back to a
    # manual scan if unavailable.
    collections = _get_collection_names(client)
    total_reindexed = 0

    for name in collections:
        try:
            count = _reindex_collection(client, name)
            total_reindexed += count
            logger.info("RAG reindex: %s — %d documents updated", name, count)
        except Exception:
            logger.exception("RAG reindex failed for collection %s", name)

    logger.info("RAG reindex complete — %d total documents updated", total_reindexed)
    return total_reindexed


def _get_collection_names(client) -> list[str]:
    """Return all collection names from ChromaDB."""
    try:
        collections = client.list_collections()
        return [c.name if hasattr(c, "name") else str(c) for c in collections]
    except Exception:
        logger.warning("Could not list ChromaDB collections")
        return []


def _reindex_collection(client, name: str) -> int:
    """Re-embed documents in a single collection. Returns count updated."""
    try:
        collection = client.get_collection(name)
    except Exception:
        return 0

    # Get all documents — check if any lack embeddings
    try:
        results = collection.get(include=["embeddings", "metadatas"])
    except Exception:
        return 0

    ids = results.get("ids", [])
    embeddings = results.get("embeddings", [])
    documents = results.get("documents", [])

    # Find docs without embeddings (need re-embedding)
    stale = []
    for i, emb in enumerate(embeddings):
        if emb is None or (hasattr(emb, "__len__") and len(emb) == 0):
            stale.append(i)

    if not stale:
        return 0

    # Re-embed stale documents using the embedding lane
    from src.embedding_lanes import get_embedding_lanes

    lanes = get_embedding_lanes()
    if not lanes:
        logger.warning("No embedding lanes available — skipping reindex for %s", name)
        return 0

    lane = lanes[0]  # use primary lane
    docs_to_embed = [documents[i] for i in stale if i < len(documents)]
    ids_to_embed = [ids[i] for i in stale if i < len(ids)]

    if not docs_to_embed:
        return 0

    try:
        new_embeddings = lane.embed_documents(docs_to_embed)
        collection.update(
            ids=ids_to_embed,
            embeddings=new_embeddings,
        )
        return len(ids_to_embed)
    except Exception:
        logger.exception("Embedding update failed for collection %s", name)
        return 0


# ── Flow (Prefect decorators) ────────────────────────────────────────────


def _create_flow():
    flow, task = _lazy_import()

    @task(retries=3, cache_key_fn=lambda *a: "rag-reindex")
    def reindex_documents_task():
        """Reindex all documents in ChromaDB (Prefect task)."""
        return _reindex_documents_task()

    @flow(name="rag-reindex", log_prints=True)
    def rag_reindex_flow():
        """Reindex RAG documents — Prefect flow entry point."""
        reindex_documents_task()

    return rag_reindex_flow


# Lazy singleton — only created when Prefect is active
_rag_reindex_flow = None


def get_rag_reindex_flow():
    """Return the Prefect flow object (or None if Prefect is disabled)."""
    global _rag_reindex_flow
    if not PREFECT_ENABLED:
        return None
    if _rag_reindex_flow is None:
        _rag_reindex_flow = _create_flow()
    return _rag_reindex_flow


# ── CLI entry point ──────────────────────────────────────────────────────


def main():
    """Run the reindex directly (no Prefect server needed)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("Running RAG reindex (standalone) …")
    count = _reindex_documents_task()
    logger.info("Done — %d documents updated.", count)
    return count


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
