"""Pure resolution of the live loop's current canonical Phase.

Behavior-preserving extraction of the inline branch previously in
stream_agent_loop (src/agent_loop.py). No side effects: reads only. Returns
exactly the same Phase | None the inline block returned for the same inputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.orchestrator.phases import Phase

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids import at runtime
    from src.orchestrator.loop import CanonicalLoop


def resolve_current_phase(
    use_canonical: bool,
    canonical_loop: CanonicalLoop | None,
    phase_tracker: Any | None,
    round_num: int,
    intent: dict | None = None,
    plan_mode: bool = False,
) -> Phase | None:
    """Return the canonical Phase for this round, or None.

    Mirrors exactly the prior inline logic:
      - canonical active and present → the loop's current Phase;
      - else PhaseTracker present → its inferred phase name coerced to Phase
        (None if the name is not a valid Phase value);
      - else None.
    """
    if use_canonical and canonical_loop is not None:
        return canonical_loop.current
    if phase_tracker is not None:
        pt_phase = phase_tracker.infer_phase(round_num, intent=intent, plan_mode=plan_mode)
        try:
            return Phase(pt_phase) if pt_phase in {p.value for p in Phase} else None
        except Exception:
            return None
    return None
