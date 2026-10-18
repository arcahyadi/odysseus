#!/usr/bin/env python3
"""
Indexe le corpus Build Your Own X dans le RAG.
Usage: python scripts/index_byox.py
"""

import sys
from pathlib import Path

import httpx

BYOX_README_URL = "https://raw.githubusercontent.com/codecrafters-io/build-your-own-x/master/README.md"
OUTPUT_DIR = Path("rag/BYOX")


def fetch_and_save():
    print("Téléchargement du corpus BYOX...")
    try:
        resp = httpx.get(BYOX_README_URL, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        readme_path = OUTPUT_DIR / "README.md"
        readme_path.write_text(resp.text, encoding="utf-8")

        print(f"✓ BYOX corpus sauvegardé : {readme_path} ({len(resp.text)} chars)")
        print("  → Indexer dans RAG : POST /api/rag/index avec path=rag/BYOX/README.md")
        return True
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if fetch_and_save() else 1)
