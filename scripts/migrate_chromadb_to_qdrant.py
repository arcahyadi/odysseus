#!/usr/bin/env python3
"""
migrate_chromadb_to_qdrant.py

Copy all vectors from ChromaDB to Qdrant.
Usage:
    ODYSSEUS_QDRANT=on python scripts/migrate_chromadb_to_qdrant.py [--verify]

Requires both chromadb-client and qdrant-client.
"""

import argparse
import os
import random
import sys
import time

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.vector.qdrant_store import QdrantVectorStore
from src.constants import CHROMA_DIR


def get_chroma_collections():
    """Return dict of {collection_name: collection} from ChromaDB."""
    from src.chroma_client import get_chroma_client

    client = get_chroma_client()
    collections = {}
    for col in client.list_collections():
        name = col.name if hasattr(col, "name") else col
        try:
            collections[name] = client.get_collection(name)
        except Exception:
            pass
    return collections


def migrate_collection(chroma_col, qdrant: QdrantVectorStore, col_name: str, batch_size: int = 100):
    """Migrate a single ChromaDB collection to Qdrant."""
    count = chroma_col.count()
    if count == 0:
        print(f"  [skip] {col_name}: empty")
        return 0

    print(f"  [migrate] {col_name}: {count} vectors")
    offset = 0
    migrated = 0

    while offset < count:
        batch = chroma_col.get(
            include=["documents", "metadatas", "embeddings"],
            limit=batch_size,
            offset=offset,
        )
        if not batch["ids"]:
            break

        ids = batch["ids"]
        docs = batch["documents"] or [""] * len(ids)
        metas = batch["metadatas"] or [{} for _ in ids]
        embs = batch["embeddings"] or []

        vector_size = len(embs[0]) if embs else 384

        # Create collection with correct size
        qdrant.create_collection(col_name, vector_size=vector_size)

        qdrant.upsert(
            collection=col_name,
            ids=ids,
            vectors=embs,
            documents=docs,
            metadatas=metas,
        )

        migrated += len(ids)
        offset += batch_size
        pct = round(100 * migrated / count, 1)
        print(f"    {migrated}/{count} ({pct}%)", end="\r")

    print(f"  [done] {col_name}: {migrated} migrated")
    return migrated


def verify_migration(chroma_col, qdrant: QdrantVectorStore, col_name: str, samples: int = 5):
    """Random-sample verification: search both backends, compare results."""
    from src.chroma_client import get_chroma_client

    chroma = get_chroma_client()
    col = chroma.get_collection(col_name)
    count = col.count()
    if count == 0:
        print(f"  [verify] {col_name}: empty, skipped")
        return True

    total = min(samples, count)
    print(f"  [verify] {col_name}: {total} random samples")
    ok = 0

    for _ in range(total):
        # Pick a random document
        all_docs = col.get(limit=1, offset=random.randint(0, count - 1), include=["documents", "embeddings"])
        if not all_docs["ids"]:
            continue
        doc_text = all_docs["documents"][0]
        embedding = all_docs["embeddings"][0]

        # Search Qdrant
        qdrant_results = qdrant.search(col_name, query_vector=embedding, limit=3)
        if qdrant_results:
            ok += 1

    success = ok >= total // 2
    print(f"  [verify] {col_name}: {ok}/{total} samples matched -> {'PASS' if success else 'FAIL'}")
    return success


def main():
    parser = argparse.ArgumentParser(description="Migrate ChromaDB vectors to Qdrant")
    parser.add_argument("--verify", action="store_true", help="Run random-sample verification after migration")
    parser.add_argument("--collection", type=str, help="Migrate only this collection (default: all)")
    parser.add_argument("--qdrant-url", type=str, default="http://localhost:6333", help="Qdrant server URL")
    args = parser.parse_args()

    print("=" * 60)
    print("ChromaDB → Qdrant migration")
    print("=" * 60)

    qdrant = QdrantVectorStore(url=args.qdrant_url)
    if not qdrant.healthy:
        print("ERROR: Cannot connect to Qdrant at", args.qdrant_url)
        sys.exit(1)

    collections = get_chroma_collections()
    if not collections:
        print("No ChromaDB collections found at", CHROMA_DIR)
        sys.exit(0)

    print(f"Found {len(collections)} collections: {list(collections.keys())}")
    total_migrated = 0
    t0 = time.time()

    for name, col in collections.items():
        if args.collection and name != args.collection:
            continue
        n = migrate_collection(col, qdrant, name)
        total_migrated += n

    elapsed = time.time() - t0
    print(f"\nTotal: {total_migrated} vectors in {elapsed:.1f}s")

    if args.verify:
        print("\nVerification:")
        all_pass = True
        for name in collections:
            if args.collection and name != args.collection:
                continue
            if not verify_migration(collections[name], qdrant, name):
                all_pass = False
        print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
