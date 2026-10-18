"""
Observer — Agrège les signaux d'observabilité et calcule le drift score.
Sources : BudgetEnforcer (budgets), CodeBurn (one-shot rate, waste), traces JSONL.
"""

import logging
from enum import Enum
from src.app_context import app_context


logger = logging.getLogger(__name__)

# Harness/protocol files that must never be modified by the agent.
# If CodeBurn detects touches on these, drift escalates to HIGH.
_HARNESS_PATTERNS = [
    "agent_loop.py",
    "budget_enforcer.py",
    "observer.py",
    "project_manifest.py",
    "docker-compose.yml",
    "Dockerfile",
    "pytest.ini",
    "pyproject.toml",
    "conftest.py",
]


# Write-type tools whose target file counts as "touched". Reads (bash cat,
# read_file, grep) are deliberately excluded so inspecting the harness never
# escalates drift — only writes to it do.
_HARNESS_WRITE_TOOLS = {
    "write_file",
    "edit_file",
    "create_document",
    "update_document",
    "edit_document",
}


class DriftLevel(Enum):
    LOW = "low"  # Légère dérive — continuer
    MEDIUM = "medium"  # Dérive significative — alerte
    HIGH = "high"  # Harness/protocole touché — re-loop ou escalade


# Persistent inter-run state — shared across Observer instances so drift
# accumulates over multiple runs instead of resetting each time.
_MAX_REPORTS = 100  # cap to bound memory
app_context.caches.persistent_reports: list[dict] = []
app_context.caches.persistent_harness_touched: bool = False


def reset_observer_state() -> None:
    """Reset persistent state — used in tests to avoid cross-test contamination."""
    app_context.caches.persistent_reports = []
    app_context.caches.persistent_harness_touched = False


class Observer:
    """Agrège les signaux et calcule le drift score global.

    Uses module-level persistent state (app_context.caches.persistent_reports, app_context.caches.persistent_harness_touched)
    so that drift accumulates across runs — a harness touch in run N is visible in run N+1.
    """

    def __init__(self) -> None:
        self._budget_statuses: dict[str, dict] = {}

    @property
    def _codeburn_reports(self) -> list[dict]:
        return app_context.caches.persistent_reports

    @property
    def _harness_touched(self) -> bool:
        return app_context.caches.persistent_harness_touched

    @_harness_touched.setter
    def _harness_touched(self, value: bool) -> None:
        app_context.caches.persistent_harness_touched = value

    def record_codeburn_report(self, report: dict) -> None:
        """Ingère un rapport CodeBurn (one_shot_rate, waste_patterns, cost_vs_commits)."""
        if not isinstance(report, dict):
            logger.warning("Observer.record_codeburn_report: expected dict, got %s", type(report))
            return
        app_context.caches.persistent_reports.append(report)
        if len(app_context.caches.persistent_reports) > _MAX_REPORTS:
            app_context.caches.persistent_reports = app_context.caches.persistent_reports[-_MAX_REPORTS:]  # cap

        # Check if harness files were touched
        touched_files: list[str] = report.get("touched_files", [])
        for f in touched_files:
            for pattern in _HARNESS_PATTERNS:
                if pattern in f:
                    self._harness_touched = True
                    logger.warning("Observer: harness file touched — %s", f)
                    break

    def record_budget_status(self, run_id: str, usage_report: dict) -> None:
        """Ingère le statut budget d'un run."""
        if not isinstance(usage_report, dict):
            logger.warning("Observer.record_budget_status: expected dict, got %s", type(usage_report))
            return
        self._budget_statuses[run_id] = usage_report

    def ingest_metrics(self, metrics: dict, tool_events: list | None = None) -> None:
        """Derive a CodeBurn-style report from existing turn signals (no recompute).

        Consumes the ``tool_events`` already assembled for the SSE stream (falling
        back to ``metrics["tool_events"]``) and reuses ``record_codeburn_report`` so
        the drift machinery is unchanged: writes to harness files still escalate to
        HIGH, failed tools become waste patterns, and one_shot_rate = success ratio.
        """
        events = tool_events if tool_events is not None else (metrics or {}).get("tool_events", [])
        if not events:
            return

        total = 0
        failures: list[dict] = []
        touched: list[str] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            total += 1
            exit_code = ev.get("exit_code")
            if exit_code is not None and exit_code != 0:
                failures.append({"tool": ev.get("tool"), "command": ev.get("command")})
            if ev.get("tool") in _HARNESS_WRITE_TOOLS:
                path_blob = " ".join(str(ev.get(k, "")) for k in ("command", "diff", "doc_title")).strip()
                if path_blob:
                    touched.append(path_blob)

        if total == 0:
            return

        self.record_codeburn_report(
            {
                "one_shot_rate": (total - len(failures)) / total,
                "waste_patterns": failures,
                "touched_files": touched,
                "source": "agent_metrics",
            }
        )

    def compute_drift_score(self) -> DriftLevel:
        """Calcule le drift score global. HIGH si fichiers harness/protocole touchés."""
        if self._harness_touched:
            return DriftLevel.HIGH

        # Check waste patterns from CodeBurn
        total_waste_score = 0.0
        for report in self._codeburn_reports:
            one_shot_rate: float = float(report.get("one_shot_rate", 1.0))
            # Low one-shot rate = high re-work = drift
            if one_shot_rate < 0.5:
                total_waste_score += 2.0
            elif one_shot_rate < 0.8:
                total_waste_score += 1.0

            waste_patterns: list = report.get("waste_patterns", [])
            total_waste_score += len(waste_patterns) * 0.5

        # Check budget usage: any run above 90% is concerning
        for run_id, status in self._budget_statuses.items():
            percent: dict = status.get("percent", {})
            max_pct = max(percent.values()) if percent else 0.0
            if max_pct >= 95:
                total_waste_score += 2.0
            elif max_pct >= 80:
                total_waste_score += 1.0

        if total_waste_score >= 4.0:
            return DriftLevel.HIGH
        if total_waste_score >= 1.5:
            return DriftLevel.MEDIUM
        return DriftLevel.LOW

    def get_summary(self) -> dict:
        """Résumé pour injection dans le prochain run."""
        drift = self.compute_drift_score()
        runs_over_alert = []
        for run_id, status in self._budget_statuses.items():
            percent = status.get("percent", {})
            max_pct = max(percent.values()) if percent else 0.0
            if max_pct >= status.get("budget", {}).get("alert_at_percent", 80):
                runs_over_alert.append(run_id)

        latest_codeburn: dict | None = self._codeburn_reports[-1] if self._codeburn_reports else None

        return {
            "drift_level": drift.value,
            "harness_touched": self._harness_touched,
            "runs_tracked": len(self._budget_statuses),
            "runs_over_alert_threshold": runs_over_alert,
            "codeburn_reports_count": len(self._codeburn_reports),
            "latest_codeburn_one_shot_rate": (latest_codeburn.get("one_shot_rate") if latest_codeburn else None),
            "recommendation": _drift_recommendation(drift),
        }


def _drift_recommendation(level: DriftLevel) -> str:
    return {
        DriftLevel.LOW: "Continue — drift within acceptable range.",
        DriftLevel.MEDIUM: "Alert — review waste patterns before next iteration.",
        DriftLevel.HIGH: "Stop — harness or protocol file touched. Escalate to human review.",
    }[level]
