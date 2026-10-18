"""CanonicalLoop — walks the 7 canonical phases and drives the phase-lock.

The loop's only side effect is calling registry.set_phase(session_id, name)
so the already-wired enforcement in tool_execution.py takes effect. If no
registry is injected, apply() is a no-op (useful for pure unit tests).
"""

from __future__ import annotations

import logging

from src.orchestrator.phases import (
    CANONICAL_SEQUENCE,
    Phase,
    phase_lock_name,
)

logger = logging.getLogger(__name__)


class CanonicalLoop:
    def __init__(self, session_id: str, registry=None):
        self.session_id = session_id
        self._registry = registry
        self._index = 0

    @property
    def current(self) -> Phase:
        return CANONICAL_SEQUENCE[self._index]

    def advance(self) -> bool:
        """Move to the next phase. Returns False if already at the last phase."""
        if self._index >= len(CANONICAL_SEQUENCE) - 1:
            return False
        self._index += 1
        return True

    def goto(self, phase: Phase) -> None:
        """Jump directly to a named phase and apply it."""
        self._index = CANONICAL_SEQUENCE.index(phase)
        self.apply()

    def apply(self) -> None:
        """Push the current phase into the phase-lock registry."""
        if self._registry is None:
            return
        name = phase_lock_name(self.current)
        self._registry.set_phase(self.session_id, name)
        logger.info("[CanonicalLoop] session=%s → phase %s", self.session_id, name)
