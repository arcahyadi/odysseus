"""CodeBurn runner — executes the codeburn CLI and feeds results to the Observer (M4).

CodeBurn reads session logs from disk (JSONL/SQLite) and produces:
  - one_shot_rate: % of edits that succeeded on first try
  - waste_patterns: expensive anti-patterns detected
  - cost_vs_commits: correlation between token spend and productive commits
  - touched_files: files modified during the session

The runner is best-effort: if codeburn is not installed or fails, it returns
an empty report. Kill-switched via ODYSSEUS_CODEBURN (default OFF).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def codeburn_enabled() -> bool:
    val = os.getenv("ODYSSEUS_CODEBURN", "off").strip().lower()
    return val in ("on", "1", "true", "yes")


def _find_codeburn() -> str | None:
    """Locate the codeburn CLI binary. Returns None if not installed."""
    # Try npm global first
    for candidate in ("codeburn", "npx", "node"):
        if shutil.which(candidate) is not None:
            return candidate
    return None


async def run_codeburn(session_id: str, trace_dir: str | None = None) -> dict:
    """Run codeburn and return a report dict. Returns empty dict on failure.

    The report dict keys match Observer.record_codeburn_report expectations:
      - one_shot_rate: float (0.0-1.0)
      - waste_patterns: list[dict] with pattern name + estimated_tokens_saved
      - cost_vs_commits: dict mapping commit hash -> cost
      - touched_files: list[str] of files modified
      - grade: str (A-F)
    """
    if not codeburn_enabled():
        return {}

    codeburn_bin = _find_codeburn()
    if codeburn_bin is None:
        logger.debug("[CodeBurn] codeburn CLI not found — install with: npm i -g codeburn")
        return {}

    # Determine trace/log directory
    if trace_dir is None:
        trace_dir = os.path.join(os.getcwd(), "data", "traces")

    trace_path = Path(trace_dir)
    if not trace_path.exists():
        logger.debug("[CodeBurn] trace dir not found: %s", trace_dir)
        return {}

    cmd = [codeburn_bin, "report", "--dir", str(trace_path), "--format", "json"]
    if codeburn_bin == "npx":
        cmd = ["npx", "codeburn", "report", "--dir", str(trace_path), "--format", "json"]
    elif codeburn_bin == "node":
        cmd = [
            "node",
            str(shutil.which("codeburn") or "codeburn"),
            "report",
            "--dir",
            str(trace_path),
            "--format",
            "json",
        ]

    logger.info("[CodeBurn] running report for session=%s", session_id)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except TimeoutError:
        logger.warning("[CodeBurn] timed out after 30s")
        return {}
    except FileNotFoundError:
        logger.debug("[CodeBurn] executable not found")
        return {}
    except Exception as exc:
        logger.warning("[CodeBurn] failed to run: %s", exc)
        return {}

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:500] if stderr else ""
        logger.debug("[CodeBurn] exited %d: %s", proc.returncode, stderr_text)
        return {}

    try:
        raw = stdout.decode("utf-8", errors="replace")
        report = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("[CodeBurn] failed to parse JSON output: %s", exc)
        return {}

    if not isinstance(report, dict):
        return {}

    # Normalize keys to what Observer expects
    normalized: dict = {}
    normalized["one_shot_rate"] = float(report.get("oneShotRate", report.get("one_shot_rate", 0)))
    normalized["waste_patterns"] = report.get("wastePatterns", report.get("waste_patterns", []))
    normalized["cost_vs_commits"] = report.get("costVsCommits", report.get("cost_vs_commits", {}))
    normalized["touched_files"] = report.get("touchedFiles", report.get("touched_files", []))
    normalized["grade"] = report.get("grade", "N/A")

    logger.info(
        "[CodeBurn] session=%s one_shot_rate=%.2f waste=%d grade=%s",
        session_id,
        normalized["one_shot_rate"],
        len(normalized["waste_patterns"]),
        normalized["grade"],
    )
    return normalized


def feed_observer(report: dict) -> None:
    """Feed a codeburn report to the singleton Observer (best-effort)."""
    if not report:
        return
    try:
        from src.observer import Observer

        observer = Observer()
        observer.record_codeburn_report(report)
    except Exception as exc:
        logger.debug("[CodeBurn] failed to feed observer: %s", exc)
