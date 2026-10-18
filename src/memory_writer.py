"""
Memory Writer — hooks into OpenCodeEngine MEMORY_OBSERVE phase.
Writes [stated] facts after each agent run using the event bus traces.
"""

import hashlib
import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class MemoryWriter:
    """Writes [stated] facts to MD files after each run."""

    def __init__(self, base_path: str = "obsidian-vault"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        self._stats = {"written": 0, "omitted": 0}

    def write(self, domain: str, fact: str, tag: str = "[stated]") -> bool:
        """Write a fact with provenance to a memory file."""
        # Omission check
        if any(w in fact.lower() for w in ["ssn", "social security", "credit card", "password"]):
            self._stats["omitted"] += 1
            return False

        filepath = os.path.join(self.base_path, "topics", f"{domain}.md")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        entry = f"- {tag} {fact}"
        now = datetime.now(UTC).isoformat()

        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            if entry in content:
                return True  # Already exists
            content = content.rstrip() + f"\n{entry}\n"
        else:
            content = f"---\nname: {domain}\ndescription: Facts about {domain}\nsources: [chat]\nupdated: {now}\n---\n\n{entry}\n"

        # Version hash
        h = hashlib.sha256(content.encode()).hexdigest()[:12]

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        self._stats["written"] += 1
        logger.info(f"Memory written: {domain}/{entry[:60]}")
        return True

    def read(self, domain: str) -> list[str]:
        """Read all facts from a domain."""
        filepath = os.path.join(self.base_path, "topics", f"{domain}.md")
        if not os.path.exists(filepath):
            return []
        with open(filepath, encoding="utf-8") as f:
            return [l.strip() for l in f.readlines() if l.strip().startswith("- [")]

    @property
    def stats(self) -> dict:
        return self._stats


# Singleton
_memory_writer = MemoryWriter()


def get_memory_writer() -> MemoryWriter:
    return _memory_writer
