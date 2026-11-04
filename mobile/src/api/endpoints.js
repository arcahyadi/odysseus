// src/api/endpoints.js
//
// One helper per Odysseus REST endpoint used by the app. Pure JavaScript (no
// JSX) so it can be syntax-checked with `node --check`. Every helper is
// defensive: the server sometimes wraps a list as {key: [...]} and sometimes
// returns a bare array, so we normalise to plain arrays of plain objects.
//
// Endpoints were verified against the Odysseus repo (see README for a table
// with file/line references):
//   GET  /api/sessions            -> bare JSON array of sessions
//   POST /api/chat                -> {response: "..."} (non-streaming)
//   POST /api/chat_stream         -> SSE (data: {json} blocks, ends "data: [DONE]")
//   GET  /api/memory              -> {memory: [...]}
//   POST /api/memory/add          -> {ok, count, message?}
//   GET  /api/digest/             -> {digests: [...], total}
//   GET  /api/notes               -> {notes: [...]}
//   GET  /api/plans               -> bare JSON array of plans
//   GET  /api/plans/{id}          -> full plan incl. steps
//   GET  /api/companion/ping      -> {ok, name, version, auth}
//   GET  /api/companion/info      -> {name, version, owner, capabilities}
//
// NOTE vs. the original brief: the real streaming route is POST /api/chat_stream
// (routes/chat_routes.py:535) and the real memory-insert route is
// POST /api/memory/add (routes/memory/memory_routes.py:84); there is no
// GET /api/chat/stream and no bare POST /api/memory in the repo.

import { request, joinUrl } from "./client";

// ---------------------------------------------------------------------------
// tiny normalisers
// ---------------------------------------------------------------------------

function asObjectArray(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (value && Array.isArray(value.sessions)) return value.sessions;
  if (value && Array.isArray(value.memory)) return value.memory;
  if (value && Array.isArray(value.memories)) return value.memories;
  if (value && Array.isArray(value.digests)) return value.digests;
  if (value && Array.isArray(value.notes)) return value.notes;
  if (value && Array.isArray(value.plans)) return value.plans;
  if (value && typeof value === "object") {
    // Defensive: a dict keyed by id (legacy / odd shapes) -> its values.
    const out = [];
    Object.keys(value).forEach(function (k) {
      const v = value[k];
      if (v && typeof v === "object") {
        out.push(v);
      }
    });
    if (out.length) {
      return out;
    }
  }
  return [];
}

function stringField(v, fallback) {
  return typeof v === "string" ? v : fallback == null ? "" : String(fallback);
}

// ---------------------------------------------------------------------------
// Companion bridge (discovery / pairing)
// ---------------------------------------------------------------------------

// GET /api/companion/ping — auth-validated health check. 200 with ok=true
// confirms host/port + credential are valid (401 otherwise).
export async function companionPing(origin, token) {
  const data = await request(origin, "/api/companion/ping", { token: token || "" });
  return {
    ok: !!(data && data.ok),
    name: stringField(data && data.name),
    version: stringField(data && data.version),
    auth: stringField(data && data.auth),
  };
}

// GET /api/companion/info — server identity + coarse capability flags. This is
// the "Discover" call: it works with a token and (on auth-disabled servers)
// without one.
export async function companionInfo(origin, token) {
  const data = await request(origin, "/api/companion/info", { token: token || "" });
  return {
    name: stringField(data && data.name),
    version: stringField(data && data.version),
    owner: stringField(data && data.owner),
    capabilities:
      data && data.capabilities && typeof data.capabilities === "object"
        ? data.capabilities
        : {},
  };
}

// GET /api/companion/models — LLM endpoints the caller can use (needs a
// chat-scoped bearer token). Kept for a future "pick a model" screen.
export async function companionModels(origin, token) {
  const data = await request(origin, "/api/companion/models", { token: token || "" });
  const list = asObjectArray(data && data.endpoints ? { endpoints: data.endpoints } : data);
  return list.map(function (ep) {
    return {
      endpoint_id: stringField(ep && ep.endpoint_id),
      name: stringField(ep && ep.name),
      endpoint_url: stringField(ep && ep.endpoint_url),
      models: Array.isArray(ep && ep.models) ? ep.models : [],
      supports_tools: !!(ep && ep.supports_tools),
    };
  });
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

// GET /api/sessions — array of {id, name, model, endpoint_url, rag, folder,
// created_at, updated_at, last_message_at, message_count, ...}. The session id
// is REQUIRED to post a chat message, so this screen is what feeds the picker.
export async function listSessions(origin, token) {
  const data = await request(origin, "/api/sessions", { token: token || "" });
  return asObjectArray(data).map(function (s) {
    return {
      id: stringField(s && s.id),
      name: stringField(s && s.name) || stringField(s && s.id) || "(unnamed)",
      model: stringField(s && s.model),
      endpoint_url: stringField(s && s.endpoint_url),
      rag: !!(s && s.rag),
      archived: !!(s && s.archived),
      folder: s && typeof s.folder === "string" ? s.folder : null,
      is_important: !!(s && s.is_important),
      message_count: s && typeof s.message_count === "number" ? s.message_count : 0,
      created_at: stringField(s && s.created_at),
      updated_at: stringField(s && s.updated_at),
      last_message_at: stringField(s && s.last_message_at),
    };
  });
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

// POST /api/chat — non-streaming reply: {message, session} -> {"response": "..."}.
// Returns the plain reply text ("" if the server shape is unexpected).
export async function sendChatMessage(origin, token, message, sessionId) {
  const data = await request(origin, "/api/chat", {
    method: "POST",
    token: token || "",
    body: { message: message, session: sessionId },
  });
  if (data && typeof data === "object" && typeof data.response === "string") {
    return data.response;
  }
  if (typeof data === "string") {
    return data;
  }
  return "";
}

// ---------------------------------------------------------------------------
// SSE streaming (POST /api/chat_stream)
// ---------------------------------------------------------------------------

// Normalise one parsed SSE data object into {type, text, thinking, data, raw}.
// The stream is heterogeneous: plain {delta: "..."} chunks (OpenAI-style),
// typed events {type: "rag_sources"|"citations"|"metrics"|"message_saved"|...,
// data: ...}, upstream chunks forwarded verbatim, and the literal
// "data: [DONE]" terminator. We never assume a field we don't see.
export function normalizeSseEvent(obj) {
  if (obj === null || typeof obj !== "object") {
    return { type: "raw", text: "", data: obj, raw: obj };
  }
  let type = typeof obj.type === "string" && obj.type ? obj.type : null;
  let text = "";
  if (typeof obj.delta === "string") {
    type = type || "chunk";
    text = obj.delta;
  } else if (typeof obj.text === "string") {
    type = type || "chunk";
    text = obj.text;
  } else if (typeof obj.content === "string") {
    type = type || "chunk";
    text = obj.content;
  }
  if (!type) {
    type = "event";
  }
  return {
    type: type,
    text: text,
    thinking: !!(obj.thinking || (obj.type === "thinking")),
    data: obj.data !== undefined ? obj.data : obj,
    raw: obj,
  };
}

// Stream one chat turn over SSE. Requires the session id (chat is
// session-scoped server-side). handlers: {onEvent(ev), onDone(), onError(err)}.
// Returns a cancel() function. React Native's fetch cannot incrementally read
// a response body, so this uses XMLHttpRequest's progressive responseText --
// dependency-free and genuinely streaming.
//
// Wire format (verified in routes/chat_routes.py): each SSE block is
// `data: <json>\n\n`; the reply stream ends with a literal `data: [DONE]\n\n`.
// Comment/heartbeat/`event:` lines are skipped.
export function streamChatReply(origin, token, message, sessionId, handlers) {
  const h = handlers || {};
  const onEvent = typeof h.onEvent === "function" ? h.onEvent : function () {};
  const onDone = typeof h.onDone === "function" ? h.onDone : function () {};
  const onError = typeof h.onError === "function" ? h.onError : function () {};

  const url = joinUrl(origin, "/api/chat_stream");
  const xhr = new XMLHttpRequest();
  let cursor = 0;
  let finished = false;

  function finish(err) {
    if (finished) {
      return;
    }
    finished = true;
    if (err) {
      onError(err);
    } else {
      onDone();
    }
  }

  // Process one complete block ("...\n\n" delimited). Returns true when the
  // stream reached its terminator.
  function handleBlock(block) {
    const lines = String(block || "").split("\n");
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (line.slice(0, 6) === "data: ") {
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") {
          onEvent({ type: "done", text: "", data: null, raw: null });
          finish();
          return true;
        }
        if (!payload) {
          continue;
        }
        let obj = null;
        try {
          obj = JSON.parse(payload);
        } catch (e) {
          obj = { type: "error", text: "unparseable stream line", raw: payload };
        }
        onEvent(normalizeSseEvent(obj));
      }
      // "event: <name>" and ": <comment>" lines carry no payload; skip them.
    }
    return false;
  }

  function pump() {
    if (finished) {
      return;
    }
    const text = xhr.responseText || "";
    if (cursor > text.length) {
      cursor = 0; // responseText reset by the platform; restart from scratch
    }
    let stop = false;
    while (!stop && cursor < text.length) {
      const idx = text.indexOf("\n\n", cursor);
      if (idx === -1) {
        break; // incomplete block; wait for more data
      }
      const block = text.slice(cursor, idx);
      cursor = idx + 2;
      stop = handleBlock(block);
    }
  }

  xhr.open("POST", url);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.setRequestHeader("Accept", "text/event-stream");
  if (token) {
    xhr.setRequestHeader("Authorization", "Bearer " + token);
  }
  xhr.timeout = 120000;
  xhr.onreadystatechange = function () {
    // readyState 3 (LOADING) fires as chunks arrive; 4 on close.
    if (xhr.readyState >= 3) {
      pump();
    }
  };
  xhr.ontimeout = function () {
    finish(new Error("Stream timed out (no data for 120s): " + url));
  };
  xhr.onerror = function () {
    finish(new Error("Network error while streaming " + url));
  };
  xhr.onload = function () {
    pump();
    const status = xhr.status || 0;
    if (status >= 200 && status < 300) {
      finish(); // server closed the stream (normally right after [DONE])
    } else {
      const tail = String(xhr.responseText || "").slice(0, 300);
      finish(new Error("HTTP " + status + (tail ? ": " + tail : "")));
    }
  };

  try {
    xhr.send(JSON.stringify({ message: message, session: sessionId }));
  } catch (e) {
    finish(e);
  }

  return function cancel() {
    finish(new Error("Cancelled by user."));
    try {
      xhr.abort();
    } catch (e) {
      // ignore
    }
  };
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

// GET /api/memory -> {memory: [...]}. Items: id/text/category/source/
// timestamp(seconds)/uses/owner.
export async function listMemories(origin, token) {
  const data = await request(origin, "/api/memory", { token: token || "" });
  return asObjectArray(data).map(function (m) {
    return {
      id: stringField(m && m.id),
      text: stringField(m && m.text),
      category: stringField(m && m.category),
      source: stringField(m && m.source),
      timestamp: m && typeof m.timestamp === "number" ? m.timestamp : null,
      uses: m && typeof m.uses === "number" ? m.uses : 0,
    };
  });
}

// POST /api/memory/add — body {text, category?, source?}. The repo registers
// the insert under /add (routes/memory/memory_routes.py:84); a bare
// POST /api/memory does not exist. Returns the server's {ok, count, message?}.
export async function addMemory(origin, token, text, opts) {
  const o = opts || {};
  return request(origin, "/api/memory/add", {
    method: "POST",
    token: token || "",
    body: {
      text: String(text || "").trim(),
      category: o.category ? String(o.category).trim() : "fact",
      source: o.source ? String(o.source).trim() : "user",
    },
  });
}

// ---------------------------------------------------------------------------
// Digest
// ---------------------------------------------------------------------------

// GET /api/digest/ — the list route is registered as "/api/digest/"
// (routes/digest/digest_routes.py:69) and FastAPI's redirect_slashes makes
// "/api/digest" resolve to it too. Items: id/date/status/summary/content/error.
export async function listDigests(origin, token) {
  const data = await request(origin, "/api/digest/", { token: token || "" });
  return asObjectArray(data).map(function (d) {
    return {
      id: stringField(d && d.id),
      date: stringField(d && d.date),
      status: stringField(d && d.status),
      summary: stringField(d && d.summary),
      content: d && d.content !== undefined && d.content !== null ? d.content : "",
      error: stringField(d && d.error),
    };
  });
}

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

// GET /api/notes -> {notes: [...]}. Items: id/title/content/note_type/label/
// pinned/color/updated_at.
export async function listNotes(origin, token) {
  const data = await request(origin, "/api/notes", { token: token || "" });
  return asObjectArray(data).map(function (n) {
    return {
      id: stringField(n && n.id),
      title: stringField(n && n.title),
      content: n && n.content !== undefined && n.content !== null ? n.content : "",
      note_type: stringField(n && n.note_type),
      label: stringField(n && n.label),
      color: stringField(n && n.color),
      pinned: !!(n && n.pinned),
      updated_at: stringField(n && n.updated_at),
    };
  });
}

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

// GET /api/plans -> bare JSON array. Summary items carry id/title/goal/status/
// step_count/done_count/current_step_index/created_at.
export async function listPlans(origin, token) {
  const data = await request(origin, "/api/plans", { token: token || "" });
  return asObjectArray(data).map(function (p) {
    return {
      id: stringField(p && p.id),
      title: stringField(p && p.title),
      goal: stringField(p && p.goal),
      status: stringField(p && p.status),
      current_step_index:
        p && typeof p.current_step_index === "number" ? p.current_step_index : null,
      step_count: p && typeof p.step_count === "number" ? p.step_count : 0,
      done_count: p && typeof p.done_count === "number" ? p.done_count : 0,
      created_at: stringField(p && p.created_at),
    };
  });
}

// GET /api/plans/{id} -> full plan including its steps array
// ({id, title, description, status, ...} per step).
export async function fetchPlan(origin, token, planId) {
  const id = encodeURIComponent(planId);
  const data = await request(origin, "/api/plans/" + id, { token: token || "" });
  const steps = Array.isArray(data && data.steps)
    ? data.steps.map(function (s) {
        return {
          id: stringField(s && s.id),
          title: stringField(s && s.title) || stringField(s && s.description) || "(step)",
          description: stringField(s && s.description),
          status: stringField(s && s.status),
          order: s && typeof s.order === "number" ? s.order : null,
        };
      })
    : [];
  return {
    id: stringField(data && data.id),
    title: stringField(data && data.title),
    goal: stringField(data && data.goal),
    status: stringField(data && data.status),
    step_count: data && typeof data.step_count === "number" ? data.step_count : steps.length,
    done_count: data && typeof data.done_count === "number" ? data.done_count : 0,
    steps: steps,
  };
}
