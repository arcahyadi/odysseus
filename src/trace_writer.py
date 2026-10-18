"""
trace_writer.py

Thread-safe JSONL trace writer AND reader for the agent loop.
Writes structured traces to data/traces/YYYY-MM-DD.jsonl.

Each line is a JSON object with:
  ts, run_id, session_id, kind
plus, for kind == "tool":
  tool, risk_level, args_summary, permission_decision, outcome,
  cost_tokens, duration_ms
or, for kind == "decision":
  decision, verifier_reasons, drift_level, reverted, error

The reader exists because a trail nobody can read is not an audit. It was
added together with `write_decision` (Sprint 3 v5, item 9 / UC-12): before
that, `write_trace` was the only public function of this module, so the
145 KB of JSONL under data/traces/ were write-only — and the AUTOEVAL
decision was not written at all, only streamed, so a client that
disconnected lost it.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Upper bound on how many records a single read may return. Applied server-side:
# a limit the caller can raise past is not a limit. 500 keeps a full tool-heavy
# day readable in one call while bounding the response.
MAX_READ_LIMIT = 500
DEFAULT_READ_LIMIT = 200

# ---------------------------------------------------------------------------
# run_id — correlation id shared by every trace/metric of a single run.
#
# A "run" = one agent-loop invocation (one chat turn or one orchestrated
# dispatch). It is held in a ContextVar so concurrent requests (each its own
# asyncio task) get an isolated id without threading it through call sites.
# The module-level default keeps pre-scope behaviour byte-compatible: until a
# caller opens a run scope, current_run_id() returns this single process id
# exactly like the old constant did.
# ---------------------------------------------------------------------------
_PROCESS_RUN_ID = str(uuid.uuid4())
_run_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_run_id", default=_PROCESS_RUN_ID)

# ---------------------------------------------------------------------------
# Thread-safe write lock (per-file)
# ---------------------------------------------------------------------------
_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_lock(path: str) -> threading.Lock:
    with _locks_mutex:
        if path not in _locks:
            _locks[path] = threading.Lock()
        return _locks[path]


# ---------------------------------------------------------------------------
# Traces directory
# ---------------------------------------------------------------------------


def _jour_valide(day: str) -> bool:
    """True only for a bare `YYYY-MM-DD` stem.

    `strptime` alone is not enough: it would not be reached for a value like
    `2024-01-01/../../x`, and a strict shape check costs nothing. The rule is
    "a date, nothing else", so a separator, a dot and a letter are all refusals.
    """
    if not isinstance(day, str) or len(day) != 10:
        return False
    if day[4] != "-" or day[7] != "-":
        return False
    if not (day[:4] + day[5:7] + day[8:]).isdigit():
        return False
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _traces_dir() -> Path:
    """Return the traces directory, creating it if needed."""
    traces = _traces_dir_path()
    traces.mkdir(parents=True, exist_ok=True)
    return traces


def _traces_dir_path() -> Path:
    """Return the traces directory WITHOUT creating it.

    Split from `_traces_dir` on purpose: a read must not bring a directory
    into existence. An audit route that creates what it inspects makes "the
    trail is empty" indistinguishable from "the trail does not exist yet".
    """
    try:
        from src.constants import DATA_DIR

        base = Path(DATA_DIR)
    except Exception:
        base = Path(__file__).parent.parent / "data"
    return base / "traces"


def _today_file() -> Path:
    """Return today's JSONL trace file path."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return _traces_dir() / f"{today}.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_trace(
    *,
    tool: str,
    risk_level: str,
    args_summary: str,
    permission_decision: str,  # "auto_approved" | "gate_required" | "approved" | "rejected"
    outcome: str,  # "success" | "error" | "rejected"
    session_id: str | None = None,
    cost_tokens: int = 0,
    duration_ms: int = 0,
    extra: dict | None = None,
) -> None:
    """Write a single trace entry to today's JSONL file.

    Thread-safe. Never raises — errors are logged at WARNING level so they
    never break the agent loop.
    """
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": _run_id_var.get(),
            "session_id": session_id or "",
            "kind": "tool",
            "tool": tool,
            "risk_level": risk_level,
            "args_summary": args_summary,
            "permission_decision": permission_decision,
            "outcome": outcome,
            "cost_tokens": cost_tokens,
            "duration_ms": duration_ms,
        }
        if extra:
            record.update(extra)

        line = json.dumps(record, ensure_ascii=False) + "\n"
        fpath = str(_today_file())
        lock = _get_lock(fpath)
        with lock, open(fpath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        logger.warning("trace_writer: failed to write trace for tool=%s: %s", tool, exc)


def write_decision(
    *,
    decision: str,
    verifier_reasons: list | None = None,
    drift_level=None,
    reverted: bool = False,
    error: str | None = None,
    session_id: str | None = None,
    reasons_omitted: str | None = None,
) -> None:
    """Record a KEEP/REVERT decision in the same trail as the tool traces.

    Why this exists: `apply_autoeval` returns an `AutoevalDecision` that the loop
    logs and puts in the SSE stream — and that is all. Once the client
    disconnects the decision is gone, and no reader could have recovered it
    because nothing was written. An audit trail that loses its own decisions is
    not a trail.

    `verifier_reasons` is the *why*, so it is stored, not summarised away: an
    audit that records "revert" without a reason is indistinguishable from a
    bug. `reverted` and `error` record what actually happened, which is a
    strictly stronger claim than the decision itself — AUTOEVAL decides
    "revert" by default while `ODYSSEUS_AUTOEVAL_ALLOW_RESET` stays OFF, so
    "revert, not reverted" is the honest normal state and must be visible as
    such.

    Same guarantees as `write_trace`: thread-safe, never raises.

    `reasons_omitted` is the honest way to record a withheld reason. When the
    turn was classified PROTECTED (P17), the caller passes the reasons as
    `None`-equivalent and names the reason here, so the audit reads "there was
    a reason, withheld" instead of "there was no reason" — the two are very
    different findings and only the second is a lie.
    """
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": _run_id_var.get(),
            "session_id": session_id or "",
            "kind": "decision",
            "decision": decision,
            "verifier_reasons": list(verifier_reasons or []),
            "drift_level": getattr(drift_level, "value", drift_level),
            "reverted": bool(reverted),
            "error": error,
            "reasons_omitted": reasons_omitted,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        fpath = str(_today_file())
        lock = _get_lock(fpath)
        with lock, open(fpath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        logger.warning("trace_writer: failed to write decision=%s: %s", decision, exc)


def write_alert(
    alert: str,
    *,
    level: str = "warning",
    severity: int = 0,
    session_id: str | None = None,
    detail: dict | None = None,
) -> None:
    """Record an alert on the same trail, under `kind: "alert"`.

    An alert is not a status and not a log line. A status is read among others; a
    log line is read by nobody during a run. What makes an alert an alert is that
    it is **retrievable later** — the client that would have shown it may already
    be gone, and that is the normal case, not the exception (item 9 measured it).

    `detail` carries the cause and the recommended action. A level alone forces the
    reader to redo the computation that produced it, which is how an alert becomes
    a chore nobody reads.

    P17: this record is metadata about a run — levels, scores, booleans, run ids.
    It never carries user text, so it is not gated on the classification verdict.
    The caller is responsible for that claim, and `write_trace`'s own callers show
    what a violation looks like. Nothing here sanitises: a sanitiser added at the
    single choke point would protect tool arguments, but this record is built by
    this function from its own arguments only, and callers pass a summary object
    they computed. If that changes, the gate belongs at the call site.
    """
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": _run_id_var.get(),
            "session_id": session_id or "",
            "kind": "alert",
            "alert": alert,
            "level": level,
            "severity": int(severity),
            "detail": detail or {},
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        fpath = str(_today_file())
        lock = _get_lock(fpath)
        with lock, open(fpath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        logger.warning("trace_writer: failed to write alert=%s: %s", alert, exc)


def read_traces(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    kind: str | None = None,
    limit: int = DEFAULT_READ_LIMIT,
    day: str | None = None,
) -> tuple[list[dict], int]:
    """Read back the trail. Returns ``(records, malformed)``.

    `records` is in chronological order and holds the **last** `limit` matching
    records — the ones an audit actually wants. `limit` is clamped to
    `MAX_READ_LIMIT`; a caller asking for more gets less, silently but safely.

    `malformed` counts lines that could not be parsed. A JSONL file ends on a
    half-written line whenever a process dies inside `f.write`, so this is the
    *expected* case, not corruption — but it must be reported rather than
    dropped: a reader that silently skips torn lines shows a cleaner audit than
    reality, and the person relying on it is exactly the person an audit exists
    for.

    Only the traces directory is read. This function is not a file browser: it
    resolves exactly one dated file under `DATA_DIR/traces` and never
    interpolates a caller-supplied path. `day` is therefore validated as a bare
    `YYYY-MM-DD` **here**, where the path is built — a stem carrying a
    separator or a dot-dot would leave the traces directory, and the only
    correct place to forbid that is next to the concatenation.
    """
    limit = max(1, min(int(limit), MAX_READ_LIMIT))
    if day is not None and not _jour_valide(day):
        raise ValueError(f"day must be YYYY-MM-DD, got {day!r}")
    fichier = _traces_dir_path() / (f"{day}.jsonl" if day else f"{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl")

    if not fichier.is_file():
        return [], 0

    malformes = 0
    retenus: deque[dict] = deque(maxlen=limit)
    try:
        with open(fichier, encoding="utf-8") as f:
            for brute in f:
                ligne = brute.strip()
                if not ligne:
                    continue
                try:
                    record = json.loads(ligne)
                except ValueError:
                    malformes += 1
                    continue
                if not isinstance(record, dict):
                    malformes += 1
                    continue
                if run_id and record.get("run_id") != run_id:
                    continue
                if session_id and record.get("session_id") != session_id:
                    continue
                if kind and record.get("kind") != kind:
                    continue
                retenus.append(record)
    except OSError as exc:
        logger.warning("trace_writer: failed to read %s: %s", fichier, exc)
        return [], malformes

    return list(retenus), malformes


# ---------------------------------------------------------------------------
# Unified token accounting (M3.X) — authoritative per-run token totals.
#
# Tokens were historically counted in ~5 divergent places (cartography risk #1).
# The single WRITER OF TRUTH is the final metrics dict from
# agent_loop._compute_final_metrics (it lands in chat_messages.meta_data). That
# writer publishes its authoritative per-run totals here, keyed by run_id, so
# secondary writers (e.g. routes.chat_helpers.accumulate_token_usage) can
# RECONCILE against them instead of writing their own numbers.
#
# Kill-switch: ODYSSEUS_UNIFIED_TOKENS, default OFF (mirrors
# orchestrator.phase_tracker.tracker_enabled). When OFF, nobody reads this
# registry and behaviour is byte-identical to before. Best-effort throughout:
# recording/reading must never raise into the agent loop.
# ---------------------------------------------------------------------------
_RUN_TOKENS_CAP = 4096  # bound memory: forget oldest runs beyond this many
_run_tokens: dict[str, dict] = {}
_run_tokens_lock = threading.Lock()


def unified_tokens_enabled() -> bool:
    """OFF unless ODYSSEUS_UNIFIED_TOKENS is set to a truthy value."""
    val = os.getenv("ODYSSEUS_UNIFIED_TOKENS", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


def record_run_tokens(run_id, input_tokens=0, output_tokens=0) -> None:
    """Publish the authoritative token totals for a run (writer of truth).

    Last-write-wins: the final metrics dict holds the run TOTAL, so re-recording
    overwrites rather than accumulating. Never raises.
    """
    try:
        if not run_id:
            return
        entry = {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
        }
        with _run_tokens_lock:
            _run_tokens[str(run_id)] = entry
            if len(_run_tokens) > _RUN_TOKENS_CAP:
                # dict preserves insertion order — drop the oldest.
                for old in list(_run_tokens.keys())[: len(_run_tokens) - _RUN_TOKENS_CAP]:
                    _run_tokens.pop(old, None)
    except Exception as exc:
        logger.warning("trace_writer: failed to record run tokens for run=%s: %s", run_id, exc)


def get_run_tokens(run_id) -> dict | None:
    """Return {'input_tokens', 'output_tokens'} for a run, or None if unknown.

    Never raises.
    """
    try:
        if not run_id:
            return None
        with _run_tokens_lock:
            entry = _run_tokens.get(str(run_id))
        return dict(entry) if entry is not None else None
    except Exception:
        return None


def current_run_id() -> str:
    """Return the run id in effect for the current context."""
    return _run_id_var.get()


def set_run_id(run_id: str) -> str:
    """Set the run id for the current context. Returns the value set."""
    _run_id_var.set(run_id)
    return run_id


def new_run_id() -> str:
    """Start a fresh run: generate a new UUID, make it current, return it."""
    return set_run_id(str(uuid.uuid4()))
