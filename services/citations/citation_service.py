"""
services/citations/citation_service.py

Source citation tracking for RAG answers and research reports.
Requirements: 8.1–8.6, 10.1, 10.4
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

MAX_SNIPPET_LEN = 300


def _normalise_score(score: float) -> float:
    """Clamp any float to [0.0, 1.0]. Requirements: 8.3"""
    try:
        return max(0.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        return 0.0


def _dedup_citations(citations: List[Dict]) -> List[Dict]:
    """
    Keep only the highest-confidence citation per chunk_id / source_url.
    Requirements: 8.4
    """
    seen: Dict[str, Dict] = {}
    for c in citations:
        key = str(c.get("chunk_id") or c.get("source_url") or id(c))
        existing = seen.get(key)
        if existing is None or c["confidence_score"] > existing["confidence_score"]:
            seen[key] = c
    return list(seen.values())


class CitationService:

    def build_rag_citations(self, retrieval_results: List[Dict]) -> List[Dict]:
        """
        Build deduplicated citation list from vector retrieval results.
        Each hit: {id, document, metadata, distance}
        Requirements: 8.1, 8.5, 8.6
        """
        citations = []
        for hit in retrieval_results:
            meta = hit.get("metadata") or {}
            chunk_id = str(hit.get("id", ""))
            source_url = meta.get("source_url") or meta.get("url") or None
            source_title = (meta.get("title") or meta.get("source_title") or "Unknown source")
            snippet = str(hit.get("document") or "")[:MAX_SNIPPET_LEN]
            distance = hit.get("distance", 0.0)
            confidence = _normalise_score(1.0 - float(distance))
            citations.append({
                "chunk_id": chunk_id,
                "source_url": source_url,        # may be None per Req 8.6
                "source_title": source_title,
                "snippet": snippet,
                "confidence_score": round(confidence, 4),
            })
        return _dedup_citations(citations)

    def build_research_citations(self, sources: List[Dict]) -> List[Dict]:
        """
        Build deduplicated citation list from research pipeline sources.
        Each source: {url, title, content/snippet, confidence?}
        Requirements: 8.2
        """
        citations = []
        for i, source in enumerate(sources):
            url = source.get("url") or None
            title = source.get("title") or "Unknown source"
            snippet = str(source.get("content") or source.get("snippet") or "")[:MAX_SNIPPET_LEN]
            confidence = _normalise_score(float(source.get("confidence", 1.0)))
            citations.append({
                "chunk_id": f"research-{i}",
                "source_url": url,
                "source_title": title,
                "snippet": snippet,
                "confidence_score": round(confidence, 4),
            })
        return _dedup_citations(citations)

    def attach_to_message_metadata(
        self,
        existing_metadata: Optional[str],
        citations: List[Dict],
    ) -> str:
        """
        Merge citations into a message metadata JSON string.
        Preserves all existing metadata fields.
        Requirements: 8.5
        """
        meta: Dict[str, Any] = {}
        if existing_metadata:
            try:
                meta = json.loads(existing_metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        meta["citations"] = citations
        return json.dumps(meta, ensure_ascii=False)

    def inject_references_section(
        self,
        report_content: str,
        citations: List[Dict],
    ) -> str:
        """
        Append '## References' section to report_content.
        If citations is empty, return content unchanged (Req 10.4).
        Requirements: 10.1, 10.4
        """
        if not citations:
            return report_content
        lines = ["\n\n## References\n"]
        for i, c in enumerate(citations, start=1):
            url = c.get("source_url")
            title = c.get("source_title", "Unknown")
            snippet = c.get("snippet", "")
            if url:
                lines.append(f"[{i}] [{title}]({url})")
            else:
                lines.append(f"[{i}] {title}")
            if snippet:
                lines.append(f"    > {snippet[:200]}")
        return report_content + "\n".join(lines)


# Module-level singleton
citation_service = CitationService()
