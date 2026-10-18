"""
serena_client.py — Serena MCP client for code intelligence.

Provides find_references, get_symbols, goto_definition, and semantic_search
by calling Serena MCP over HTTP. Falls back gracefully when the server is
unreachable or the kill-switch is off.

Kill-switch: ODYSSEUS_SERENA_MCP=on
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

SERENA_MCP_URL = os.getenv("SERENA_MCP_URL", "http://localhost:9751")
_HTTP_TIMEOUT = 15


def _serena_enabled() -> bool:
    return os.getenv("ODYSSEUS_SERENA_MCP", "").strip().lower() in ("1", "true", "yes", "on")


def _mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if not _serena_enabled():
        return {"error": "Serena MCP is disabled (ODYSSEUS_SERENA_MCP not on)"}
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{SERENA_MCP_URL}/mcp",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("result", body)
    except urllib.error.URLError as exc:
        logger.warning("Serena MCP unreachable at %s: %s", SERENA_MCP_URL, exc)
        return {"error": f"Serena MCP unreachable: {exc}"}
    except Exception as exc:
        logger.exception("Serena MCP call failed for %s", tool_name)
        return {"error": str(exc)}


def find_references(symbol: str, file: str | None = None) -> dict[str, Any]:
    """Find all references to a symbol.

    Args:
        symbol: The symbol name to find references for.
        file: Optional file path to scope the search.

    Returns:
        Dict with key 'references' (list of locations), or 'error'.
    """
    args = {"symbol": symbol}
    if file:
        args["file"] = file
    result = _mcp_call("find_references", args)
    if "error" in result:
        return result
    content = result.get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text", "{}"))
            except json.JSONDecodeError:
                return {"references": [item.get("text", "")]}
    return result


def get_symbols(file: str) -> dict[str, Any]:
    """List all symbols in a file.

    Args:
        file: Path to the file to extract symbols from.

    Returns:
        Dict with key 'symbols' (list of symbol info), or 'error'.
    """
    result = _mcp_call("get_symbols", {"file": file})
    if "error" in result:
        return result
    content = result.get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text", "{}"))
            except json.JSONDecodeError:
                return {"symbols": [item.get("text", "")]}
    return result


def goto_definition(symbol: str, file: str | None = None) -> dict[str, Any]:
    """Jump to the definition of a symbol.

    Args:
        symbol: The symbol name to find the definition of.
        file: Optional file path to scope the search.

    Returns:
        Dict with keys 'file', 'line', 'column', or 'error'.
    """
    args = {"symbol": symbol}
    if file:
        args["file"] = file
    result = _mcp_call("goto_definition", args)
    if "error" in result:
        return result
    content = result.get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text", "{}"))
            except json.JSONDecodeError:
                return {"definition": item.get("text", "")}
    return result


def semantic_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Semantic code search across the codebase.

    Args:
        query: Natural-language query.
        limit: Max results (default 10).

    Returns:
        Dict with key 'results' (list of matched locations), or 'error'.
    """
    result = _mcp_call("semantic_search", {"query": query, "limit": limit})
    if "error" in result:
        return result
    content = result.get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text", "{}"))
            except json.JSONDecodeError:
                return {"results": [item.get("text", "")]}
    return result
