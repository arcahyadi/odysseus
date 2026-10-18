"""checkpoint_tracker — kill-switched bridge that persists a run checkpoint at
MEMORY_OBSERVE (M3.2 Trinité checkpoint).

Native mapping (native-first, zero redundancy)
----------------------------------------------
The roadmap names a "Trinité checkpoint". The native one
(``routes.knowledge_routes.trinite_checkpoint``) is a PRE-GENERATION READ: it
fuses CBM + VectorRAG + Obsidian context to enrich a generation. It persists
nothing and takes no run state, so it cannot be reused for the chosen POST-ROUND
design (capture session_id, run_id, final metrics summary, outcome at session
end) without misusing it. The correct native substrate for a post-round WRITE is
the Obsidian memory leg — the same Trinité store the native checkpoint reads —
whose write primitive is ``mcp_servers.obsidian_mcp.create_note(path, content)``.
This module persists ONE checkpoint note there, reusing that primitive.

SAFETY: OFF by default (ODYSSEUS_CHECKPOINT). When OFF, nothing is written and
live behaviour is byte-identical. When ON, one checkpoint note is written via the
native Obsidian primitive. Best-effort: any fault is swallowed so it can never
break the loop.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Keep the persisted metrics summary bounded so a large metrics dict never bloats
# the note. Only the first N keys survive; the JSON is capped by MAX_METRICS_CHARS.
MAX_METRICS_KEYS = 40
MAX_METRICS_CHARS = 4000


def checkpoint_enabled() -> bool:
    """OFF unless ODYSSEUS_CHECKPOINT is set to a truthy value."""
    val = os.getenv("ODYSSEUS_CHECKPOINT", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


def _summarize_metrics(metrics) -> dict:
    """Return a bounded, JSON-safe summary of the run metrics."""
    if not isinstance(metrics, dict):
        return {}
    summary: dict = {}
    for i, (k, v) in enumerate(metrics.items()):
        if i >= MAX_METRICS_KEYS:
            summary["_truncated"] = True
            break
        try:
            json.dumps(v)
            summary[str(k)] = v
        except (TypeError, ValueError):
            summary[str(k)] = str(v)
    # Hard char cap: if still too big, drop values, keep keys.
    if len(json.dumps(summary, default=str)) > MAX_METRICS_CHARS:
        summary = {"_keys": list(summary.keys())[:MAX_METRICS_KEYS], "_truncated": True}
    return summary


def _render_note(payload: dict) -> str:
    """Render the checkpoint as a markdown note with an embedded JSON block."""
    body = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    return (
        f"# Checkpoint {payload.get('run_id', '')}\n\n"
        f"- session: {payload.get('session_id', '')}\n"
        f"- outcome: {payload.get('outcome', '')}\n"
        f"- at: {payload.get('created_at', '')}\n\n"
        f"```json\n{body}\n```\n"
    )


def record_checkpoint(
    *,
    session_id: str,
    run_id: str | None,
    metrics: dict | None,
    outcome: str = "completed",
    enabled: bool | None = None,
    backend=None,
) -> dict | None:
    """Persist ONE run checkpoint via the native Obsidian memory primitive.

    No-op (returns None) when the kill-switch is OFF. Otherwise builds a bounded
    checkpoint record (session_id, run_id, metrics summary, outcome, timestamp)
    and writes it as a note through ``backend.create_note(path, content)``.

    ``backend`` is injectable for tests; when None the native
    ``mcp_servers.obsidian_mcp`` module (which exposes create_note) is used.

    Never raises — checkpointing is observational and must not break the loop.
    """
    is_enabled = checkpoint_enabled() if enabled is None else bool(enabled)
    if not is_enabled:
        return None

    try:
        vault = backend
        if vault is None:
            # Lazy import so importing this module never forces the MCP dep.
            from mcp_servers import obsidian_mcp as vault  # type: ignore

        created_at = datetime.now(UTC).isoformat()
        payload = {
            "session_id": session_id,
            "run_id": run_id,
            "outcome": outcome,
            "created_at": created_at,
            "metrics": _summarize_metrics(metrics),
        }
        stamp = created_at.replace(":", "").replace("-", "")
        rid = (run_id or "run")[:12]
        sid = (session_id or "live")[:16]
        path = f"agentos/checkpoints/{stamp}-{sid}-{rid}.md"
        content = _render_note(payload)

        result = vault.create_note(path, content)
        if isinstance(result, dict) and not result.get("error"):
            logger.info(
                "[checkpoint] recorded session=%s run=%s outcome=%s path=%s",
                session_id,
                run_id,
                outcome,
                path,
            )
        return result
    except Exception as exc:
        logger.debug("[checkpoint] record ignoré : %s", exc)
        return None
