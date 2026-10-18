"""Memory provider interfaces for native and external memory systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from src.app_context import app_context



@dataclass
class MemoryRecord:
    """Provider-neutral memory entry."""

    id: str
    text: str
    timestamp: int = 0
    category: str = "fact"
    source: str = "unknown"
    owner: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySearchHit:
    """A memory returned by provider recall."""

    memory: MemoryRecord
    provider_id: str
    score: float | None = None


class MemoryProvider(ABC):
    """Base contract for Odysseus memory providers.

    The native memory provider should always be available. External providers
    can add recall/write behavior and their own tools without replacing the
    built-in local memory baseline.
    """

    provider_id = "unknown"
    display_name = "Unknown"
    enabled = True

    async def initialize(self) -> None:
        """Prepare provider resources before use."""

    async def shutdown(self) -> None:
        """Release provider resources."""

    async def on_session_end(
        self,
        *,
        session_id: str | None = None,
        messages: list[Any] | None = None,
        outcome: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Session-lifecycle hook. Default no-op; observe-only providers override."""

    @abstractmethod
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
        """Store a memory and return the stored record."""

    @abstractmethod
    async def recall(
        self,
        query: str,
        *,
        owner: str | None = None,
        top_k: int = 5,
    ) -> list[MemorySearchHit]:
        """Return provider memories relevant to the query."""

    @abstractmethod
    async def list_memories(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List memories visible to the owner."""

    @abstractmethod
    async def delete(self, memory_id: str, *, owner: str | None = None) -> bool:
        """Delete a memory by ID when allowed by the provider."""

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return provider-defined tool schemas when this provider is enabled."""
        return []

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Handle a provider-defined tool call."""
        raise KeyError(f"Provider {self.provider_id} does not expose tool {name}")


class NativeMemoryProvider(MemoryProvider):
    """Provider adapter for Odysseus' built-in memory manager and vector store."""

    provider_id = "native"
    display_name = "Odysseus native memory"

    _CORE_FIELDS = {
        "id",
        "text",
        "timestamp",
        "source",
        "category",
        "uses",
        "owner",
        "session_id",
        "metadata",
    }

    def __init__(self, memory_manager, memory_vector=None):
        self.memory_manager = memory_manager
        self.memory_vector = memory_vector

    def _to_record(self, entry: dict[str, Any]) -> MemoryRecord:
        metadata = {key: value for key, value in entry.items() if key not in self._CORE_FIELDS}
        stored_metadata = entry.get("metadata")
        if isinstance(stored_metadata, dict):
            metadata.update(stored_metadata)

        return MemoryRecord(
            id=entry.get("id", ""),
            text=entry.get("text", ""),
            timestamp=entry.get("timestamp", 0),
            category=entry.get("category", "fact"),
            source=entry.get("source", "unknown"),
            owner=entry.get("owner"),
            session_id=entry.get("session_id"),
            metadata=metadata,
        )

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
        entry = self.memory_manager.add_entry(
            text,
            source=source,
            category=category,
            owner=owner,
        )
        if session_id:
            entry["session_id"] = session_id
        if metadata:
            entry["metadata"] = dict(metadata)

        memories = self.memory_manager.load_all()
        memories.append(entry)
        self.memory_manager.save(memories)

        if self._vector_available():
            self.memory_vector.add(entry["id"], entry["text"])

        return self._to_record(entry)

    async def recall(
        self,
        query: str,
        *,
        owner: str | None = None,
        top_k: int = 5,
    ) -> list[MemorySearchHit]:
        memories = self.memory_manager.load(owner=owner)
        by_id = {m.get("id"): m for m in memories}

        if self._vector_available():
            hits: list[MemorySearchHit] = []
            for result in self.memory_vector.search(query, k=top_k):
                if not isinstance(result, dict):
                    continue
                memory_id = result.get("memory_id")
                entry = by_id.get(memory_id) if memory_id else result
                if not entry:
                    continue
                if owner is not None and entry.get("owner") != owner:
                    continue
                hits.append(
                    MemorySearchHit(
                        memory=self._to_record(entry),
                        provider_id=self.provider_id,
                        score=result.get("score"),
                    )
                )
            if hits:
                return hits

        fallback = self.memory_manager.get_relevant_memories(
            query,
            memories,
            max_items=top_k,
        )
        return [
            MemorySearchHit(
                memory=self._to_record(entry),
                provider_id=self.provider_id,
                score=None,
            )
            for entry in fallback
        ]

    async def list_memories(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        return [self._to_record(entry) for entry in self.memory_manager.load(owner=owner)[:limit]]

    async def delete(self, memory_id: str, *, owner: str | None = None) -> bool:
        memories = self.memory_manager.load_all()
        remaining = []
        deleted_id = None

        for entry in memories:
            if entry.get("id") != memory_id:
                remaining.append(entry)
                continue
            if owner is not None and entry.get("owner") != owner:
                remaining.append(entry)
                continue
            deleted_id = entry.get("id")

        if deleted_id is None:
            return False

        self.memory_manager.save(remaining)
        if self._vector_available():
            self.memory_vector.remove(deleted_id)
        return True

    def _vector_available(self) -> bool:
        return bool(self.memory_vector and getattr(self.memory_vector, "healthy", True))


class MemoryProviderRegistry:
    """Container for native and optional external memory providers."""

    def __init__(self, providers: Iterable[MemoryProvider] | None = None):
        self._providers: dict[str, MemoryProvider] = {}
        for provider in providers or []:
            self.register(provider)

    def register(self, provider: MemoryProvider) -> None:
        if provider.provider_id in self._providers:
            raise ValueError(f"Memory provider already registered: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> MemoryProvider:
        return self._providers[provider_id]

    def all(self) -> list[MemoryProvider]:
        return list(self._providers.values())

    def active(self) -> list[MemoryProvider]:
        return [provider for provider in self._providers.values() if provider.enabled]

    async def dispatch_session_end(self, **kwargs: Any) -> None:
        """Fan the end-of-session hook out to every active provider.

        A single provider's failure must not stop the others nor bubble up into
        the agent loop, so per-provider exceptions are swallowed.
        """
        import logging

        log = logging.getLogger(__name__)
        for provider in self.active():
            try:
                await provider.on_session_end(**kwargs)
            except Exception as exc:  # noqa: BLE001 - isolate per-provider faults
                log.debug(
                    "memory provider %s on_session_end failed: %s",
                    provider.provider_id,
                    exc,
                )

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        seen: dict[str, str] = {}

        for provider in self.active():
            for schema in provider.get_tool_schemas():
                name = self._tool_name(schema)
                if name in seen:
                    raise ValueError(
                        f"Memory tool name conflict: {name} from {provider.provider_id} already exposed by {seen[name]}"
                    )
                seen[name] = provider.provider_id
                schemas.append(schema)

        return schemas

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        provider_by_tool: dict[str, MemoryProvider] = {}
        for provider in self.active():
            for schema in provider.get_tool_schemas():
                tool_name = self._tool_name(schema)
                if tool_name in provider_by_tool:
                    raise ValueError(
                        f"Memory tool name conflict: {tool_name} from "
                        f"{provider.provider_id} already exposed by "
                        f"{provider_by_tool[tool_name].provider_id}"
                    )
                provider_by_tool[tool_name] = provider

        provider = provider_by_tool.get(name)
        if provider:
            return await provider.handle_tool_call(name, arguments)
        raise KeyError(f"No active memory provider exposes tool {name}")

    @staticmethod
    def _tool_name(schema: dict[str, Any]) -> str:
        if not isinstance(schema, dict):
            raise ValueError("Memory provider tool schema must be a dict")
        name = schema.get("name")
        if isinstance(name, str) and name:
            return name
        function = schema.get("function")
        if isinstance(function, dict):
            function_name = function.get("name")
            if isinstance(function_name, str) and function_name:
                return function_name
        raise ValueError("Memory provider tool schema is missing a tool name")


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"on", "1", "true", "yes"}


class AcontextMemoryProvider(MemoryProvider):
    """Observe-only provider: distills a finished session to the acontext service.

    It does NOT store or recall memories (the native provider owns that). Its
    only behavior is the end-of-session distillation POST, gated by
    ``ACONTEXT_ENABLED`` and targeting ``ACONTEXT_URL``.
    """

    provider_id = "acontext"
    display_name = "Acontext session distillation"

    def __init__(
        self,
        base_url: str | None = None,
        enabled: bool | None = None,
        timeout: float = 2.0,
    ):
        import os

        self.base_url = (base_url or os.getenv("ACONTEXT_URL") or "http://localhost:8029").rstrip("/")
        self.enabled = enabled if enabled is not None else _env_truthy(os.getenv("ACONTEXT_ENABLED"))
        self.timeout = timeout

    async def on_session_end(
        self,
        *,
        session_id: str | None = None,
        messages: list[Any] | None = None,
        outcome: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        import logging

        payload = {
            "session_id": session_id or "unknown",
            "messages_count": len(messages) if messages is not None else 0,
            "outcome": outcome,
        }
        if metadata:
            payload["metadata"] = metadata
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(f"{self.base_url}/api/sessions/complete", json=payload)
        except Exception as exc:  # noqa: BLE001 - distillation is best-effort
            logging.getLogger(__name__).debug("acontext distillation skipped: %s", exc)

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
        # Observe-only: acontext is not a memory store, so remember does not
        # persist. Returns a neutral record echoing the input.
        return MemoryRecord(
            id="",
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
        return []

    async def list_memories(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        return []

    async def delete(self, memory_id: str, *, owner: str | None = None) -> bool:
        return False


# ── Active-registry singleton ──────────────────────────────────────────────
# Mirrors the channel_gateway ``get_gateway`` pattern: the app builds one
# registry at startup and stashes it here so free functions (e.g. the streaming
# agent loop) can fan session-end out without threading it through every call.
app_context.caches.active_registry: MemoryProviderRegistry | None = None


def set_active_registry(registry: MemoryProviderRegistry | None) -> None:
    app_context.caches.active_registry = registry


def get_active_registry() -> MemoryProviderRegistry | None:
    return app_context.caches.active_registry
