"""Canonical 7-phase loop definitions (Milestone 2, design Section 2).

Each canonical phase maps to a phase-lock enforcement name (a key in
config/phase-lock.yaml) and a set of "forced" tools the loop should encourage
in that phase. The enforcement itself lives in src/tool_registry.py; this module
is pure data + helpers.
"""

from __future__ import annotations

from enum import Enum


class Phase(Enum):
    CLASSIFY = "CLASSIFY"
    KNOW = "KNOW"
    PLAN = "PLAN"
    BUILD = "BUILD"
    QUALITY = "QUALITY"
    AUTOEVAL = "AUTOEVAL"
    MEMORY_OBSERVE = "MEMORY_OBSERVE"


# Ordered sequence the loop walks through.
CANONICAL_SEQUENCE: list[Phase] = [
    Phase.CLASSIFY,
    Phase.KNOW,
    Phase.PLAN,
    Phase.BUILD,
    Phase.QUALITY,
    Phase.AUTOEVAL,
    Phase.MEMORY_OBSERVE,
]

# Map each canonical phase to the phase-lock.yaml enforcement key.
# Identity mapping today, kept explicit so a future rename of an enforcement
# profile does not silently break the loop.
_PHASE_LOCK_NAME: dict[Phase, str] = {
    Phase.CLASSIFY: "CLASSIFY",
    Phase.KNOW: "KNOW",
    Phase.PLAN: "PLAN",
    Phase.BUILD: "BUILD",
    Phase.QUALITY: "QUALITY",
    Phase.AUTOEVAL: "AUTOEVAL",
    Phase.MEMORY_OBSERVE: "MEMORY_OBSERVE",
}

# Tools the loop should force/encourage per phase (advisory; enforcement of
# BLOCKED tools is done by the phase-lock config).
_FORCED_TOOLS: dict[Phase, list[str]] = {
    Phase.CLASSIFY: ["risk_classifier"],
    Phase.KNOW: ["memory_search"],
    Phase.PLAN: [],
    Phase.BUILD: [],
    Phase.QUALITY: [],
    Phase.AUTOEVAL: ["autoeval"],
    Phase.MEMORY_OBSERVE: ["memory_distill", "trace_writer"],
}


def phase_lock_name(phase: Phase) -> str:
    return _PHASE_LOCK_NAME[phase]


def forced_tools(phase: Phase) -> list[str]:
    return list(_FORCED_TOOLS.get(phase, []))
