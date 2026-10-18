"""M3.2 — acontext woken via the native MemoryProviderRegistry seam.

The old integration was a hardcoded, ungated, *synchronous* ``httpx.post`` at
the tail of ``stream_agent_loop`` (blocked the event loop, ignored ACONTEXT_URL
and ACONTEXT_ENABLED). This wires acontext in as an observe-only memory provider
whose only new behavior is end-of-session distillation, dispatched through the
registry. These tests pin the contract.
"""

import asyncio


def run(coro):
    return asyncio.run(coro)


class _SpyProvider:
    """Minimal MemoryProvider-shaped spy for dispatch tests."""

    def __init__(self, provider_id, enabled=True, boom=False):
        self.provider_id = provider_id
        self.enabled = enabled
        self.boom = boom
        self.calls = []

    async def on_session_end(self, **kwargs):
        if self.boom:
            raise RuntimeError("provider blew up")
        self.calls.append(kwargs)


def test_base_provider_on_session_end_is_noop():
    from src.memory_provider import NativeMemoryProvider

    class _M:
        def load_all(self):
            return []

    provider = NativeMemoryProvider(_M(), None)
    # default hook exists and returns None without touching anything
    assert run(provider.on_session_end(session_id="s1", messages=[], outcome="completed")) is None


def test_dispatch_session_end_hits_only_active_providers():
    from src.memory_provider import MemoryProviderRegistry

    active = _SpyProvider("a", enabled=True)
    disabled = _SpyProvider("b", enabled=False)
    reg = MemoryProviderRegistry([active, disabled])

    run(reg.dispatch_session_end(session_id="s1", messages=[1, 2], outcome="completed"))

    assert len(active.calls) == 1
    assert active.calls[0]["session_id"] == "s1"
    assert disabled.calls == []


def test_dispatch_session_end_isolates_provider_failures():
    from src.memory_provider import MemoryProviderRegistry

    boom = _SpyProvider("boom", enabled=True, boom=True)
    good = _SpyProvider("good", enabled=True)
    reg = MemoryProviderRegistry([boom, good])

    # one raising provider must not stop the others or bubble up
    run(reg.dispatch_session_end(session_id="s1", messages=[], outcome="completed"))

    assert len(good.calls) == 1


def test_acontext_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ACONTEXT_ENABLED", raising=False)
    from src.memory_provider import AcontextMemoryProvider

    provider = AcontextMemoryProvider()
    assert provider.enabled is False


def test_acontext_enabled_by_env(monkeypatch):
    monkeypatch.setenv("ACONTEXT_ENABLED", "true")
    from src.memory_provider import AcontextMemoryProvider

    provider = AcontextMemoryProvider()
    assert provider.enabled is True


def test_acontext_url_from_env(monkeypatch):
    monkeypatch.setenv("ACONTEXT_URL", "http://acontext:8029")
    from src.memory_provider import AcontextMemoryProvider

    provider = AcontextMemoryProvider()
    assert provider.base_url == "http://acontext:8029"


def test_acontext_url_default(monkeypatch):
    monkeypatch.delenv("ACONTEXT_URL", raising=False)
    from src.memory_provider import AcontextMemoryProvider

    provider = AcontextMemoryProvider()
    assert provider.base_url == "http://localhost:8029"


def test_acontext_crud_is_inert(monkeypatch):
    monkeypatch.setenv("ACONTEXT_ENABLED", "true")
    from src.memory_provider import AcontextMemoryProvider

    provider = AcontextMemoryProvider()
    assert run(provider.recall("anything")) == []
    assert run(provider.list_memories()) == []
    assert run(provider.delete("x")) is False
    # acontext is observe-only: it exposes no memory tools
    assert provider.get_tool_schemas() == []


def test_acontext_on_session_end_posts(monkeypatch):
    monkeypatch.setenv("ACONTEXT_ENABLED", "true")
    monkeypatch.setenv("ACONTEXT_URL", "http://acontext:8029")
    from src.memory_provider import AcontextMemoryProvider

    captured = {}

    class _FakeResp:
        status_code = 200

    class _FakeClient:
        def __init__(self, *a, **k):
            captured["timeout"] = k.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    provider = AcontextMemoryProvider()
    run(provider.on_session_end(session_id="sess-42", messages=[1, 2, 3], outcome="completed"))

    assert captured["url"] == "http://acontext:8029/api/sessions/complete"
    assert captured["json"]["session_id"] == "sess-42"
    assert captured["json"]["messages_count"] == 3
    assert captured["json"]["outcome"] == "completed"


def test_acontext_on_session_end_swallows_errors(monkeypatch):
    monkeypatch.setenv("ACONTEXT_ENABLED", "true")
    from src.memory_provider import AcontextMemoryProvider

    class _BoomClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise RuntimeError("network down")

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _BoomClient)

    provider = AcontextMemoryProvider()
    # must not raise
    assert run(provider.on_session_end(session_id="s", messages=[], outcome="completed")) is None


def test_active_registry_singleton_roundtrip():
    from src.memory_provider import (
        MemoryProviderRegistry,
        get_active_registry,
        set_active_registry,
    )

    reg = MemoryProviderRegistry([])
    set_active_registry(reg)
    assert get_active_registry() is reg
    set_active_registry(None)
    assert get_active_registry() is None
