# Odysseus MCP Bridge (`odysseus-functions`)

Expose a running **Odysseus** instance as an MCP server, so external agents
(Claude Code, Codex, any MCP client) can drive the full agent, search its past
conversations, and inspect its tool set.

This is an **optional** integration — the app itself is untouched. It is a
single-file Python server (fastmcp) that talks to the normal HTTP API with a
regular `ody_…` API token (scope `chat`).

## Tools

| Tool | Cost | What it does |
|---|---|---|
| `odysseus_chat(message, session_id="mcp-bridge")` | 10-30 s | Full agent roundtrip — reasoning, its tools, its memory. Reply in `.response` |
| `odysseus_search(q, limit=10)` | instant | Full-text search over past chat messages |
| `odysseus_tools()` | instant | The instance's tool list with enabled/disabled status |

`session_id` is the session **name** (a topic label). The bridge resolves it
to the API's session UUID and auto-creates missing sessions. Sessions created
through the bridge are the token owner's real sessions — they show up in the
desktop UI. Chat roundtrips are a full agent run: expect tens of seconds.

## Token

An API token with scope **chat**, format `ody_…` (Settings > Integrations can
generate one, or your instance admin). The token acts as its owner
(`effective_user`): chats attribute to the owner's account, and can never
mint tokens or reach admin endpoints.

**Never put the token value in a repo or chat** — keep it in the client's MCP
config or a secrets manager only.

## Run as stdio (local agent config)

```bash
python3 -m venv ~/.venvs/odysseus-mcp
~/.venvs/odysseus-mcp/bin/pip install -r integrations/mcp/requirements.txt

claude mcp add odysseus-functions -s user \
  -e ODYSSEUS_BASE_URL=http://your-odysseus-host:7000 \
  -e ODYSSEUS_TOKEN=ody_… \
  -- ~/.venvs/odysseus-mcp/bin/python /path/to/odysseus/integrations/mcp/mcp_server.py
```

Stdio is the default transport: a private pipe, no extra auth needed.

## Run as an HTTP gateway (shared / remote)

```bash
ODYSSEUS_BASE_URL=http://your-odysseus-host:7000 \
ODYSSEUS_TOKEN=ody_… \
ODYSSEUS_MCP_TRANSPORT=http \
ODYSSEUS_MCP_TOKEN=<random 32-byte hex> \
ODYSSEUS_MCP_HOST=127.0.0.1 ODYSSEUS_MCP_PORT=3014 \
python3 integrations/mcp/mcp_server.py
```

- MCP endpoint: `http://127.0.0.1:3014/mcp` (+ `Authorization: Bearer
  <ODYSSEUS_MCP_TOKEN>` on **every** request, constant-time checked, including
  `GET /health`).
- Put it behind your own TLS/reverse proxy if you need remote access; keep it
  loopback-bound otherwise — the gateway is a single static token.
- Client config (URL transport):

```json
{
  "mcpServers": {
    "odysseus-functions": {
      "type": "url",
      "url": "https://your-host/mcp",
      "headers": { "Authorization": "Bearer <gateway-token>" }
    }
  }
}
```

## Config knobs (env)

| Var | Default | Meaning |
|---|---|---|
| `ODYSSEUS_BASE_URL` | `http://127.0.0.1:7000` | instance base URL |
| `ODYSSEUS_TOKEN` | — (required) | `ody_…` API token, scope chat |
| `ODYSSEUS_ENDPOINT_ID` | — | endpoint id used when **auto-creating** a session (required for auto-create; find yours in your instance's endpoints config) |
| `ODYSSEUS_MODEL` | `qwen3.5:9b` | model for auto-created sessions |
| `ODYSSEUS_CHAT_TIMEOUT` | `300` | chat roundtrip timeout (s) |
| `ODYSSEUS_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `ODYSSEUS_MCP_HOST` / `ODYSSEUS_MCP_PORT` | `127.0.0.1` / `3014` | http bind |
| `ODYSSEUS_MCP_TOKEN` | — (required for http) | gateway bearer token |

## Notes

- Works against any Odysseus deployment reachable over HTTP; no changes to
  the app, no admin endpoints used.
- The API requires the session **UUID** in `POST /api/chat`; the bridge
  resolves name → UUID via `GET /api/sessions` and caches the mapping
  in-process.
