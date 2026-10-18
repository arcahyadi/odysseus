"""Native orchestration layer for Odysseus (Milestone 2)."""

from src.orchestrator.autoeval import (
    AutoevalDecision,
    apply_autoeval,
    autoeval_enabled,
    decide_keep_or_revert,
)
from src.orchestrator.autoevolve import (
    autoevolve_enabled,
    maybe_autoevolve,
    trigger_improvement_research,
)
from src.orchestrator.dispatcher import DispatchResult, dispatch, resolve_model
from src.orchestrator.gate import gate_enabled, should_block_destructive
from src.orchestrator.loop import CanonicalLoop
from src.orchestrator.phase_tracker import PhaseTracker, tracker_enabled
from src.orchestrator.phases import CANONICAL_SEQUENCE, Phase, forced_tools, phase_lock_name
from src.orchestrator.registry import AgentRegistry
from src.orchestrator.router_advice import advise, router_enabled
from src.orchestrator.spec import AgentSpec, parse_agent_spec

# LangGraph imports are lazy — only available when langgraph is installed.
try:
    from src.orchestrator.langgraph_loop import (
        AgentState,
        build_input_state,
        build_langgraph,
        langgraph_enabled,
        langgraph_stream,
    )
except ImportError:
    langgraph_enabled = None  # type: ignore
    build_langgraph = None  # type: ignore
    langgraph_stream = None  # type: ignore
    build_input_state = None  # type: ignore
    AgentState = None  # type: ignore

__all__ = [
    "AgentSpec",
    "parse_agent_spec",
    "AgentRegistry",
    "resolve_model",
    "dispatch",
    "DispatchResult",
    "Phase",
    "CANONICAL_SEQUENCE",
    "phase_lock_name",
    "forced_tools",
    "CanonicalLoop",
    "should_block_destructive",
    "gate_enabled",
    "PhaseTracker",
    "tracker_enabled",
    "advise",
    "router_enabled",
    "autoeval_enabled",
    "decide_keep_or_revert",
    "apply_autoeval",
    "AutoevalDecision",
    "autoevolve_enabled",
    "maybe_autoevolve",
    "trigger_improvement_research",
    "langgraph_enabled",
    "build_langgraph",
    "langgraph_stream",
    "build_input_state",
    "AgentState",
]
