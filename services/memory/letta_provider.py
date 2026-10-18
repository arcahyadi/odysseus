"""Letta/MemGPT memory provider — virtual context management for small models.

Solves the prompt/context bloat problem: agents with 4k/8k/16k token windows
can't use tools + memory + docs simultaneously. Letta pages data in/out of
working memory automatically, keeping context within budget while maintaining
access to unlimited archival memory.

Gate: ODYSSEUS_LETTA=on + docker compose --profile memory up letta
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from src.memory_provider import (
    MemoryProvider,
    MemoryRecord,
    MemorySearchHit,
)

logger = logging.getLogger(__name__)


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"on", "1", "true", "yes"}


class LettaMemoryProvider(MemoryProvider):
    """Memory provider backed by Letta (formerly MemGPT).

    Letta manages what stays in context vs archival memory. Agents get
    unlimited effective context via automatic paging — critical for small
    models (4k/8k/16k) that can't fit tools + memory + docs.

    Architecture:
        - Working memory: in-context, managed by Letta's virtual context
        - Archival memory: database-backed, searched on demand
        - Self-editing: agent can modify its own memory blocks
    """

    provider_id = "letta"
    display_name = "Letta virtual context management"

    def __init__(
        self,
        base_url: str | None = None,
        enabled: bool | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("LETTA_URL") or "http://localhost:8283").rstrip("/")
        self.enabled = enabled if enabled is not None else _env_truthy(os.getenv("ODYSSEUS_LETTA"))
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """Lazy-init the Letta client."""
        if self._client is None:
            try:
                from letta import create_client

                self._client = create_client(base_url=self.base_url)
            except ImportError:
                logger.warning("letta-client not installed — pip install letta-client")
                raise
        return self._client

    # ── Core MemoryProvider interface ────────────────────────────────────

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
        """Store a memory in Letta archival memory."""
        import httpx

        payload = {
            "text": text,
            "metadata": {
                "category": category,
                "source": source,
                **(metadata or {}),
            },
        }
        if owner:
            payload["metadata"]["owner"] = owner
        if session_id:
            payload["metadata"]["session_id"] = session_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/archival/memory",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("letta remember failed: %s", exc)
            return MemoryRecord(
                id=f"letta-fallback-{int(time.time())}",
                text=text,
                category=category,
                source=source,
                owner=owner,
                session_id=session_id,
                metadata=dict(metadata) if metadata else {},
            )

        return MemoryRecord(
            id=data.get("id", ""),
            text=text,
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
        """Search Letta archival memory."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/archival/memory/search",
                    json={"query": query, "page": 1},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.debug("letta recall failed: %s", exc)
            return []

        hits: list[MemorySearchHit] = []
        for item in (data.get("results") or data.get("archival_memory") or [])[:top_k]:
            content = item.get("content") or item.get("text") or ""
            meta = item.get("metadata") or {}
            if owner and meta.get("owner") and meta["owner"] != owner:
                continue
            hits.append(
                MemorySearchHit(
                    memory=MemoryRecord(
                        id=item.get("id", ""),
                        text=content,
                        category=meta.get("category", "fact"),
                        source=meta.get("source", "letta"),
                        owner=meta.get("owner"),
                        session_id=meta.get("session_id"),
                        metadata=meta,
                    ),
                    provider_id=self.provider_id,
                    score=item.get("score"),
                )
            )
        return hits

    async def list_memories(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List archival memories from Letta."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/archival/memory",
                    params={"page": 1},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.debug("letta list_memories failed: %s", exc)
            return []

        records: list[MemoryRecord] = []
        for item in (data.get("results") or data.get("archival_memory") or [])[:limit]:
            meta = item.get("metadata") or {}
            if owner and meta.get("owner") and meta["owner"] != owner:
                continue
            records.append(
                MemoryRecord(
                    id=item.get("id", ""),
                    text=item.get("content") or item.get("text") or "",
                    category=meta.get("category", "fact"),
                    source=meta.get("source", "letta"),
                    owner=meta.get("owner"),
                    session_id=meta.get("session_id"),
                    metadata=meta,
                )
            )
        return records

    async def delete(self, memory_id: str, *, owner: str | None = None) -> bool:
        """Delete a Letta archival memory entry."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.delete(
                    f"{self.base_url}/v1/archival/memory/{memory_id}",
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.debug("letta delete failed: %s", exc)
            return False

    # ── Virtual context management (Letta-specific) ─────────────────────

    async def create_agent(
        self,
        name: str,
        system_prompt: str,
        model: str = "gpt-4o-mini",
        tools: list[str] | None = None,
        context_window_limit: int | None = None,
    ) -> dict[str, Any] | None:
        """Create a Letta agent with virtual context management.

        The agent automatically pages data in/out of context to stay within
        token limits — critical for small-context models.
        """
        import httpx

        payload: dict[str, Any] = {
            "name": name,
            "system_prompt": system_prompt,
            "model": model,
        }
        if tools:
            payload["tool_names"] = tools
        if context_window_limit:
            payload["llm_config"] = {
                "context_window": context_window_limit,
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/agents",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("letta create_agent failed: %s", exc)
            return None

    async def send_message(
        self,
        agent_id: str,
        message: str,
    ) -> dict[str, Any] | None:
        """Send a message to a Letta agent.

        Letta handles context paging automatically — older messages get
        archived, large documents get compressed, and the agent maintains
        working memory within its configured token budget.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/agents/{agent_id}/messages",
                    json={"messages": [{"role": "user", "content": message}]},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("letta send_message failed: %s", exc)
            return None

    # ── Tool schemas (Letta-specific tools) ─────────────────────────────

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Expose Letta-specific memory tools."""
        return [
            {
                "name": "letta_archival_search",
                "description": (
                    "Search Letta archival memory. Returns facts, documents, "
                    "and context that Letta has archived from previous conversations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for archival memory",
                        }
                    },
                    "required": ["query"],
                },
            },
        ]

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle Letta-specific tool calls."""
        if name == "letta_archival_search":
            hits = await self.recall(
                arguments.get("query", ""),
                top_k=arguments.get("top_k", 5),
            )
            return [
                {
                    "text": hit.memory.text,
                    "score": hit.score,
                    "metadata": hit.memory.metadata,
                }
                for hit in hits
            ]
        raise KeyError(f"LettaMemoryProvider does not expose tool {name}")
