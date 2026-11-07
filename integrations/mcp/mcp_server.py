#!/usr/bin/env python3
"""odysseus-functions — MCP bridge (stdio or HTTP) for an Odysseus instance.

Exposes the agent's HTTP API as three MCP tools so brain agents can drive a
remote Odysseus (chat with the full agent, search past messages, list tools).

Config via environment:
  ODYSSEUS_BASE_URL     default http://127.0.0.1:7000 (local instance;
                        set ODYSSEUS_BASE_URL for remote instances)
  ODYSSEUS_TOKEN        REQUIRED — ody_* API token, scope "chat"
  ODYSSEUS_ENDPOINT_ID  used when auto-creating a session (pez default 7dac0958)
  ODYSSEUS_MODEL        used when auto-creating a session (default qwen3.5:9b)
  ODYSSEUS_CHAT_TIMEOUT seconds for a chat roundtrip (default 300)

Transport:
  ODYSSEUS_MCP_TRANSPORT  "stdio" (default) or "http"
  ODYSSEUS_MCP_HOST       http bind host (default 127.0.0.0 — loopback only;
                          containers set 0.0.0.0 and publish on host loopback)
  ODYSSEUS_MCP_PORT       http bind port (default 3014)
  ODYSSEUS_MCP_TOKEN      REQUIRED in http mode — static gateway bearer token,
                          constant-time checked on EVERY request (MCP path and
                          /health alike), brain-mcp style. In stdio mode the
                          transport is a private pipe, no gateway token needed.

Session semantics: `session_id` is the human-friendly session NAME as shown in
the Odysseus UI. The API requires the session UUID, so the bridge resolves
name -> UUID via GET /api/sessions and auto-creates missing sessions (POST
/api/session, form-encoded) with the endpoint/model above. Sessions created
here are the owner's real sessions — they appear in the desktop UI too, because
API tokens act as their owner (effective_user).
"""
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

__version__ = "1.1.0"

BASE_URL = os.environ.get("ODYSSEUS_BASE_URL", "http://127.0.0.1:7000").rstrip("/")
TOKEN = os.environ.get("ODYSSEUS_TOKEN", "")
ENDPOINT_ID = os.environ.get("ODYSSEUS_ENDPOINT_ID", "7dac0958")
MODEL = os.environ.get("ODYSSEUS_MODEL", "qwen3.5:9b")
CHAT_TIMEOUT = int(os.environ.get("ODYSSEUS_CHAT_TIMEOUT", "300"))

TRANSPORT = os.environ.get("ODYSSEUS_MCP_TRANSPORT", "stdio").lower()
GW_HOST = os.environ.get("ODYSSEUS_MCP_HOST", "127.0.0.1")
GW_PORT = int(os.environ.get("ODYSSEUS_MCP_PORT", "3014"))
GW_TOKEN = os.environ.get("ODYSSEUS_MCP_TOKEN", "")

mcp = FastMCP("odysseus-functions")

_session_ids: dict[str, str] = {}  # name -> UUID, filled lazily


def _api(method: str, path: str, payload: dict | None = None,
         form: dict | None = None, timeout: int = 30):
    """One HTTP call to the Odysseus API; returns decoded JSON.

    Raises RuntimeError with the response body on HTTP errors so tool callers
    see the API's own error message instead of a bare status code.
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {body}") from None


def _resolve_session(name: str) -> str:
    """Session NAME -> UUID, auto-creating the session on first use."""
    if name in _session_ids:
        return _session_ids[name]
    sessions = _api("GET", "/api/sessions")
    if isinstance(sessions, dict):  # tolerate a wrapped response
        sessions = sessions.get("sessions", [])
    for s in sessions:
        if s.get("name") == name:
            _session_ids[name] = s["id"]
            return s["id"]
    created = _api("POST", "/api/session",
                   form={"name": name, "endpoint_id": ENDPOINT_ID, "model": MODEL})
    _session_ids[name] = created["id"]
    return created["id"]


@mcp.tool
def odysseus_chat(message: str, session_id: str = "mcp-bridge") -> dict:
    """Talk to the full Odysseus agent (tools, memory, the lot).

    Returns dict with the agent reply under "response" plus the model /
    endpoint actually used. Each session_id keeps its own history, visible in
    the Odysseus UI. A chat roundtrip can take tens of seconds.
    """
    sid = _resolve_session(session_id)
    return _api("POST", "/api/chat", {"message": message, "session": sid},
                timeout=CHAT_TIMEOUT)


@mcp.tool
def odysseus_search(q: str, limit: int = 10) -> list:
    """Full-text search over the owner's past Odysseus chat messages.

    Returns a list of hits (message_id, session_id, session_name, role,
    content_snippet, ...). limit: 1-100.
    """
    return _api("GET", f"/api/search?q={urllib.parse.quote(q)}&limit={limit}")


@mcp.tool
def odysseus_tools() -> dict:
    """List the Odysseus agent's tools with their enabled/disabled status."""
    return _api("GET", "/api/tools")


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """Static bearer token on every route (tools, health, everything)."""

    async def dispatch(self, request: Request, call_next):
        expected = f"Bearer {GW_TOKEN}".encode()
        got = request.headers.get("authorization", "").encode()
        if not GW_TOKEN or not hmac.compare_digest(got, expected):
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness for the HTTP gateway (also behind the bearer token)."""
    return JSONResponse(
        {"status": "ok", "version": __version__, "base_url": BASE_URL,
         "transport": "http", "ts": int(time.time())}
    )


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("ODYSSEUS_TOKEN env var is required (ody_* API token, scope chat)")
    if TRANSPORT == "http":
        if not GW_TOKEN:
            raise SystemExit("ODYSSEUS_MCP_TOKEN is required for HTTP mode")
        app = mcp.http_app(middleware=[Middleware(GatewayAuthMiddleware)])
        import uvicorn

        uvicorn.run(app, host=GW_HOST, port=GW_PORT, log_level="info")
    else:
        mcp.run()  # stdio default
