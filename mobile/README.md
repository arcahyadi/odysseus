# Odysseus Mobile (Expo scaffold)

A dependency-light **Expo (React Native, plain JavaScript)** companion app for a
self-hosted [Odysseus](https://github.com/odysseus) AI workspace. It runs on a
phone on the **same LAN** as the server and talks to it over its REST API using a
Bearer API token (`ody_...`).

This is a **scaffold / skeleton** — open it later with:

```bash
npm install
npx expo start
```

No packages are installed by this scaffold and nothing here was executed against
a server; all sources are written to be consistent with the Odysseus backend
routes verified in the repo (see the endpoint table below).

---

## 1. Prerequisites / running

- Node 18+ and the Expo Go app (or an Android/iOS simulator) on the phone.
- The Odysseus server must **bind to your LAN**, not just loopback:
  `APP_BIND=0.0.0.0` (default port `APP_PORT`, which is **7000** —
  `companion/pairing.py:23`, `launcher.py:133-142`). Launch with
  `launch-windows.ps1` / the docker compose file, then verify the web UI is
  reachable at `http://<your-lan-ip>:7000`.
- Phone and server on the same network. For plain `http://` LAN testing:
  - **Expo Go** allows cleartext LAN traffic out of the box.
  - Standalone Android builds: `app.json` already sets
    `android.usesCleartextTraffic: true`.
  - Standalone iOS builds: `app.json` sets ATS `NSAllowsLocalNetworking`;
    if your build still refuses a raw-IP `http://` origin, relax ATS
    (`NSAllowsArbitraryLoads`) or use HTTPS.

## 2. Pairing flow

The server exposes a small "companion bridge" (`companion/routes.py`) purely so
LAN clients can discover what a server offers and validate credentials:

| Endpoint | Purpose | Verified |
| --- | --- | --- |
| `GET /api/companion/ping` | Auth-validated health: `{ok, name, version, auth}` | `companion/routes.py:85` |
| `GET /api/companion/info` | Server identity + capability flags: `{name, version, owner, capabilities:{chat,streaming}}` | `companion/routes.py:97` |
| `GET /api/companion/models` | Model endpoints the caller may use (chat-scoped bearer token required) | `companion/routes.py:109` |
| `GET /api/companion/pair` | Admin-only HTML page that renders a "Generate pairing code" form | `companion/routes.py:162` |
| `POST /api/companion/pair` | Admin-cookie-only token mint. `?format=json` returns `{host, port, token, hosts, payload:{v,host,port,token}, qr}` | `companion/routes.py:189` |

Pairing tokens are minted as `ody_<random>` with a **`chat` scope**
(`companion/pairing.py:20,83-106`). Because minting requires an admin *cookie*
(CSRF posture, `companion/routes.py:12-17`), a phone cannot mint one itself.

**In the app:**
1. Open **Pair with Odysseus**.
2. Enter the server address: `http://<lan-ip>:7000`.
3. Get a token on the server:
   - **Settings → API tokens** (recommended for full dashboard access — pick
     scopes matching what you want the phone to read/write), or
   - the admin web page **/api/companion/pair → "Generate pairing code"**
     (chat scope only).
4. Tap **Discover server** (`GET /api/companion/info`) to confirm the server is
   reachable, then **Test token** (`GET /api/companion/ping`) to validate the
   credential, then **Save & continue**.

Scope note: `ody_` pairing codes are chat-scoped, so they work for chat +
companion endpoints but will typically see **empty** results on the
Sessions/Memory/Digest/Notes/Plans lists (those are owner-scoped reads). Use a
token minted in **Settings → API tokens** for the full dashboard.

## 3. REST endpoints used by the app (verified in repo)

Auth header on every request when configured: `Authorization: Bearer ody_...`.

| Method | Path | Body / shape | Screen |
| --- | --- | --- | --- |
| GET | `/api/sessions` | bare JSON array of `{id, name, model, endpoint_url, rag, folder, message_count, created_at, updated_at, last_message_at, ...}` | Chat (session picker) |
| POST | `/api/chat` | `{message, session, ...}` (message + session **required**) → `{"response": "..."}` | Chat (non-streaming fallback) |
| POST | `/api/chat_stream` | `{message, session, ...}` → SSE stream (below) | Chat (streaming) |
| GET | `/api/memory` | `{memory: [...]}` items `{id, text, category, source, timestamp, uses}` | Memory |
| POST | `/api/memory/add` | `{text, category?, source?}` → `{ok, count, message?}` | Memory |
| GET | `/api/digest/` | `{digests: [...], total}` items `{id, date, status, summary, content, error}` | Digest |
| GET | `/api/notes` | `{notes: [...]}` items `{id, title, content, note_type, label, pinned, updated_at, ...}` | Notes |
| GET | `/api/plans` | bare JSON array of `{id, title, goal, status, current_step_index, step_count, done_count, created_at}` | Plans |
| GET | `/api/plans/{id}` | full plan incl. `steps: [{id, title, description, status, order, ...}]` | Plans (expanded) |

### SSE protocol (used by Chat)

The real streaming route is **`POST /api/chat_stream`**
(`routes/chat_routes.py:535`). The wire format is standard SSE blocks:

```
data: {"type":"model_info","model":"..."}\n\n
data: {"delta":"Hello"}\n\n          <- un-typed chunk events carry the reply
data: {"type":"rag_sources","data":[...]}\n\n
data: {"type":"message_saved","id":"..."}\n\n
data: [DONE]\n\n                     <- literal terminator
```

- `{delta: "..."}` chunks (optionally flagged `thinking: true` for reasoning
  tokens) accumulate into the reply — see `routes/chat_routes.py:1199-1311`.
- Metadata events are typed (`model_info`, `rag_sources`, `citations`,
  `web_sources`, `metrics`, `tool_start`, `tool_output`, `message_saved`, ...)
  and carry their payload under `data` (`routes/chat_routes.py:1024-1048`).
- The stream ends with the literal `data: [DONE]` line, **not** a JSON `done`
  event (`routes/chat_routes.py:1206-1237,1524-1525`).
- Heartbeat/`event:`/comment lines exist and are ignored by the parser.
- Because RN's `fetch` cannot read a body incrementally, the app streams via
  `XMLHttpRequest.responseText` (`src/api/endpoints.js` →
  `streamChatReply`), parsing complete `\n\n`-delimited blocks as they arrive.

**Chat always requires a session id** — `{message, session}` — verified by
`routes/chat_routes.py:37-44` and the `ChatRequest` model
(`src/request_models.py:7-14`). Pick a session from `GET /api/sessions` first.

## 4. Project layout

```
mobile/
  index.js                 # registerRootComponent entry (package.json "main")
  App.js                   # re-exports src/AppNavigator
  package.json             # Expo SDK 51, plain JS — no react-navigation dep
  app.json                 # name "Odysseus", portrait, android/ios ids
  babel.config.js          # babel-preset-expo
  src/
    AppNavigator.js        # tiny manual stack navigator (no 3rd-party nav)
    styles.js              # palette + shared StyleSheet
    utils.js               # pure-JS formatting helpers
    components.js          # Screen, buttons, notices, chips
    api/client.js          # config store (AsyncStorage w/ in-memory fallback),
                           # normalizeOrigin/joinUrl, fetch wrapper + ApiError
    api/endpoints.js       # one helper per endpoint + SSE parser/streamer
    screens/
      PairingScreen.js     # URL + token entry, Discover/Test/Save
      HomeScreen.js        # dashboard: Chat/Memory/Digest/Notes/Plans
      ChatScreen.js        # session picker + SSE streamed reply + raw log
      MemoryScreen.js      # list + add memory
      DigestScreen.js      # list, expand to content
      NotesScreen.js       # list, expand to content
      PlansScreen.js       # list + progress, expand loads steps
```

## 5. Notes / deliberate decisions

- **Plain JavaScript** everywhere (no TypeScript toolchain). Files with JSX use
  `.js` too. Only `src/api/client.js`, `src/api/endpoints.js` and
  `src/utils.js` are pure JS and were checked with `node --check`.
- **No navigation dependency**: `AppNavigator.js` is a ~40-line manual stack
  (push/back/replace). Adding react-navigation later is straightforward — every
  screen only receives `config` + a small `navigation` prop object.
- **Sessions**: the app lists them to let you pick one for chat; creating
  sessions is intentionally left to the web UI (POST `/api/session` is
  form-encoded and needs an endpoint/model — out of scope for the scaffold).
- **Config storage**: `@react-native-async-storage/async-storage` when
  available; a guarded in-memory fallback keeps the app usable otherwise.
- **Error handling**: every fetch is wrapped; screens render an inline error
  box instead of crashing. HTTP errors carry the server's `detail` message
  when present (`client.js` `ApiError`).
