"""Maintenance pipelines — memory cleanup and data backups.

Run standalone:   python -m services.pipelines.maintenance_pipeline
Scheduled via:    memory_cleanup_flow.serve(name="memory-cleanup", cron="0 3 * * *")
                  backup_flow.serve(name="data-backup", cron="0 4 * * 0")
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Kill-switch gate ──────────────────────────────────────────────────────
PREFECT_ENABLED = os.getenv("ODYSSEUS_PREFECT", "off").lower() in ("on", "1", "true")


def _lazy_import():
    """Import prefect decorators; raise a clear error if missing."""
    try:
        from prefect import flow as _flow
        from prefect import task as _task

        return _flow, _task
    except ImportError:
        raise ImportError(
            "Prefect is not installed. Install it with: pip install prefect  "
            "(see requirements-optional.txt). Set ODYSSEUS_PREFECT=off to "
            "use the built-in task_scheduler instead."
        )


# ── Memory cleanup ───────────────────────────────────────────────────────


def _memory_cleanup_task():
    """Remove stale memories and consolidate duplicates.

    Uses the existing consolidate_memory action from builtin_actions.py.
    """
    logger.info("Memory cleanup: starting …")

    cleaned = 0
    try:
        # Step 1: Remove orphaned memories (owner with no matching user)
        cleaned += _remove_orphaned_memories()
    except Exception:
        logger.exception("Orphaned memory cleanup failed")

    try:
        # Step 2: Consolidate duplicate memories per owner
        cleaned += _consolidate_duplicates()
    except Exception:
        logger.exception("Memory consolidation failed")

    try:
        # Step 3: Prune very old low-salience memories
        cleaned += _prune_old_memories()
    except Exception:
        logger.exception("Old memory pruning failed")

    logger.info("Memory cleanup complete — %d items processed", cleaned)
    return cleaned


def _remove_orphaned_memories() -> int:
    """Remove memories whose owner no longer exists in the user store."""
    try:
        from core.auth import AuthManager
        from core.database import db

        auth = AuthManager()
        existing_users = set(auth.users.keys())
        existing_users.add("")  # ownerless memories are valid

        conn = db._conn()
        cursor = conn.execute("SELECT DISTINCT owner FROM memories WHERE owner != ''")
        owners_in_db = {row[0] for row in cursor.fetchall()}
        orphans = owners_in_db - existing_users

        if not orphans:
            return 0

        count = 0
        for orphan in orphans:
            cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE owner = ?", (orphan,))
            n = cursor.fetchone()[0]
            conn.execute("DELETE FROM memories WHERE owner = ?", (orphan,))
            count += n
            logger.info("Removed %d orphaned memories for owner '%s'", n, orphan)

        conn.commit()
        return count
    except Exception:
        logger.exception("Orphan memory removal failed")
        return 0


def _consolidate_duplicates() -> int:
    """Consolidate near-duplicate memories via builtin action."""
    try:
        # Run for each owner that has memories
        from core.database import db
        from src.builtin_actions import action_consolidate_memory

        conn = db._conn()
        cursor = conn.execute("SELECT DISTINCT owner FROM memories")
        owners = [row[0] for row in cursor.fetchall()]

        total = 0
        for owner in owners:
            try:
                msg, ok = action_consolidate_memory(owner)
                if ok:
                    # Parse "consolidated N memories" from the message
                    import re

                    m = re.search(r"(\d+)", msg or "")
                    if m:
                        total += int(m.group(1))
            except Exception:
                logger.debug("Consolidation skipped for owner %s", owner)

        return total
    except Exception:
        logger.exception("Duplicate consolidation failed")
        return 0


def _prune_old_memories() -> int:
    """Remove memories older than 90 days with very low salience."""
    try:
        from core.database import db

        conn = db._conn()
        cutoff = datetime.now(UTC).replace(tzinfo=None)
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=90)

        cursor = conn.execute(
            "DELETE FROM memories WHERE created_at < ? AND salience < 0.2",
            (cutoff.isoformat(),),
        )
        count = cursor.rowcount
        conn.commit()

        if count:
            logger.info("Pruned %d old low-salience memories", count)
        return count
    except Exception:
        logger.exception("Old memory pruning failed")
        return 0


# ── Backup ────────────────────────────────────────────────────────────────


def _backup_task():
    """Backup data directory to a timestamped archive.

    Backups land in data/backups/ as .tar.gz. Keeps the last 7.
    """
    data_dir = Path(os.getenv("ODYSSEUS_DATA_DIR", "data")).resolve()
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"odysseus_backup_{timestamp}"
    archive_path = backup_dir / archive_name

    logger.info("Backup: archiving %s → %s", data_dir, archive_path)

    # Create tar.gz (excluding backups/ itself to avoid recursion)
    try:
        shutil.make_archive(
            str(archive_path),
            "gztar",
            root_dir=data_dir,
            base_dir=None,
        )
    except Exception:
        # Fallback: copy only key dirs if tar fails (Windows edge case)
        _backup_fallback(data_dir, archive_path)

    # Prune old backups — keep last 7
    _prune_old_backups(backup_dir, keep=7)

    size_mb = archive_path.stat().st_size / (1024 * 1024) if archive_path.exists() else 0
    logger.info("Backup complete — %s (%.1f MB)", archive_path.name, size_mb)
    return str(archive_path)


def _backup_fallback(data_dir: Path, archive_path: Path):
    """Copy key directories when make_archive fails (e.g. Windows)."""
    dest = Path(str(archive_path) + "_copy")
    dest.mkdir(parents=True, exist_ok=True)

    for name in ("settings", "sessions", "uploads", "memories.json"):
        src = data_dir / name
        if src.is_dir():
            shutil.copytree(src, dest / name, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, dest / name)

    logger.info("Backup fallback: copied key dirs to %s", dest)


def _prune_old_backups(backup_dir: Path, keep: int = 7):
    """Remove all but the newest `keep` backups."""
    archives = sorted(
        backup_dir.glob("odysseus_backup_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in archives[keep:]:
        try:
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
            logger.info("Pruned old backup: %s", old.name)
        except Exception:
            logger.debug("Could not prune %s", old)


# ── Flows (Prefect decorators) ──────────────────────────────────────────


def _create_flows():
    flow, task = _lazy_import()

    @task(retries=2, cache_key_fn=lambda *a: "memory-cleanup")
    def memory_cleanup_task():
        return _memory_cleanup_task()

    @flow(name="memory-cleanup", log_prints=True)
    def memory_cleanup_flow():
        """Clean up old/duplicate memories — Prefect flow."""
        memory_cleanup_task()

    @task(retries=2, cache_key_fn=lambda *a: "data-backup")
    def backup_task():
        return _backup_task()

    @flow(name="data-backup", log_prints=True)
    def backup_flow():
        """Backup data directory — Prefect flow."""
        backup_task()

    return memory_cleanup_flow, backup_flow


# Lazy singletons
_memory_cleanup_flow = None
_backup_flow = None


def get_memory_cleanup_flow():
    global _memory_cleanup_flow
    if not PREFECT_ENABLED:
        return None
    if _memory_cleanup_flow is None:
        _memory_cleanup_flow, _ = _create_flows()
    return _memory_cleanup_flow


def get_backup_flow():
    global _backup_flow
    if not PREFECT_ENABLED:
        return None
    if _backup_flow is None:
        _, _backup_flow = _create_flows()
    return _backup_flow


# ── CLI entry point ──────────────────────────────────────────────────────


def main():
    """Run both maintenance tasks directly (no Prefect server needed)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    logger.info("Running memory cleanup (standalone) …")
    _memory_cleanup_task()

    logger.info("Running backup (standalone) …")
    _backup_task()

    logger.info("Maintenance complete.")


if __name__ == "__main__":
    main()
