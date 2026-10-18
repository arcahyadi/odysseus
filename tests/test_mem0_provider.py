"""Tests for Mem0Provider — A4 memory integration.

Covers:
- Kill-switch behaviour (ODYSSEUS_MEM0 env)
- Provider registration/disabled state
- search_facts / get_user_profile when disabled
- Tool schemas exposed
- on_session_end graceful degradation when mem0ai missing
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_provider(enabled: bool = True):
    """Build a Mem0Provider with the real module but mocked internals."""
    # Ensure the module is importable
    from services.memory.mem0_provider import Mem0Provider

    provider = Mem0Provider(native_provider=None, enabled=enabled)
    provider._memory = MagicMock()  # pretend mem0ai is loaded
    return provider


def _make_disabled_provider():
    from services.memory.mem0_provider import Mem0Provider

    return Mem0Provider(native_provider=None, enabled=False)


# ── Kill-switch tests ───────────────────────────────────────────────────


class TestKillSwitch:
    def test_off_disables(self):
        """ODYSSEUS_MEM0=off → provider disabled."""
        from services.memory.mem0_provider import Mem0Provider

        with patch.dict(os.environ, {"ODYSSEUS_MEM0": "off"}):
            p = Mem0Provider(native_provider=None)
            assert not p.enabled

    def test_empty_env_enabled(self):
        """No env var → provider enabled by default."""
        from services.memory.mem0_provider import Mem0Provider

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ODYSSEUS_MEM0", None)
            p = Mem0Provider(native_provider=None)
            assert p.enabled

    def test_on_env_enabled(self):
        """ODYSSEUS_MEM0=on → provider enabled."""
        from services.memory.mem0_provider import Mem0Provider

        with patch.dict(os.environ, {"ODYSSEUS_MEM0": "on"}):
            p = Mem0Provider(native_provider=None)
            assert p.enabled

    def test_explicit_enabled_overrides(self):
        """Explicit enabled=True overrides env."""
        from services.memory.mem0_provider import Mem0Provider

        with patch.dict(os.environ, {"ODYSSEUS_MEM0": "off"}):
            p = Mem0Provider(native_provider=None, enabled=True)
            assert p.enabled

    def test_explicit_disabled_overrides(self):
        """Explicit enabled=False disables even if env is on."""
        from services.memory.mem0_provider import Mem0Provider

        with patch.dict(os.environ, {"ODYSSEUS_MEM0": "on"}):
            p = Mem0Provider(native_provider=None, enabled=False)
            assert not p.enabled


# ── Provider metadata ───────────────────────────────────────────────────


class TestProviderMeta:
    def test_provider_id(self):
        p = _make_provider()
        assert p.provider_id == "mem0"

    def test_display_name(self):
        p = _make_provider()
        assert "Mem0" in p.display_name


# ── Disabled provider behaviour ─────────────────────────────────────────


class TestDisabledBehaviour:
    @pytest.mark.asyncio
    async def test_search_facts_empty(self):
        p = _make_disabled_provider()
        result = await p.search_facts("hello", user_id="u1")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_profile_empty(self):
        p = _make_disabled_provider()
        result = await p.get_user_profile("u1")
        assert result == {"user_id": "u1", "facts": [], "count": 0}

    @pytest.mark.asyncio
    async def test_on_session_end_noop(self):
        p = _make_disabled_provider()
        # Should not raise
        await p.on_session_end(messages=[{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_remember_noop(self):
        p = _make_disabled_provider()
        record = await p.remember("test fact")
        assert record.text == "test fact"

    @pytest.mark.asyncio
    async def test_recall_empty(self):
        p = _make_disabled_provider()
        hits = await p.recall("query")
        assert hits == []

    @pytest.mark.asyncio
    async def test_list_memories_empty(self):
        p = _make_disabled_provider()
        records = await p.list_memories()
        assert records == []

    @pytest.mark.asyncio
    async def test_delete_returns_false(self):
        p = _make_disabled_provider()
        result = await p.delete("fake-id")
        assert result is False


# ── Tool schemas ─────────────────────────────────────────────────────────


class TestToolSchemas:
    def test_exposes_two_tools(self):
        p = _make_provider()
        schemas = p.get_tool_schemas()
        assert len(schemas) == 2

    def test_tool_names(self):
        p = _make_provider()
        schemas = p.get_tool_schemas()
        names = {s["function"]["name"] for s in schemas}
        assert names == {"mem0_search_facts", "mem0_get_profile"}


# ── Enabled provider with mock mem0ai ───────────────────────────────────


class TestEnabledBehaviour:
    @pytest.mark.asyncio
    async def test_search_facts_calls_mem0(self):
        p = _make_provider()
        p._memory.search = MagicMock(
            return_value={
                "results": [
                    {"id": "f1", "memory": "User likes dark mode", "score": 0.9, "event": "ADD"},
                    {"id": "f2", "memory": "User prefers tabs over spaces", "score": 0.7, "event": "ADD"},
                ]
            }
        )
        facts = await p.search_facts("preferences", user_id="u1")
        assert len(facts) == 2
        assert facts[0]["text"] == "User likes dark mode"
        p._memory.search.assert_called_once_with("preferences", user_id="u1", limit=10)

    @pytest.mark.asyncio
    async def test_get_user_profile_calls_mem0(self):
        p = _make_provider()
        p._memory.get_all = MagicMock(
            return_value={
                "results": [
                    {"id": "f1", "memory": "Alice is a developer", "score": 1.0, "event": "ADD"},
                ]
            }
        )
        profile = await p.get_user_profile("u1")
        assert profile["count"] == 1
        assert profile["facts"][0]["text"] == "Alice is a developer"

    @pytest.mark.asyncio
    async def test_on_session_end_extracts_facts(self):
        p = _make_provider()
        p._memory.add = MagicMock(
            return_value={
                "results": [
                    {"id": "new1", "memory": "User works at Acme", "event": "ADD", "score": 0.95},
                ]
            }
        )
        await p.on_session_end(
            session_id="s1",
            messages=[
                {"role": "user", "content": "I work at Acme Corp"},
                {"role": "assistant", "content": "Got it!"},
            ],
            metadata={"user_id": "u1"},
        )
        p._memory.add.assert_called_once()
        assert len(p._facts) == 1
        assert p._facts[0]["text"] == "User works at Acme"

    @pytest.mark.asyncio
    async def test_on_session_end_graceful_on_error(self):
        p = _make_provider()
        p._memory.add = MagicMock(side_effect=RuntimeError("mem0 down"))
        # Should not raise
        await p.on_session_end(
            session_id="s1",
            messages=[{"role": "user", "content": "test"}],
        )

    @pytest.mark.asyncio
    async def test_remember_delegates_to_mem0_and_native(self):
        native = MagicMock()
        native.remember = AsyncMock(return_value=MagicMock(text="test"))
        p = _make_provider()
        p._native = native
        p._memory.add = MagicMock()

        result = await p.remember("test fact", owner="u1")
        p._memory.add.assert_called_once()
        native.remember.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tool_call_search(self):
        p = _make_provider()
        p._memory.search = MagicMock(return_value={"results": []})
        result = await p.handle_tool_call("mem0_search_facts", {"query": "test"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_handle_tool_call_profile(self):
        p = _make_provider()
        p._memory.get_all = MagicMock(return_value={"results": []})
        result = await p.handle_tool_call("mem0_get_profile", {"user_id": "u1"})
        assert result["count"] == 0
