// Tiny pure-JS formatting helpers shared by screens. No JSX, no RN imports,
// so it can be sanity-checked with `node --check`.

function pad2(n) {
  return n < 10 ? "0" + n : "" + n;
}

// Format unix-seconds OR unix-ms OR an ISO string into "YYYY-MM-DD HH:MM".
export function fmtTimestamp(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    value = parseInt(value.trim(), 10);
  }
  if (typeof value === "number") {
    // Unix seconds are ~1e9..1e11; ms timestamps are ~1e12..1e13.
    const ms = value < 1e12 ? value * 1000 : value;
    const d = new Date(ms);
    if (!Number.isNaN(d.getTime())) {
      return (
        d.getFullYear() +
        "-" + pad2(d.getMonth() + 1) +
        "-" + pad2(d.getDate()) +
        " " + pad2(d.getHours()) +
        ":" + pad2(d.getMinutes())
      );
    }
    return String(value);
  }
  if (value instanceof Date) {
    return fmtTimestamp(value.getTime());
  }
  // Assume an ISO-8601 string the server already produced.
  return String(value);
}

// Shorten long text while keeping whole words where easy.
export function excerpt(value, maxLength) {
  const n = maxLength || 160;
  if (value === null || value === undefined) {
    return "";
  }
  const t = String(value);
  if (t.length <= n) {
    return t;
  }
  return t.slice(0, n).trimEnd() + "\u2026";
}

// Render a value that may be a plain string or structured JSON as display text.
export function asText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (e) {
    return String(value);
  }
}

// "in_progress" -> "In Progress", "queued" -> "Queued", etc.
export function humanStatus(value) {
  if (value === null || value === undefined) {
    return "unknown";
  }
  const s = String(value).replace(/[_-]+/g, " ").trim();
  if (!s) {
    return "unknown";
  }
  return s.replace(/\b\w/g, function (c) {
    return c.toUpperCase();
  });
}

// Best-effort error message extraction from anything thrown by the API layer.
export function errMsg(error, fallback) {
  if (!error) {
    return fallback || "Something went wrong.";
  }
  if (typeof error === "string") {
    return error;
  }
  if (error && error.message) {
    return String(error.message);
  }
  return fallback || "Something went wrong.";
}
