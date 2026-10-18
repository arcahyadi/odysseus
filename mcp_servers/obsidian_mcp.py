"""Obsidian second-brain MCP server — reads/writes Markdown files in vault."""

import asyncio
import json
import os
from pathlib import Path

VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/obsidian-vault"))


def _ensure_vault() -> Path:
    """Return vault path or raise if not configured/accessible."""
    if not VAULT_PATH.exists():
        raise FileNotFoundError(
            f"Obsidian vault not found at {VAULT_PATH}. Set OBSIDIAN_VAULT_PATH env var to the correct path."
        )
    return VAULT_PATH


def list_notes(folder: str = "") -> list[dict]:
    """List markdown notes in a vault folder (recursive).

    Args:
        folder: Relative sub-folder inside the vault. Empty string = vault root.

    Returns:
        List of dicts with keys: path (relative), name, size_bytes.
    """
    try:
        vault = _ensure_vault()
    except FileNotFoundError as exc:
        return [{"error": str(exc)}]

    base = vault / folder if folder else vault
    if not base.exists():
        return [{"error": f"Folder '{folder}' not found in vault."}]

    notes = []
    for md_file in sorted(base.rglob("*.md")):
        relative = md_file.relative_to(vault)
        notes.append(
            {
                "path": str(relative).replace("\\", "/"),
                "name": md_file.stem,
                "size_bytes": md_file.stat().st_size,
            }
        )
    return notes


def get_note(path: str) -> dict:
    """Read a markdown note from the vault.

    Args:
        path: Relative path inside the vault (e.g. "agentos/learnings/2026-06-27.md").

    Returns:
        Dict with keys: path, content. On error: {"error": "..."}.
    """
    try:
        vault = _ensure_vault()
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    note_path = vault / path
    if not note_path.exists():
        return {"error": f"Note '{path}' not found in vault."}
    if not note_path.is_file():
        return {"error": f"'{path}' is not a file."}

    try:
        content = note_path.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except OSError as exc:
        return {"error": f"Could not read note: {exc}"}


def create_note(path: str, content: str) -> dict:
    """Create or overwrite a markdown note in the vault.

    Args:
        path:    Relative path inside the vault. Parent folders are created as needed.
        content: Markdown content to write.

    Returns:
        Dict with keys: path, bytes_written. On error: {"error": "..."}.
    """
    try:
        vault = _ensure_vault()
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    note_path = vault / path
    try:
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
        return {"path": path, "bytes_written": len(content.encode("utf-8"))}
    except OSError as exc:
        return {"error": f"Could not write note: {exc}"}


def search_notes(query: str, folder: str = "") -> list[dict]:
    """Full-text search across markdown notes (case-insensitive substring match).

    Args:
        query:  Search term.
        folder: Restrict search to this sub-folder (empty = entire vault).

    Returns:
        List of dicts with keys: path, name, matches (list of matching lines).
    """
    try:
        vault = _ensure_vault()
    except FileNotFoundError as exc:
        return [{"error": str(exc)}]

    base = vault / folder if folder else vault
    if not base.exists():
        return [{"error": f"Folder '{folder}' not found in vault."}]

    query_lower = query.lower()
    results = []
    for md_file in sorted(base.rglob("*.md")):
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        matching_lines = [line.strip() for line in lines if query_lower in line.lower()]
        if matching_lines:
            relative = str(md_file.relative_to(vault)).replace("\\", "/")
            results.append(
                {
                    "path": relative,
                    "name": md_file.stem,
                    "matches": matching_lines,
                }
            )

    return results


# ---------------------------------------------------------------------------
# MCP tool registry — maps tool names to callables for the host to discover.
# ---------------------------------------------------------------------------

TOOLS = {
    "list_notes": list_notes,
    "get_note": get_note,
    "create_note": create_note,
    "search_notes": search_notes,
}


# ---------------------------------------------------------------------------
# stdio MCP server — exposes the READ/search tools to the agent host.
#
# Only list_notes/get_note/search_notes are surfaced. create_note is kept off
# the agent tool surface on purpose: the vault write leg is owned by the native
# checkpoint bridge (src/orchestrator/checkpoint_tracker.py), which imports
# create_note directly — not via MCP. This server is registered only when the
# ODYSSEUS_OBSIDIAN_MCP kill-switch is ON (default OFF), so startup is
# byte-identical by default.
# ---------------------------------------------------------------------------

from mcp.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402
from mcp.types import TextContent, Tool  # noqa: E402

server = Server("obsidian")


def _text_result(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_notes",
            description="List markdown notes in the Obsidian vault (recursive). "
            "Optional 'folder' restricts to a sub-folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Relative sub-folder inside the vault (empty = root).",
                    }
                },
            },
        ),
        Tool(
            name="get_note",
            description="Read a single markdown note from the Obsidian vault by relative path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path inside the vault, e.g. 'agentos/learnings/x.md'.",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="search_notes",
            description="Case-insensitive full-text search across markdown notes in the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term."},
                    "folder": {
                        "type": "string",
                        "description": "Restrict search to this sub-folder (empty = entire vault).",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_notes":
        result = list_notes(arguments.get("folder", ""))
    elif name == "get_note":
        result = get_note(arguments.get("path", ""))
    elif name == "search_notes":
        result = search_notes(arguments.get("query", ""), arguments.get("folder", ""))
    else:
        return _text_result(f"Unknown tool: {name}")
    return _text_result(json.dumps(result, ensure_ascii=False, indent=2))


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    asyncio.run(run())
