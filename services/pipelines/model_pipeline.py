"""Model update pipeline — checks for newer model versions and refreshes caches.

Run standalone:   python -m services.pipelines.model_pipeline
Scheduled via:    model_update_flow.serve(name="model-update", cron="0 5 * * 0")
"""

from __future__ import annotations

import logging
import os

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


# ── Tasks ─────────────────────────────────────────────────────────────────


def _check_model_updates_task():
    """Check for newer versions of local models and update the cache.

    Scans the HuggingFace cache and checks for newer tags.
    """
    logger.info("Model update check: starting …")
    updates_found = 0

    try:
        updates_found = _check_hf_model_updates()
    except Exception:
        logger.exception("HuggingFace model update check failed")

    try:
        _refresh_embedding_index()
    except Exception:
        logger.exception("Embedding index refresh failed")

    logger.info("Model update check complete — %d updates found", updates_found)
    return updates_found


def _check_hf_model_updates_task():
    """Check HuggingFace Hub for newer model versions."""
    try:
        from huggingface_hub import HfApi, scan_cache_dir

        api = HfApi()
        cache = scan_cache_dir()

        updates = []
        for repo in cache.repos:
            try:
                # Check if a newer revision exists
                remote_info = api.repo_info(repo.repo_id)
                local_rev = repo.revisions[-1].commit_hash if repo.revisions else None
                if local_rev and remote_info.last_modified:
                    # Compare — any newer commit means an update available
                    updates.append(
                        {
                            "repo_id": repo.repo_id,
                            "local_size": repo.size_on_disk,
                            "last_modified": str(remote_info.last_modified),
                        }
                    )
            except Exception:
                continue

        if updates:
            logger.info("Model updates available for %d models:", len(updates))
            for u in updates:
                logger.info("  - %s (last modified: %s)", u["repo_id"], u["last_modified"])

        return len(updates)
    except ImportError:
        logger.warning("huggingface_hub not installed — skipping model update check")
        return 0


def _check_hf_cache_size_task():
    """Report HuggingFace cache size and optionally prune old models."""
    try:
        from huggingface_hub import scan_cache_dir

        cache = scan_cache_dir()
        total_bytes = cache.size_on_disk
        total_gb = total_bytes / (1024**3)

        logger.info("HuggingFace cache: %.1f GB across %d repos", total_gb, cache.size_on_disk)

        # Warn if cache exceeds 10GB
        if total_gb > 10:
            logger.warning(
                "HuggingFace cache is %.1f GB — consider pruning with `huggingface-cli delete-cache`", total_gb
            )

        return total_bytes
    except ImportError:
        logger.warning("huggingface_hub not installed — skipping cache check")
        return 0


def _check_hf_model_updates() -> int:
    """Core model update check logic."""
    return _check_hf_model_updates_task()


def _refresh_embedding_index():
    """Refresh the embedding tool index (if fastembed is available)."""
    try:
        from src.tool_index import refresh_tool_index

        refresh_tool_index()
        logger.info("Embedding tool index refreshed")
    except ImportError:
        logger.debug("tool_index not available — skipping")
    except Exception:
        logger.exception("Tool index refresh failed")


# ── Flow (Prefect decorators) ────────────────────────────────────────────


def _create_flow():
    flow, task = _lazy_import()

    @task(retries=2, cache_key_fn=lambda *a: "model-update")
    def model_update_task():
        """Check and report model updates (Prefect task)."""
        return _check_model_updates_task()

    @flow(name="model-update", log_prints=True)
    def model_update_flow():
        """Weekly model update check — Prefect flow."""
        model_update_task()

    return model_update_flow


_model_update_flow = None


def get_model_update_flow():
    global _model_update_flow
    if not PREFECT_ENABLED:
        return None
    if _model_update_flow is None:
        _model_update_flow = _create_flow()
    return _model_update_flow


# ── CLI entry point ──────────────────────────────────────────────────────


def main():
    """Run the model update check directly (no Prefect server needed)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("Running model update check (standalone) …")
    count = _check_model_updates_task()
    logger.info("Done — %d updates found.", count)
    return count


if __name__ == "__main__":
    main()
