"""
services/memory/graph.py

Entity/relationship graph extracted from chat messages.
Requirements: 3.1–3.8, 4.1–4.7
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.database import GraphEntity, GraphRelationship, SessionLocal

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = {"person", "project", "concept", "tool", "organisation"}
VALID_REL_TYPES = {
    "works-on", "related-to", "mentioned-with",
    "reports-to", "uses", "owns", "part-of",
}

_EXTRACTION_SYSTEM = """Extract entities and relationships from the text below.
Return ONLY a JSON object with two keys:
  "entities": [{"name": str, "type": "person|project|concept|tool|organisation"}, ...]
  "relationships": [{"source": str, "target": str, "type": "works-on|related-to|mentioned-with|reports-to|uses|owns|part-of"}, ...]
Use entity names exactly as they appear. If no entities, return empty lists.
Return valid JSON only — no markdown fences, no explanation."""


class GraphMemoryStore:
    """Async entity/relationship extraction and retrieval from SQLite."""

    def __init__(self, db_factory=None):
        self._db = db_factory or SessionLocal

    # ── Extraction ────────────────────────────────────────────────────────────

    def schedule_extraction(
        self,
        message: str,
        owner: str,
        endpoint_url: str,
        model: str,
        headers: Dict = None,
    ) -> None:
        """Fire-and-forget: schedule async LLM extraction for a chat message."""
        asyncio.create_task(
            self._extract_and_store(message, owner, endpoint_url, model, headers or {})
        )

    async def extract_and_store(
        self,
        message: str,
        owner: str,
        endpoint_url: str,
        model: str,
        headers: Dict = None,
    ) -> None:
        """Awaitable variant of schedule_extraction.

        Used by the chat post-response extraction queue so graph extraction
        runs sequentially with memory/skill extraction (issue #2927: side LLM
        calls must not overlap the main completion stream or the next turn).
        Exceptions are isolated inside _extract_and_store.
        """
        await self._extract_and_store(message, owner, endpoint_url, model, headers or {})

    async def _extract_and_store(
        self,
        message: str,
        owner: str,
        endpoint_url: str,
        model: str,
        headers: Dict,
    ) -> None:
        try:
            import httpx
            url = endpoint_url.rstrip("/")
            if "/v1" not in url:
                url += "/v1"
            url += "/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": _EXTRACTION_SYSTEM},
                    {"role": "user", "content": message},
                ],
                "temperature": 0.0,
                "max_tokens": 800,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await asyncio.wait_for(
                    client.post(url, json=payload, headers=headers),
                    timeout=30.0,
                )
                resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            parsed = self._parse_extraction(raw)
        except Exception as exc:
            logger.warning("Graph extraction failed for owner=%s: %s", owner, exc)
            return

        db = self._db()
        try:
            entity_map = self._upsert_entities(db, owner, parsed.get("entities", []))
            self._upsert_relationships(db, owner, entity_map, parsed.get("relationships", []))
            db.commit()
        except Exception as exc:
            logger.error("Graph DB write failed: %s", exc)
            db.rollback()
        finally:
            db.close()

    def _parse_extraction(self, raw: str) -> Dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"entities": [], "relationships": []}
        entities = []
        for e in (data.get("entities") or []):
            name = str(e.get("name", "")).strip()
            etype = str(e.get("type", "")).lower()
            if name and etype in VALID_ENTITY_TYPES:
                entities.append({"name": name, "type": etype})
        relationships = []
        for r in (data.get("relationships") or []):
            rtype = str(r.get("type", "")).lower()
            if rtype in VALID_REL_TYPES:
                relationships.append({
                    "source": str(r.get("source", "")).strip(),
                    "target": str(r.get("target", "")).strip(),
                    "type": rtype,
                })
        return {"entities": entities, "relationships": relationships}

    def _upsert_entities(self, db, owner: str, entities: List[Dict]) -> Dict[str, str]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        name_to_id: Dict[str, str] = {}
        for e in entities:
            name_norm = e["name"].lower().strip()
            row = (db.query(GraphEntity)
                   .filter_by(owner=owner, name_norm=name_norm, type=e["type"])
                   .first())
            if row:
                row.mention_count += 1
                row.last_seen_at = now
                name_to_id[e["name"]] = row.id
            else:
                eid = str(uuid.uuid4())
                row = GraphEntity(
                    id=eid, owner=owner,
                    name=e["name"], name_norm=name_norm, type=e["type"],
                    mention_count=1, first_seen_at=now, last_seen_at=now,
                )
                db.add(row)
                name_to_id[e["name"]] = eid
        return name_to_id

    def _upsert_relationships(self, db, owner: str, entity_map: Dict, rels: List[Dict]) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for r in rels:
            src_id = entity_map.get(r["source"])
            tgt_id = entity_map.get(r["target"])
            if not src_id or not tgt_id or src_id == tgt_id:
                continue
            row = (db.query(GraphRelationship)
                   .filter_by(owner=owner, source_id=src_id, target_id=tgt_id, type=r["type"])
                   .first())
            if row:
                row.strength += 1
            else:
                db.add(GraphRelationship(
                    id=str(uuid.uuid4()), owner=owner,
                    source_id=src_id, target_id=tgt_id,
                    type=r["type"], strength=1, created_at=now,
                ))

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_2hop_context(self, owner: str, query: str) -> str:
        """Find entities in query, return 2-hop subgraph as compact text."""
        db = self._db()
        try:
            query_lower = query.lower()
            seed_ids = [
                e.id for e in db.query(GraphEntity).filter_by(owner=owner).all()
                if e.name_norm in query_lower
            ]
            if not seed_ids:
                return ""
            return self._build_context_text(db, owner, seed_ids)
        finally:
            db.close()

    def _build_context_text(self, db, owner: str, seed_ids: List[str], max_hops: int = 2) -> str:
        visited = set(seed_ids)
        frontier = set(seed_ids)
        for _ in range(max_hops):
            next_frontier = set()
            for eid in frontier:
                for rel in (db.query(GraphRelationship)
                             .filter(GraphRelationship.owner == owner)
                             .filter(
                                 (GraphRelationship.source_id == eid) |
                                 (GraphRelationship.target_id == eid)
                             ).all()):
                    for nid in (rel.source_id, rel.target_id):
                        if nid not in visited:
                            visited.add(nid)
                            next_frontier.add(nid)
            frontier = next_frontier

        from sqlalchemy import text as _text
        entities = (db.query(GraphEntity)
                    .filter(GraphEntity.id.in_(visited), GraphEntity.owner == owner).all())
        if not entities:
            return ""
        lines = ["[Knowledge Graph Context]"]
        for e in entities:
            lines.append(f"- {e.name} ({e.type}, seen {e.mention_count}x)")
        return "\n".join(lines)

    def search_entities(self, owner: str, fragment: str = "") -> List[Dict]:
        db = self._db()
        try:
            q = db.query(GraphEntity).filter(GraphEntity.owner == owner)
            if fragment:
                q = q.filter(GraphEntity.name_norm.contains(fragment.lower()))
            return [self._entity_to_dict(e) for e in q.all()]
        finally:
            db.close()

    def get_entity_with_neighbours(self, owner: str, entity_id: str) -> Optional[Dict]:
        db = self._db()
        try:
            e = db.query(GraphEntity).filter_by(id=entity_id, owner=owner).first()
            if not e:
                return None
            rels = (db.query(GraphRelationship)
                    .filter(GraphRelationship.owner == owner)
                    .filter(
                        (GraphRelationship.source_id == entity_id) |
                        (GraphRelationship.target_id == entity_id)
                    ).all())
            result = self._entity_to_dict(e)
            result["relationships"] = [
                {"source_id": r.source_id, "target_id": r.target_id,
                 "type": r.type, "strength": r.strength}
                for r in rels
            ]
            return result
        finally:
            db.close()

    def export_graph(self, owner: str) -> Dict:
        db = self._db()
        try:
            entities = db.query(GraphEntity).filter_by(owner=owner).all()
            rels = db.query(GraphRelationship).filter_by(owner=owner).all()
            return {
                "nodes": [self._entity_to_dict(e) for e in entities],
                "edges": [
                    {"source_id": r.source_id, "target_id": r.target_id,
                     "type": r.type, "strength": r.strength}
                    for r in rels
                ],
            }
        finally:
            db.close()

    @staticmethod
    def _entity_to_dict(e: GraphEntity) -> Dict:
        return {
            "id": e.id, "name": e.name, "type": e.type,
            "mention_count": e.mention_count,
            "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
            "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
        }


# Module-level singleton
graph_store = GraphMemoryStore()
