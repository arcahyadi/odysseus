"""
cbm_client.py — Codebase Memory (CBM) client for semantic graph operations.

Provides search_graph, get_node, get_neighbors, and find_path by calling
the CBM MCP server at codebase-memory:9749 over HTTP.

Kill-switch: ODYSSEUS_CBM=on
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

CBM_MCP_URL = os.getenv("CBM_MCP_URL", "http://codebase-memory:9749")
_HTTP_TIMEOUT = 15


def _cbm_enabled() -> bool:
    return os.getenv("ODYSSEUS_CBM", "").strip().lower() in ("1", "true", "yes", "on")


def _mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if not _cbm_enabled():
        return {"error": "CBM is disabled (ODYSSEUS_CBM not on)"}
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{CBM_MCP_URL}/mcp",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("result", body)
    except urllib.error.URLError as exc:
        logger.warning("CBM MCP unreachable at %s: %s", CBM_MCP_URL, exc)
        return {"error": f"CBM MCP unreachable: {exc}"}
    except Exception as exc:
        logger.exception("CBM MCP call failed for %s", tool_name)
        return {"error": str(exc)}


def _unwrap_text(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text", "{}"))
            except json.JSONDecodeError:
                return {"raw": item.get("text", "")}
    return result


def search_graph(query: str, limit: int = 10) -> dict[str, Any]:
    """Semantic search across the codebase memory graph.

    Args:
        query: Natural-language or structural query.
        limit: Max results (default 10).

    Returns:
        Dict with key 'results' (list of matched nodes with scores), or 'error'.
    """
    result = _mcp_call("search_graph", {"query": query, "limit": limit})
    if "error" in result:
        return result
    return _unwrap_text(result)


def get_node(node_id: str) -> dict[str, Any]:
    """Retrieve a single node by its ID.

    Args:
        node_id: The node identifier.

    Returns:
        Dict with node properties (name, type, file, metadata), or 'error'.
    """
    result = _mcp_call("get_node", {"node_id": node_id})
    if "error" in result:
        return result
    return _unwrap_text(result)


def get_neighbors(node_id: str, direction: str = "both") -> dict[str, Any]:
    """Get the neighbors of a node in the graph.

    Args:
        node_id: The node identifier.
        direction: 'in', 'out', or 'both' (default).

    Returns:
        Dict with key 'neighbors' (list of adjacent nodes), or 'error'.
    """
    result = _mcp_call("get_neighbors", {"node_id": node_id, "direction": direction})
    if "error" in result:
        return result
    return _unwrap_text(result)


def find_path(from_id: str, to_id: str) -> dict[str, Any]:
    """Find the shortest path between two nodes.

    Args:
        from_id: Source node ID.
        to_id: Target node ID.

    Returns:
        Dict with key 'path' (ordered list of node IDs), or 'error'.
    """
    result = _mcp_call("find_path", {"from_id": from_id, "to_id": to_id})
    if "error" in result:
        return result
    return _unwrap_text(result)
