"""
qdrant_store.py

Production-grade Qdrant vector store (Rust backend, Apache 2.0).
Drop-in replacement for ChromaDB with payload filtering, quantization,
and HA consensus.  Opt-in via ODYSSEUS_QDRANT=on / VECTOR_BACKEND=qdrant.

API mirrors the subset of ChromaDB used by rag_vector.py and
memory_vector.py so integration is a thin adapter.
"""

import logging
import os
from typing import Any

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _qdrant_enabled() -> bool:
    """Kill-switch check: ODYSSEUS_QDRANT env var."""
    val = os.getenv("ODYSSEUS_QDRANT", "off").strip().lower()
    return val in {"on", "1", "true", "yes"}


def _collection_suffix(name: str, suffix: str) -> str:
    """Same suffix convention as embedding_lanes.collection_name."""
    return f"{name}__{suffix}" if suffix else name


# ---------------------------------------------------------------------------
# Core store
# ---------------------------------------------------------------------------


class QdrantVectorStore:
    """Async-compatible Qdrant vector store.

    Supports the same CRUD surface the existing ChromaDB code uses:
    create / upsert / query / search / delete / count / list_collections.
    """

    def __init__(self, url: str | None = None):
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed. Install with: pip install qdrant-client")
        if url is None:
            url = os.getenv("VECTOR_QDRANT_URL", "http://localhost:6333")
        self.url = url
        self.client = QdrantClient(url=url)
        self._healthy = True

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @property
    def healthy(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(
        self,
        name: str,
        vector_size: int = 384,
        distance: Distance = Distance.COSINE,
    ) -> bool:
        """Create a collection if it doesn't exist."""
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if name in existing:
                logger.debug("Qdrant collection '%s' already exists", name)
                return True
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=distance),
            )
            logger.info("Qdrant collection '%s' created (dim=%d)", name, vector_size)
            return True
        except Exception as e:
            logger.error("create_collection '%s' failed: %s", name, e)
            return False

    def delete_collection(self, name: str) -> bool:
        try:
            self.client.delete_collection(collection_name=name)
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        try:
            return [c.name for c in self.client.get_collections().collections]
        except Exception:
            return []

    def collection_count(self, name: str) -> int:
        try:
            info = self.client.get_collection(collection_name=name)
            return info.points_count or 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Upsert (single + batch)
    # ------------------------------------------------------------------

    def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Upsert points into a collection.

        Args:
            collection: Collection name.
            ids: Point IDs (strings → int hash internally).
            vectors: Embedding vectors.
            documents: Original text.
            metadatas: Payload dicts (stored as Qdrant payload).
        """
        try:
            points = []
            for i, (pid, vec, doc) in enumerate(zip(ids, vectors, documents, strict=False)):
                payload = {"document": doc}
                if metadatas and i < len(metadatas):
                    payload.update(metadatas[i])
                # Qdrant point IDs must be int or UUID — hash string IDs.
                int_id = abs(hash(pid)) % (2**63)
                points.append(PointStruct(id=int_id, vector=vec, payload=payload))

            # Batch in chunks of 100
            for start in range(0, len(points), 100):
                self.client.upsert(
                    collection_name=collection,
                    points=points[start : start + 100],
                )
            return True
        except Exception as e:
            logger.error("qdrant upsert failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for nearest neighbours.

        Returns list of dicts matching the ChromaDB result shape:
        {"id": str, "document": str, "metadata": dict, "distance": float}
        """
        try:
            query_filter = None
            if where:
                conditions = []
                for key, value in where.items():
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                query_filter = Filter(must=conditions)

            results = self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
            )
            out = []
            for hit in results:
                doc = hit.payload.get("document", "")
                meta = {k: v for k, v in hit.payload.items() if k != "document"}
                out.append(
                    {
                        "id": str(hit.id),
                        "document": doc,
                        "metadata": meta,
                        "distance": round(1.0 - hit.score, 4),  # convert similarity→distance
                        "similarity": round(hit.score, 4),
                    }
                )
            return out
        except Exception as e:
            logger.error("qdrant search failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Get / delete by ID
    # ------------------------------------------------------------------

    def get_by_ids(self, collection: str, ids: list[str]) -> dict[str, list]:
        """Retrieve points by ID.  Returns {"ids": [...], "documents": [...], "metadatas": [...]}."""
        try:
            int_ids = [abs(hash(i)) % (2**63) for i in ids]
            points = self.client.retrieve(collection_name=collection, ids=int_ids, with_payload=True)
            id_list = []
            doc_list = []
            meta_list = []
            for pt in points:
                id_list.append(str(ids[int_ids.index(pt.id)]))
                doc_list.append(pt.payload.get("document", ""))
                meta_list.append({k: v for k, v in pt.payload.items() if k != "document"})
            return {"ids": id_list, "documents": doc_list, "metadatas": meta_list}
        except Exception as e:
            logger.error("qdrant get_by_ids failed: %s", e)
            return {"ids": [], "documents": [], "metadatas": []}

    def get_all(self, collection: str, where: dict[str, Any] | None = None) -> dict[str, list]:
        """Get all points (optionally filtered).  Used for keyword fallback."""
        try:
            scroll_filter = None
            if where:
                conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in where.items()]
                scroll_filter = Filter(must=conditions)

            points, _ = self.client.scroll(
                collection_name=collection,
                limit=10000,
                scroll_filter=scroll_filter,
                with_payload=True,
            )
            ids = []
            docs = []
            metas = []
            for pt in points:
                ids.append(str(pt.id))
                docs.append(pt.payload.get("document", ""))
                metas.append({k: v for k, v in pt.payload.items() if k != "document"})
            return {"ids": ids, "documents": docs, "metadatas": metas}
        except Exception as e:
            logger.error("qdrant get_all failed: %s", e)
            return {"ids": [], "documents": [], "metadatas": []}

    def delete_by_ids(self, collection: str, ids: list[str]) -> bool:
        try:
            int_ids = [abs(hash(i)) % (2**63) for i in ids]
            self.client.delete(
                collection_name=collection,
                points_selector=int_ids,
            )
            return True
        except Exception as e:
            logger.error("qdrant delete failed: %s", e)
            return False

    def update_metadata(self, collection: str, ids: list[str], metadatas: list[dict[str, Any]]) -> bool:
        """Update payload (metadata) for existing points."""
        try:
            int_ids = [abs(hash(i)) % (2**63) for i in ids]
            for int_id, meta in zip(int_ids, metadatas, strict=False):
                self.client.set_payload(
                    collection_name=collection,
                    payload=meta,
                    points=[int_id],
                )
            return True
        except Exception as e:
            logger.error("qdrant update_metadata failed: %s", e)
            return False
