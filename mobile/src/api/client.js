// src/api/client.js
//
// Thin HTTP + config-storage layer for the Odysseus mobile app.
// Pure JavaScript (no JSX) so it can be syntax-checked with `node --check`.
//
// Auth model: the app talks to a self-hosted Odysseus server on the LAN over
// plain HTTP(S). When a Bearer API token (ody_...) is configured it is sent on
// every request as `Authorization: Bearer ody_...`. Tokens are created on the
// server under Settings -> API tokens, or via the web "Pair a device" page
// (POST /api/companion/pair, admin only) which mints a chat-scoped code.
//
// Storage: config (server origin + token + discovered server info) is kept in
// AsyncStorage when the native module is available, with a plain in-memory
// object as fallback (web preview / module missing). The in-memory fallback
// deliberately loses data on restart -- pairing is one tap anyway.

const STORAGE_KEY = "odysseus.mobile.config.v1";

export const DEFAULT_CONFIG = {
  origin: "", // e.g. "http://192.168.1.50:7000"
  token: "", // e.g. "ody_..."
  serverName: "",
  serverVersion: "",
  owner: "",
  capabilities: {}, // { chat: true, streaming: true, ... } from /api/companion/info
};

// ---------------------------------------------------------------------------
// Config store
// ---------------------------------------------------------------------------

let memoryFallback = Object.assign({}, DEFAULT_CONFIG);

// Lazy, guarded require: if @react-native-async-storage is not installed the
// rest of the app still works against the in-memory fallback.
function getAsyncStorage() {
  try {
    const mod = require("@react-native-async-storage/async-storage");
    return mod && mod.default ? mod.default : mod;
  } catch (e) {
    return null;
  }
}

export async function loadConfig() {
  try {
    const store = getAsyncStorage();
    if (store && typeof store.getItem === "function") {
      const raw = await store.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") {
          memoryFallback = Object.assign({}, DEFAULT_CONFIG, parsed);
          return Object.assign({}, memoryFallback);
        }
      }
    }
  } catch (e) {
    // Fall through to the in-memory snapshot.
  }
  return Object.assign({}, DEFAULT_CONFIG, memoryFallback);
}

// Merge `patch` into the stored config and persist.
export async function saveConfig(patch) {
  const current = await loadConfig();
  const next = Object.assign({}, current, patch || {});
  memoryFallback = next;
  try {
    const store = getAsyncStorage();
    if (store && typeof store.setItem === "function") {
      await store.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  } catch (e) {
    // Non-fatal: pairing still proceeds, value just won't survive restart.
  }
  return Object.assign({}, next);
}

export async function clearConfig() {
  memoryFallback = Object.assign({}, DEFAULT_CONFIG);
  try {
    const store = getAsyncStorage();
    if (store && typeof store.removeItem === "function") {
      await store.removeItem(STORAGE_KEY);
    }
  } catch (e) {
    // ignore
  }
  return Object.assign({}, DEFAULT_CONFIG);
}

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------

// Accept "192.168.1.5:7000", "http://host:7000/" etc. -> "http://host:7000".
export function normalizeOrigin(raw) {
  const s = String(raw == null ? "" : raw).trim();
  if (!s) {
    return "";
  }
  const withScheme = /^https?:\/\//i.test(s) ? s : "http://" + s;
  return withScheme.replace(/\/+$/, "");
}

export function joinUrl(origin, path) {
  const base = normalizeOrigin(origin);
  if (!base) {
    throw new Error("No server URL configured. Pair with a server first.");
  }
  const p = "/" + String(path == null ? "" : path).replace(/^\/+/, "");
  return base + p;
}

// ---------------------------------------------------------------------------
// fetch wrapper
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(status, message, detail) {
    super(message || (status ? "Request failed (HTTP " + status + ")" : "Request failed"));
    this.name = "ApiError";
    this.status = status; // 0 = network/timeout, else HTTP status
    this.detail = detail; // parsed server detail (often the {"detail": ...} body)
  }
}

function readMessage(data, text) {
  if (data && typeof data === "object") {
    if (typeof data.detail === "string" && data.detail) {
      return data.detail;
    }
    if (typeof data.message === "string" && data.message) {
      return data.message;
    }
    if (typeof data.error === "string" && data.error) {
      return data.error;
    }
  }
  const trimmed = String(text || "").trim();
  return trimmed ? trimmed.slice(0, 300) : "";
}

// Core request helper. Body (object) is JSON-encoded. Returns parsed JSON when
// possible, otherwise the raw text. Throws ApiError on network failure or any
// non-2xx response.
export async function request(origin, path, opts) {
  const o = opts || {};
  const method = o.method || "GET";
  const body = o.body === undefined ? null : o.body;
  const token = o.token || "";
  const timeoutMs = o.timeoutMs || 20000;

  const url = joinUrl(origin, path);

  const headers = {
    Accept: "application/json",
  };
  if (body !== null && body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = "Bearer " + token;
  }

  // AbortController for timeouts (supported in RN 0.60+).
  let controller = null;
  let timer = null;
  if (typeof AbortController === "function") {
    controller = new AbortController();
    timer = setTimeout(function () {
      try {
        controller.abort();
      } catch (e) {
        // ignore
      }
    }, timeoutMs);
  }

  let res;
  try {
    res = await fetch(url, {
      method: method,
      headers: headers,
      body: body === null || body === undefined ? undefined : JSON.stringify(body),
      signal: controller ? controller.signal : undefined,
    });
  } catch (e) {
    if (controller && e && e.name === "AbortError") {
      throw new ApiError(0, "Request timed out after " + timeoutMs + "ms: " + url);
    }
    const why = e && e.message ? e.message : String(e);
    throw new ApiError(0, "Network error reaching " + url + (why ? " (" + why + ")" : ""));
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }

  const text = await res
    .text()
    .then(function (t) {
      return t;
    })
    .catch(function () {
      return "";
    });

  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = text; // non-JSON body (HTML error page, plain text, ...)
    }
  }

  if (!res.ok) {
    const message = readMessage(data, text) || "HTTP " + res.status;
    throw new ApiError(res.status, message, data);
  }

  return data;
}
