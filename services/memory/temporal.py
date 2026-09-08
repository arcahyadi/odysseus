"""
services/memory/temporal.py

Temporal memory: expiry, active_from, archival, time-range retrieval.
Requirements: 1.1–1.9, 2.1–2.4
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_iso(value: str) -> datetime:
    """Parse ISO-8601 UTC datetime string. Raises ValueError on bad input."""
    try:
        return datetime.strptime(str(value), ISO_FMT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid ISO-8601 UTC datetime: {value!r}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TemporalMemoryStore:
    """
    Wraps an existing MemoryManager to add temporal fields and archival.
    memory_manager must implement load_all() and save(entries).
    memory_vector is optional; if present, remove() is called on archival.
    """

    def __init__(self, memory_manager, memory_vector=None):
        self._mm = memory_manager
        self._mv = memory_vector

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_temporal_fields(
        self,
        expires_at: Optional[str],
        active_from: Optional[str],
    ) -> None:
        """Raise ValueError (map to HTTP 422) if either field is invalid."""
        if expires_at is not None:
            _parse_iso(expires_at)
        if active_from is not None:
            _parse_iso(active_from)

    # ── Write helpers ─────────────────────────────────────────────────────────

    def set_temporal(
        self,
        entry: Dict[str, Any],
        expires_at: Optional[str],
        active_from: Optional[str],
    ) -> Dict[str, Any]:
        """Attach temporal fields to an in-memory entry dict."""
        entry["expires_at"] = expires_at
        entry["active_from"] = active_from
        entry.setdefault("status", "active")
        return entry

    # ── Read helpers ──────────────────────────────────────────────────────────

    def is_active(self, entry: Dict[str, Any]) -> bool:
        """Return True if the entry should appear in standard context retrieval."""
        if entry.get("status") == "archived":
            return False
        af = entry.get("active_from")
        if af:
            try:
                if _parse_iso(af) > _utcnow():
                    return False
            except ValueError:
                pass  # malformed stored value — treat as active
        return True

    def filter_active(self, entries: List[Dict]) -> List[Dict]:
        """Return only entries that pass is_active()."""
        return [e for e in entries if self.is_active(e)]

    # ── Time-range retrieval ──────────────────────────────────────────────────

    def time_range_query(
        self,
        entries: List[Dict],
        from_dt: Optional[str] = None,
        to_dt: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Dict]:
        """
        Return entries whose created_at (unix epoch) falls within [from_dt, to_dt].
        Returns [] when from_dt > to_dt. Partial bounds supported.
        """
        from_ts: Optional[float] = None
        to_ts: Optional[float] = None
        if from_dt:
            from_ts = _parse_iso(from_dt).timestamp()
        if to_dt:
            to_ts = _parse_iso(to_dt).timestamp()
        if from_ts is not None and to_ts is not None and from_ts > to_ts:
            return []

        def _in_range(e: Dict) -> bool:
            if not include_archived and e.get("status") == "archived":
                return False
            ts = float(e.get("timestamp", 0))
            if from_ts is not None and ts < from_ts:
                return False
            if to_ts is not None and ts > to_ts:
                return False
            return True

        result = [e for e in entries if _in_range(e)]
        result.sort(key=lambda e: e.get("timestamp", 0))
        return result

    # ── Archival ──────────────────────────────────────────────────────────────

    def run_expiry_pass(self) -> int:
        """
        Scan all memory entries (all owners). Archive any where expires_at <= now.
        Returns the number of entries archived in this pass.
        Requirements: 1.4, 1.5, 1.7, 1.8
        """
        now = _utcnow()
        now_str = now.strftime(ISO_FMT)
        try:
            all_entries = self._mm.load_all()
        except Exception as exc:
            logger.warning("TemporalMemoryStore: load_all() failed: %s", exc)
            return 0

        archived_ids = []
        changed = False
        for entry in all_entries:
            ea = entry.get("expires_at")
            if not ea or entry.get("status") == "archived":
                continue
            try:
                if _parse_iso(ea) <= now:
                    entry["status"] = "archived"
                    entry["archived_at"] = now_str
                    archived_ids.append(entry.get("id", ""))
                    changed = True
            except ValueError:
                logger.warning(
                    "Skipping malformed expires_at %r on entry %s",
                    ea, entry.get("id")
                )

        if changed:
            try:
                self._mm.save(all_entries)
            except Exception as exc:
                logger.warning("TemporalMemoryStore: save() failed: %s", exc)
                return 0
            # Drop archived entries from vector index if available
            if self._mv is not None:
                for entry_id in archived_ids:
                    try:
                        self._mv.remove(entry_id)
                    except Exception:
                        pass

        logger.info("Expiry pass: archived %d entries", len(archived_ids))
        return len(archived_ids)
