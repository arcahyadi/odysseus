"""Model resolution for an agent spec (Milestone 2, P1 slice).

Resolves WHICH model an agent should run on. `resolve_model` takes an INJECTED,
duck-typed `router` (`.route(intent_category, stage)`) — it does not import any
concrete router. The redundant ModelRouter was removed (M3.1); callers pass the
native resolver or leave `router=None` to fall back to the session default.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.orchestrator.loop import CanonicalLoop
from src.orchestrator.spec import AgentSpec

logger = logging.getLogger(__name__)


def resolve_model(spec: AgentSpec, router=None, stage: str | None = None) -> str | None:
    """Resolve the LiteLLM model string for an agent.

    Priority:
      1. spec.model (explicit override in the agent frontmatter)
      2. router.route(intent_category="utility", stage=stage)
      3. None (caller falls back to the session's default model)
    """
    if spec.model:
        logger.debug("[dispatcher] %s uses explicit model %s", spec.name, spec.model)
        return spec.model

    if router is not None:
        model = router.route(intent_category="utility", stage=stage)
        logger.info("[dispatcher] %s routed to %s (stage=%s)", spec.name, model, stage)
        return model

    logger.debug("[dispatcher] %s has no model and no router; returning None", spec.name)
    return None


@dataclass
class DispatchResult:
    agent: str
    model: str | None
    phases_run: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    completed: bool = False


def dispatch(
    spec: AgentSpec,
    objective: str,
    *,
    session_id: str,
    registry=None,
    router=None,
    stage: str | None = None,
    runner: Callable | None = None,
) -> DispatchResult:
    """Run `objective` for `spec` through the canonical 7-phase loop.

    This is an ORCHESTRATED run — isolated from the live chat path. For each
    phase it (1) applies the phase to the phase-lock registry for `session_id`,
    then (2) invokes the injected `runner(phase, spec, objective, model)` to do
    the work. The runner is injected so this coordinator is fully unit-testable;
    a real stream_agent_loop-backed runner lands in a later phase.
    """
    model = resolve_model(spec, router=router, stage=stage)
    loop = CanonicalLoop(session_id, registry=registry)

    result = DispatchResult(agent=spec.name, model=model)
    while True:
        loop.apply()
        phase = loop.current
        result.phases_run.append(phase.name)
        if runner is not None:
            result.outputs[phase.name] = runner(phase=phase, spec=spec, objective=objective, model=model)
        if not loop.advance():
            break

    result.completed = True
    return result



def _reset_caches() -> None:
    """Vide les caches de ce module. Pour l'isolation des tests (MOD-3).

    Ce module n'a pas de cache propre (il délègue à endpoint_resolver),
    mais la fonction existe pour l'isolation des tests (MOD-3)."""
    pass
