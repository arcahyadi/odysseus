"""Fast launcher — skips slow MCP connections for quick UI testing."""

import asyncio
import os

# Skip slow services
#
# Each line below must name a variable the code actually READS. The launcher used
# to write three names nothing read, so it activated nothing:
#
#   * `ODYSSEUS_DURABLE_EXEC` → the real name is `ODYSSEUS_DURABLE_EXECUTION`,
#     read by `src/durable_execution.py`. Renamed. It was masked because the
#     switch is already `on` by default: the day a palier flips that default to
#     `off`, the launcher would silently stop enabling what it believes it
#     enables.
#   * `ODYSSEUS_THOUGHT_BUS` → deleted. There is no such switch: no module reads
#     it, and the registry has no thought-bus entry. The launcher was writing an
#     intention, not a setting. (That the bus feature has NO kill-switch at all is
#     a governance finding of its own — reported, not fixed here.)
#   * `MCP_CONNECT_TIMEOUT` → deleted. The speed-up is the monkey-patch below
#     (`connect_all_enabled` / `connect_external_enabled`), and nothing read the
#     variable. Giving it a plausible real name would have created a second dead
#     wire, this one harder to spot than the first.
#
# `tests/test_sprint4_lanceur.py` now fails on any variable written here that has
# no reader, so the next drift of this kind is caught by the suite and not by eye.
os.environ["CHROMADB_HOST"] = ""
os.environ["ODYSSEUS_DURABLE_EXECUTION"] = "on"
os.environ["AUTH_ENABLED"] = "false"
os.environ["LOCALHOST_BYPASS"] = "true"

# Patch MCP manager to skip slow connections
import src.mcp_manager as mcp_mgr

_orig_connect = mcp_mgr.MCPManager.connect_all_enabled


async def _fast_connect(self):
    try:
        await asyncio.wait_for(_orig_connect(self), timeout=3)
    except:
        pass


mcp_mgr.MCPManager.connect_all_enabled = _fast_connect

_orig_external = mcp_mgr.MCPManager.connect_external_enabled


async def _skip_external(self):
    pass


mcp_mgr.MCPManager.connect_external_enabled = _skip_external

# Now start
if __name__ == "__main__":
    import uvicorn

    print("Fast launcher — starting on http://127.0.0.1:7000")
    uvicorn.run("app:app", host="127.0.0.1", port=7000, log_level="warning")
