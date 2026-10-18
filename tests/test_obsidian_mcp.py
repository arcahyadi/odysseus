"""Tests for the Obsidian read/search stdio MCP scaffold + its default-OFF gate."""

import json

import pytest

from mcp_servers import obsidian_mcp


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """A tmp Obsidian vault with two notes; points the module at it."""
    (tmp_path / "agentos").mkdir()
    (tmp_path / "root.md").write_text("root note\nalpha line", encoding="utf-8")
    (tmp_path / "agentos" / "learning.md").write_text("second brain\nalpha appears here too", encoding="utf-8")
    monkeypatch.setattr(obsidian_mcp, "VAULT_PATH", tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_list_tools_exposes_only_read_tools():
    tools = await obsidian_mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {"list_notes", "get_note", "search_notes"}
    # create_note is deliberately NOT exposed to the agent (write leg is the
    # native checkpoint bridge's job).
    assert "create_note" not in names


@pytest.mark.asyncio
async def test_call_get_note_returns_content(vault):
    result = await obsidian_mcp.call_tool("get_note", {"path": "root.md"})
    payload = json.loads(result[0].text)
    assert payload["path"] == "root.md"
    assert "root note" in payload["content"]


@pytest.mark.asyncio
async def test_call_list_notes_lists_vault(vault):
    result = await obsidian_mcp.call_tool("list_notes", {})
    payload = json.loads(result[0].text)
    paths = {n["path"] for n in payload}
    assert paths == {"root.md", "agentos/learning.md"}


@pytest.mark.asyncio
async def test_call_search_notes_finds_matches(vault):
    result = await obsidian_mcp.call_tool("search_notes", {"query": "alpha"})
    payload = json.loads(result[0].text)
    paths = {r["path"] for r in payload}
    assert paths == {"root.md", "agentos/learning.md"}


@pytest.mark.asyncio
async def test_call_unknown_tool_returns_error(vault):
    result = await obsidian_mcp.call_tool("create_note", {"path": "x.md", "content": "y"})
    assert "Unknown tool" in result[0].text


def test_obsidian_mcp_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_OBSIDIAN_MCP", raising=False)
    from src import builtin_mcp

    assert builtin_mcp._obsidian_mcp_enabled() is False
    assert builtin_mcp._optional_python_servers() == {}


def test_obsidian_mcp_registered_when_gate_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_OBSIDIAN_MCP", "1")
    from src import builtin_mcp

    assert builtin_mcp._obsidian_mcp_enabled() is True
    optional = builtin_mcp._optional_python_servers()
    assert "obsidian" in optional
    assert optional["obsidian"][0] == "mcp_servers/obsidian_mcp.py"
