"""Discover .opencode agent specs from a directory and expose lookup.

Discovery is defensive: a single malformed file must never abort the scan.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.orchestrator.spec import AgentSpec, parse_agent_spec

logger = logging.getLogger(__name__)

# Default location relative to project root (parent of src/).
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_AGENTS_DIR = _PROJECT_ROOT / ".opencode" / "agents"


class AgentRegistry:
    """Loads and indexes AgentSpec objects by name."""

    def __init__(self, agents_dir=None):
        self._dir = Path(agents_dir) if agents_dir is not None else _DEFAULT_AGENTS_DIR
        self._specs: dict[str, AgentSpec] = {}

    def discover(self) -> AgentRegistry:
        """(Re)scan the agents directory. Idempotent — replaces the index."""
        specs: dict[str, AgentSpec] = {}
        if not self._dir.is_dir():
            logger.warning("[AgentRegistry] agents dir not found: %s", self._dir)
            self._specs = specs
            return self

        for md in sorted(self._dir.glob("*.md")):
            try:
                spec = parse_agent_spec(md)
            except Exception as exc:  # never let one file break discovery
                logger.warning("[AgentRegistry] skipping %s: %s", md.name, exc)
                continue
            specs[spec.name] = spec

        self._specs = specs
        logger.info("[AgentRegistry] discovered %d agents from %s", len(specs), self._dir)
        return self

    def get(self, name: str) -> AgentSpec | None:
        return self._specs.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._specs.keys())

    def all(self) -> list[AgentSpec]:
        return [self._specs[n] for n in self.list_names()]
