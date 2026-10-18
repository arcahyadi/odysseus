"""AgentDispatcher — auto-trigger .opencode agents at each canonical phase (M4).

Each agent is gated by its own kill-switch (default OFF). When ON, the agent
runs as an async background task via the shared task_llm_call_async. Agents
never break the loop — failures are logged and swallowed.

Explicit invocation (via /agent or /design) uses dispatch_explicit() — same
mechanism, but triggered by user command instead of phase auto-fire.

Architecture:
  Phase CLASSIFY        → constitution        (ODYSSEUS_AGENT_CONSTITUTION)
  Phase KNOW            → (none yet — CBM native)
  Phase PLAN            → gsd-planner          (ODYSSEUS_AGENT_PLANNER)
                        → gsd-researcher       (ODYSSEUS_AGENT_RESEARCHER)
  Phase BUILD           → gsd-executor         (ODYSSEUS_AGENT_EXECUTOR)
                        → gsd-debugger (fail)  (ODYSSEUS_AGENT_DEBUGGER)
  Phase QUALITY         → debate-5-personas    (ODYSSEUS_AGENT_DEBATE)
                        → security-audit       (ODYSSEUS_AGENT_SECURITY)
  Phase AUTOEVAL        → gsd-verifier         (ODYSSEUS_AGENT_VERIFIER)
                        → edge-case-gen        (ODYSSEUS_AGENT_EDGECASE)
  Phase MEMORY_OBSERVE  → gsd-roadmapper       (ODYSSEUS_AGENT_ROADMAPPER)
  Tool (explicit only)  → design-extract       (ODYSSEUS_AGENT_DESIGN_EXTRACT)
                        → open-design          (ODYSSEUS_AGENT_OPEN_DESIGN)
"""

from __future__ import annotations

import asyncio
import logging
import os

from src.orchestrator.phases import Phase

logger = logging.getLogger(__name__)

# ── Phase → agent mapping ──────────────────────────────────────────────
# Each entry: (agent_name, kill_switch_env_var)
# Agents fire in parallel within a phase via asyncio.gather.
# Each agent is isolated — a failure in one never affects the others.

_PHASE_AGENTS: dict[Phase, list[tuple[str, str]]] = {
    Phase.CLASSIFY: [
        ("constitution", "ODYSSEUS_AGENT_CONSTITUTION"),
    ],
    Phase.KNOW: [
        # CBM is native, no agent needed here (yet)
    ],
    Phase.PLAN: [
        ("gsd-planner", "ODYSSEUS_AGENT_PLANNER"),
        ("gsd-researcher", "ODYSSEUS_AGENT_RESEARCHER"),
    ],
    Phase.BUILD: [
        ("gsd-executor", "ODYSSEUS_AGENT_EXECUTOR"),
    ],
    Phase.QUALITY: [
        ("debate-5-personas", "ODYSSEUS_AGENT_DEBATE"),
        ("security-audit", "ODYSSEUS_AGENT_SECURITY"),
    ],
    Phase.AUTOEVAL: [
        ("gsd-verifier", "ODYSSEUS_AGENT_VERIFIER"),
        ("edge-case-gen", "ODYSSEUS_AGENT_EDGECASE"),
    ],
    Phase.MEMORY_OBSERVE: [
        ("gsd-roadmapper", "ODYSSEUS_AGENT_ROADMAPPER"),
    ],
}

# Explicit-invocation-only agents (not phase-tied).
_EXPLICIT_AGENTS: dict[str, str] = {
    "design-extract": "ODYSSEUS_AGENT_DESIGN_EXTRACT",
    "open-design": "ODYSSEUS_AGENT_OPEN_DESIGN",
    # Orchestrators re-exposed for explicit /agent invocation:
    "gsd-planner": "ODYSSEUS_AGENT_PLANNER",
    "gsd-researcher": "ODYSSEUS_AGENT_RESEARCHER",
    "gsd-executor": "ODYSSEUS_AGENT_EXECUTOR",
    "gsd-debugger": "ODYSSEUS_AGENT_DEBUGGER",
    "gsd-verifier": "ODYSSEUS_AGENT_VERIFIER",
    "gsd-roadmapper": "ODYSSEUS_AGENT_ROADMAPPER",
}


def _is_enabled(env_var: str) -> bool:
    val = os.getenv(env_var, "off").strip().lower()
    return val in ("on", "1", "true", "yes")


class AgentDispatcher:
    """Dispatches .opencode agents by phase or explicit command."""

    def __init__(self, registry=None):
        self._registry = registry  # AgentRegistry instance (lazy)
        self._running: dict[str, asyncio.Task] = {}

    # ── lazy registry ──────────────────────────────────────────────────
    def _get_registry(self):
        if self._registry is not None:
            return self._registry
        # Try to get the app.state catalog if available
        try:
            from app import app as _app  # noqa: F401 — avoid circular

            catalog = getattr(_app.state, "agent_catalog", None)
            if catalog is not None:
                self._registry = catalog
                return self._registry
        except Exception:
            pass
        # Fallback: discover directly (slower, but works)
        try:
            from src.orchestrator.registry import AgentRegistry

            self._registry = AgentRegistry().discover()
            return self._registry
        except Exception:
            return None

    # ── phase dispatch ─────────────────────────────────────────────────
    def agents_for_phase(self, phase: Phase) -> list[str]:
        """Return enabled agent names for the given phase."""
        entries = _PHASE_AGENTS.get(phase, [])
        return [name for name, env_var in entries if _is_enabled(env_var)]

    async def dispatch_for_phase(
        self, phase: Phase, session_id: str, context: str | None = None, on_event: callable | None = None
    ):
        """Fire all enabled agents for this phase IN PARALLEL (best-effort).

        Each agent runs concurrently via asyncio.gather. Failures are isolated —
        a crash in one agent never affects the others. If *on_event* is provided,
        it is called with ``{type, agent, phase, status}`` for each agent as it
        completes (or fails).
        """
        agent_names = self.agents_for_phase(phase)
        if not agent_names:
            return

        try:
            registry = self._get_registry()
        except Exception:
            logger.debug("[AgentDispatcher] registry unavailable, skipping phase %s", phase.value)
            return

        if registry is None:
            logger.debug("[AgentDispatcher] no registry available, skipping phase %s", phase.value)
            return

        async def _run_one(name: str):
            spec = registry.get(name) if hasattr(registry, "get") else None
            if spec is None:
                logger.warning("[AgentDispatcher] agent %r not found in registry", name)
                return None
            try:
                result = await self._run_agent(spec, phase.value, session_id, context)
                if on_event:
                    on_event(
                        {
                            "type": "agent_dispatch",
                            "agent": name,
                            "phase": phase.value,
                            "status": "completed",
                            "result_len": len(str(result)) if result else 0,
                        }
                    )
                return result
            except Exception as exc:
                logger.warning(
                    "[AgentDispatcher] agent %r failed for phase %s: %s",
                    name,
                    phase.value,
                    exc,
                )
                if on_event:
                    on_event(
                        {
                            "type": "agent_dispatch",
                            "agent": name,
                            "phase": phase.value,
                            "status": "failed",
                            "error": str(exc)[:200],
                        }
                    )
                return None

        # Launch all agents in parallel — each isolated from the others
        await asyncio.gather(*(_run_one(name) for name in agent_names), return_exceptions=True)

    # ── explicit dispatch ──────────────────────────────────────────────
    def explicit_enabled(self, agent_name: str) -> bool:
        """Check if an explicit-invocation agent is enabled."""
        env_var = _EXPLICIT_AGENTS.get(agent_name)
        if env_var is None:
            return False
        return _is_enabled(env_var)

    def list_explicit_agents(self) -> list[str]:
        """List all currently enabled explicit-invocation agents."""
        return [name for name in _EXPLICIT_AGENTS if self.explicit_enabled(name)]

    async def dispatch_explicit(self, agent_name: str, session_id: str, context: str | None = None):
        """Fire an agent explicitly (user command /agent or /design)."""
        if not self.explicit_enabled(agent_name):
            raise ValueError(
                f"Agent {agent_name!r} is not enabled. Set {_EXPLICIT_AGENTS.get(agent_name, 'the kill-switch')}=on"
            )

        registry = self._get_registry()
        if registry is None:
            raise RuntimeError("Agent catalog not loaded — set ODYSSEUS_AGENT_CATALOG=on")

        spec = registry.get(agent_name) if hasattr(registry, "get") else None
        if spec is None:
            raise ValueError(f"Agent {agent_name!r} not found in catalog")

        return await self._run_agent(spec, "explicit", session_id, context)

    # ── internal: run one agent ────────────────────────────────────────
    async def _run_agent(self, spec, trigger: str, session_id: str, context: str | None = None):
        """Run a single agent as a background LLM call. Never raises."""
        try:
            from src.task_endpoint import task_llm_call_async
        except ImportError:
            logger.warning("[AgentDispatcher] task_endpoint not available, cannot run agent %s", spec.name)
            return

        prompt = spec.prompt or spec.description or f"Agent: {spec.name}"
        user_message = context or f"Triggered by phase: {trigger}"

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ]

        logger.info(
            "[AgentDispatcher] spawning %s | trigger=%s | session=%s",
            spec.name,
            trigger,
            session_id,
        )

        try:
            result = await task_llm_call_async(messages, owner=session_id)
            logger.info(
                "[AgentDispatcher] %s completed | trigger=%s | result_len=%d",
                spec.name,
                trigger,
                len(str(result)) if result else 0,
            )
            return result
        except Exception as exc:
            logger.warning(
                "[AgentDispatcher] %s call failed | trigger=%s | %s: %s",
                spec.name,
                trigger,
                type(exc).__name__,
                exc,
            )
            return None
