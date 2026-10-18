"""Pure builders for live-indicator SSE events.

No I/O, no side effects — each function returns a JSON-serializable dict
shaped for the frontend cockpit/badge handlers. A field is None when its
source module is inactive/unknown; the frontend renders None as a muted
"—" chip (never fabricates a value).
"""

from __future__ import annotations

from typing import Any

_DRIFT_LEVELS = {"low", "med", "high"}


def normalize_drift(drift: Any) -> str | None:
    """Coerce a DriftLevel enum / string into 'low'|'med'|'high' or None."""
    if drift is None:
        return None
    raw = getattr(drift, "value", drift)
    text = str(raw).strip().lower()
    return text if text in _DRIFT_LEVELS else None


def run_status_event(
    *,
    phase: str | None,
    drift: Any,
    used: int,
    max_rounds: int,
    budget_pct: int | None,
    budget_tokens: int | None,
    phase_active: bool = False,
) -> dict:
    """Consolidated per-round status for the persistent cockpit strip.

    ``phase_active`` is True only when an orchestrator is actually driving the
    phase (ODYSSEUS_LIVE_ORCHESTRATION or ODYSSEUS_PHASE_TRACKER on). When
    False, ``phase`` is the hardcoded conservative default (BUILD/PLAN) and the
    frontend must render it neutrally, never as an active/healthy signal.
    """
    budget = None
    if budget_pct is not None or budget_tokens is not None:
        budget = {"pct": budget_pct, "tokens": budget_tokens}
    return {
        "type": "run_status",
        "phase": phase,
        "phase_active": bool(phase_active),
        "drift": normalize_drift(drift),
        "iters": {"used": used, "max": max_rounds},
        "budget": budget,
    }


def autoeval_event(*, decision: str, reason: str = "") -> dict:
    """Discrete autoeval keep/revert decision -> inline badge."""
    return {"type": "autoeval_result", "decision": decision, "reason": reason}


def verifier_event(*, reasons: Any) -> dict:
    """Discrete verifier verdict -> inline badge. Empty reasons == pass."""
    if not reasons:
        return {"type": "verifier_result", "status": "pass", "detail": ""}
    if isinstance(reasons, (list, tuple)):
        detail = "; ".join(str(r) for r in reasons[:3])
    else:
        detail = str(reasons)
    return {"type": "verifier_result", "status": "fail", "detail": detail}
