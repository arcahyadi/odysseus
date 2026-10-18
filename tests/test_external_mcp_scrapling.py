"""Bloc F — wake Scrapling as a real MCP server (native-first, verified).

The docker-compose service runs Scrapling's own MCP server over Streamable HTTP.
Its real tools are get/bulk_get/fetch/bulk_fetch/stealthy_fetch/... — NOT the
`scrapling_fetch/spider/extract` the old SCRAPLING_TOOLS invented, and NOT the
REST `/extract`+`/spider` the old proxy assumed. The correct wiring is to let
the native MCP manager connect to it (transport=http) so the *server's own*
tools surface as `mcp__scrapling__*` with schemas discovered at connect time.

`EXTERNAL_MCP_SERVERS` was dead config (never consumed). These tests pin the
decision layer that makes it live: only entries with a real MCP `transport` are
connected, gated by their enable-flag env (kill-switch), and REST-only bundles
(Kroki → served by the native render_diagram tool) are never MCP-connected.
"""

import asyncio

from src.mcp_manager import EXTERNAL_MCP_SERVERS, McpManager


def _picks(m):
    return {sid: (name, transport, url) for sid, name, transport, url in m._external_servers_to_connect()}


def test_scrapling_included_when_enabled(monkeypatch):
    monkeypatch.setenv("SCRAPLING_ENABLED", "true")
    assert "scrapling" in _picks(McpManager())


def test_scrapling_excluded_when_disabled(monkeypatch):
    monkeypatch.setenv("SCRAPLING_ENABLED", "false")
    assert "scrapling" not in _picks(McpManager())


def test_scrapling_uses_http_streamable_mount(monkeypatch):
    monkeypatch.setenv("SCRAPLING_ENABLED", "true")
    _name, transport, url = _picks(McpManager())["scrapling"]
    assert transport == "http"
    # Streamable-HTTP MCP endpoint is mounted at /mcp
    assert url.rstrip("/").endswith("/mcp")


def test_kroki_is_never_mcp_connected(monkeypatch):
    # Kroki ships as a container but has no MCP endpoint — the native
    # render_diagram tool serves it over REST. It must never be MCP-connected.
    monkeypatch.setenv("KROKI_ENABLED", "true")
    assert "kroki" not in _picks(McpManager())


def test_connect_external_enabled_dispatches_http_connect(monkeypatch):
    monkeypatch.setenv("SCRAPLING_ENABLED", "true")
    m = McpManager()
    calls = []

    async def fake_connect(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(m, "connect_server", fake_connect)

    async def _run():
        tasks = await m.connect_external_enabled()
        if tasks:
            await asyncio.gather(*tasks)

    asyncio.run(_run())
    scrapling_calls = [c for c in calls if c.get("server_id") == "scrapling"]
    assert scrapling_calls, "expected a connect_server call for scrapling"
    assert scrapling_calls[0]["transport"] == "http"
    assert scrapling_calls[0]["url"].rstrip("/").endswith("/mcp")


def test_connect_external_enabled_skips_when_all_disabled(monkeypatch):
    monkeypatch.setenv("SCRAPLING_ENABLED", "false")
    m = McpManager()
    calls = []

    async def fake_connect(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(m, "connect_server", fake_connect)

    async def _run():
        tasks = await m.connect_external_enabled()
        if tasks:
            await asyncio.gather(*tasks)

    asyncio.run(_run())
    assert calls == []


def test_scrapling_entry_no_longer_references_fake_tool_schema():
    # The invented SCRAPLING_TOOLS schema is gone; the entry must not point at it.
    assert EXTERNAL_MCP_SERVERS["scrapling"].get("tools") != "SCRAPLING_TOOLS"
