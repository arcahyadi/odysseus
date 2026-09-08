"""
services/memory/namespace.py

Per-persona memory namespace isolation and promote-to-global.
Requirements: 5.1–5.8
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

GLOBAL_NS = "global"


class NamespaceResolver:
    """
    Wraps a MemoryManager to add per-persona namespace isolation.
    memory_manager must implement load_all() and save(entries).
    """

    def __init__(self, memory_manager):
        self._mm = memory_manager

    def resolve_namespace(self, crew_member_id: Optional[str]) -> str:
        """Return the namespace for a session. Requirements: 5.1, 5.2"""
        return crew_member_id if crew_member_id else GLOBAL_NS

    def write_entry(
        self,
        entry: Dict[str, Any],
        crew_member_id: Optional[str],
    ) -> Dict[str, Any]:
        """Tag an entry with the resolved namespace before saving."""
        entry["namespace"] = self.resolve_namespace(crew_member_id)
        return entry

    def filter_for_session(
        self,
        entries: List[Dict],
        owner: str,
        crew_member_id: Optional[str],
    ) -> List[Dict]:
        """
        Return entries visible in a session context.
        - Persona session: namespace==crew_member_id OR namespace=="global"
        - Global session: namespace=="global" only
        - Legacy entries with no namespace field default to "global"
        Requirements: 5.3, 5.7
        """
        ns = self.resolve_namespace(crew_member_id)
        if ns == GLOBAL_NS:
            return [
                e for e in entries
                if e.get("owner") == owner
                and e.get("namespace", GLOBAL_NS) == GLOBAL_NS
            ]
        return [
            e for e in entries
            if e.get("owner") == owner
            and e.get("namespace", GLOBAL_NS) in (ns, GLOBAL_NS)
        ]

    def promote_to_global(self, entry_id: str, owner: str) -> Dict[str, Any]:
        """
        Move entry to global namespace.
        Raises KeyError if entry not found / not owned.
        Raises ValueError if already global.
        Requirements: 5.4, 5.5, 5.6
        """
        try:
            all_entries = self._mm.load_all()
        except Exception as exc:
            raise KeyError(f"Could not load entries: {exc}") from exc

        target = next(
            (e for e in all_entries
             if e.get("id") == entry_id and e.get("owner") == owner),
            None,
        )
        if target is None:
            raise KeyError(f"Memory entry {entry_id!r} not found for owner {owner!r}")
        if target.get("namespace", GLOBAL_NS) == GLOBAL_NS:
            raise ValueError("Entry is already in global namespace")

        target["namespace"] = GLOBAL_NS
        try:
            self._mm.save(all_entries)
        except Exception as exc:
            raise RuntimeError(f"Failed to save after promote: {exc}") from exc
        return target
