"""Mem0 — intelligent fact extraction from conversations.

Wraps the ``mem0ai`` library (Apache 2.0) to auto-extract structured facts
(entities, preferences, decisions) from chat text.  Stores extracted facts in
the existing ChromaDB vector store so no new infrastructure is required.

Kill-switch: ``ODYSSEUS_MEM0=off`` disables this provider entirely.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from uuid import uuid4

from src.memory_provider import (
    MemoryProvider,
    MemoryRecord,
    MemorySearchHit,
)

logger = logging.getLogger(__name__)


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"on", "1", "true", "yes"}


def _env_falsy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"off", "0", "false", "no"}


class Mem0Provider(MemoryProvider):
    """Memory provider backed by Mem0 for structured fact extraction.

    Unlike the native provider, Mem0Provider *adds* to the native store
    (via a ``_native`` reference) and also keeps its own extracted-fact
    index so callers can query structured preferences and facts.
    """

    provider_id = "mem0"
    display_name = "Mem0 intelligent fact extraction"

    def __init__(
        self,
        native_provider: MemoryProvider | None = None,
        enabled: bool | None = None,
    ):
        import os as _os

        self._native = native_provider
        self.enabled = enabled if enabled is not None else not _env_falsy(_os.getenv("ODYSSEUS_MEM0"))
        self._memory: Any = None  # lazily initialised Memory instance
        self._facts: list[dict[str, Any]] = []  # in-memory extracted facts

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        if not self.enabled:
            return
        try:
            from mem0 import Memory  # type: ignore[import-untyped]

            # Build a config that uses ChromaDB for vector storage.
            # The config dict is passed directly to mem0ai; if the user
            # has MEM0_API_KEY set, mem0ai will use the hosted service
            # instead.
            config: dict[str, Any] = {}
            api_key = os.getenv("MEM0_API_KEY")
            if api_key:
                config["api_key"] = api_key
            else:
                # Local mode — use in-memory store for simplicity.
                # ChromaDB can be configured here when needed.
                config = {
                    "version": "v1.1",
                    "embedder": {
                        "provider": "fastembed",
                    },
                    "vector_store": {
                        "provider": "chroma",
                        "config": {
                            "collection_name": "odysseus_mem0_facts",
                        },
                    },
                }
            self._memory = Memory.from_config(config)
            logger.info("Mem0Provider initialized (mode=%s)", "hosted" if api_key else "local")
        except ImportError:
            logger.warning("mem0ai not installed — Mem0Provider disabled")
            self.enabled = False
        except Exception as exc:
            logger.warning("Mem0Provider init failed: %s", exc)
            self.enabled = False

    async def shutdown(self) -> None:
        self._memory = None

    # ── Fact extraction ──────────────────────────────────────────────────

    async def on_session_end(
        self,
        *,
        session_id: str | None = None,
        messages: list[Any] | None = None,
        outcome: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Auto-extract facts from a completed session's messages."""
        if not self.enabled or not self._memory or not messages:
            return

        user_id = (metadata or {}).get("user_id", "default")
        try:
            # mem0ai expects a list of message dicts with 'role' and 'content'
            mem0_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    mem0_messages.append(
                        {
                            "role": msg.get("role", "user"),
                            "content": msg.get("content", ""),
                        }
                    )
                elif hasattr(msg, "role") and hasattr(msg, "content"):
                    mem0_messages.append(
                        {
                            "role": getattr(msg, "role", "user"),
                            "content": getattr(msg, "content", ""),
                        }
                    )

            if not mem0_messages:
                return

            result = self._memory.add(
                mem0_messages,
                user_id=user_id,
                metadata={"session_id": session_id} if session_id else None,
            )

            # Store extracted facts locally for fast retrieval
            if isinstance(result, dict) and "results" in result:
                for fact in result["results"]:
                    self._facts.append(
                        {
                            "id": fact.get("id", str(uuid4())),
                            "text": fact.get("memory", ""),
                            "event": fact.get("event", "ADD"),
                            "user_id": user_id,
                            "session_id": session_id,
                            "timestamp": int(time.time()),
                            "score": fact.get("score", 1.0),
                        }
                    )

            logger.debug(
                "Mem0 extracted facts from session %s (user=%s): %d results",
                session_id,
                user_id,
                len(result.get("results", [])) if isinstance(result, dict) else 0,
            )
        except Exception as exc:
            logger.debug("Mem0 on_session_end failed: %s", exc)

    # ── Fact search ──────────────────────────────────────────────────────

    async def search_facts(self, query: str, user_id: str = "default") -> list[dict[str, Any]]:
        """Semantic search across extracted facts."""
        if not self.enabled or not self._memory:
            return []

        try:
            results = self._memory.search(query, user_id=user_id, limit=10)
            if isinstance(results, dict) and "results" in results:
                return [
                    {
                        "id": r.get("id", ""),
                        "text": r.get("memory", ""),
                        "score": r.get("score", 0.0),
                        "event": r.get("event", "ADD"),
                    }
                    for r in results["results"]
                ]
            return []
        except Exception as exc:
            logger.debug("Mem0 search_facts failed: %s", exc)
            return []

    async def get_user_profile(self, user_id: str = "default") -> dict[str, Any]:
        """Return consolidated user preferences and facts from Mem0."""
        if not self.enabled or not self._memory:
            return {"user_id": user_id, "facts": [], "count": 0}

        try:
            all_memories = self._memory.get_all(user_id=user_id)
            facts = []
            if isinstance(all_memories, dict) and "results" in all_memories:
                for r in all_memories["results"]:
                    facts.append(
                        {
                            "id": r.get("id", ""),
                            "text": r.get("memory", ""),
                            "event": r.get("event", "ADD"),
                            "score": r.get("score", 1.0),
                        }
                    )
            return {
                "user_id": user_id,
                "facts": facts,
                "count": len(facts),
            }
        except Exception as exc:
            logger.debug("Mem0 get_user_profile failed: %s", exc)
            return {"user_id": user_id, "facts": [], "count": 0}

    # ── MemoryProvider interface ─────────────────────────────────────────

    async def remember(
        self,
        text: str,
        *,
        owner: str | None = None,
        session_id: str | None = None,
        category: str = "fact",
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Store a fact via Mem0 and also delegate to native provider."""
        user_id = owner or "default"

        if self._memory:
            try:
                self._memory.add(
                    [{"role": "user", "content": text}],
                    user_id=user_id,
                    metadata={"session_id": session_id, "category": category},
                )
            except Exception as exc:
                logger.debug("Mem0 remember failed: %s", exc)

        # Also store in native provider for fallback
        if self._native:
            return await self._native.remember(
                text,
                owner=owner,
                session_id=session_id,
                category=category,
                source=source,
                metadata=metadata,
            )

        return MemoryRecord(
            id=str(uuid4()),
            text=text,
            timestamp=int(time.time()),
            category=category,
            source=source,
            owner=owner,
            session_id=session_id,
            metadata=dict(metadata) if metadata else {},
        )

    async def recall(
        self,
        query: str,
        *,
        owner: str | None = None,
        top_k: int = 5,
    ) -> list[MemorySearchHit]:
        """Search Mem0 facts, fallback to native if available."""
        user_id = owner or "default"
        facts = await self.search_facts(query, user_id)

        hits: list[MemorySearchHit] = []
        for fact in facts[:top_k]:
            hits.append(
                MemorySearchHit(
                    memory=MemoryRecord(
                        id=fact["id"],
                        text=fact["text"],
                        category="fact",
                        source="mem0",
                        owner=owner,
                    ),
                    provider_id=self.provider_id,
                    score=fact.get("score"),
                )
            )

        # Supplement with native provider results if under top_k
        if len(hits) < top_k and self._native:
            native_hits = await self._native.recall(query, owner=owner, top_k=top_k - len(hits))
            hits.extend(native_hits)

        return hits

    async def list_memories(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List facts from Mem0 plus native memories."""
        user_id = owner or "default"
        profile = await self.get_user_profile(user_id)
        records: list[MemoryRecord] = []

        for fact in profile.get("facts", [])[:limit]:
            records.append(
                MemoryRecord(
                    id=fact["id"],
                    text=fact["text"],
                    category="fact",
                    source="mem0",
                    owner=owner,
                )
            )

        # Supplement from native
        if self._native and len(records) < limit:
            native_records = await self._native.list_memories(owner=owner, limit=limit - len(records))
            records.extend(native_records)

        return records

    async def delete(self, memory_id: str, *, owner: str | None = None) -> bool:
        """Delete a fact from Mem0 and optionally from native."""
        if self._memory:
            try:
                self._memory.delete(memory_id)
                return True
            except Exception as exc:
                logger.debug("Mem0 delete failed: %s", exc)

        if self._native:
            return await self._native.delete(memory_id, owner=owner)

        return False

    # ── Tool schemas for agent integration ───────────────────────────────

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "mem0_search_facts",
                    "description": (
                        "Search structured facts extracted by Mem0 from past conversations. "
                        "Returns entities, preferences, decisions, and other personal details."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g. 'user preferences', 'contact info')",
                            },
                            "user_id": {
                                "type": "string",
                                "description": "User ID to scope the search",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mem0_get_profile",
                    "description": (
                        "Get the consolidated user profile with all extracted facts, preferences, and personal details."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User ID",
                            },
                        },
                        "required": [],
                    },
                },
            },
        ]

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "mem0_search_facts":
            return await self.search_facts(
                arguments["query"],
                user_id=arguments.get("user_id", "default"),
            )
        if name == "mem0_get_profile":
            return await self.get_user_profile(
                arguments.get("user_id", "default"),
            )
        return await super().handle_tool_call(name, arguments)
