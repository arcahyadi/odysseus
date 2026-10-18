"""
Autoeval Loop — Pattern autoresearch (Karpathy).
L'agent modifie du code → eval_command → compare metric → keep si mieux / git revert si pire.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    score: float
    raw_output: str
    success: bool
    error: str | None = None


@dataclass
class AutoevalRun:
    iteration: int
    score_before: float
    score_after: float
    improved: bool
    action_taken: str  # "kept" ou "reverted"
    git_hash_before: str
    git_hash_after: str | None


class AutoevalLoop:
    """
    Boucle d'auto-évaluation bornée.

    Usage :
        loop = AutoevalLoop(project_dir=".", eval_command="pytest tests/ -q --tb=no", metric="pass_rate")
        result = loop.run(max_iterations=10)
    """

    def __init__(
        self,
        project_dir: str,
        eval_command: str,  # Figé — jamais modifié par l'agent
        metric: str,  # Nom de la métrique à extraire
        higher_is_better: bool = True,
        timeout_seconds: int = 300,  # Timeout par run
    ):
        self.project_dir = Path(project_dir)
        self.eval_command = eval_command  # JAMAIS MODIFIÉ
        self.metric = metric
        self.higher_is_better = higher_is_better
        self.timeout_seconds = timeout_seconds
        self.history: list[AutoevalRun] = []

    def run_eval(self) -> EvalResult:
        """Lance eval_command et extrait la métrique. NE MODIFIE JAMAIS eval_command."""
        try:
            result = subprocess.run(
                self.eval_command,
                shell=True,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            output = result.stdout + result.stderr
            score = self._extract_metric(output, self.metric)
            return EvalResult(score=score, raw_output=output, success=result.returncode == 0)
        except subprocess.TimeoutExpired:
            return EvalResult(score=0.0, raw_output="TIMEOUT", success=False, error="timeout")
        except Exception as e:
            return EvalResult(score=0.0, raw_output=str(e), success=False, error=str(e))

    def _extract_metric(self, output: str, metric: str) -> float:
        """
        Extrait une métrique numérique depuis la sortie d'un eval.
        Stratégies :
        1. pytest : "X passed, Y failed" → pass_rate = X/(X+Y)
        2. JSON : {"metric": value}
        3. Regex générique : cherche "metric: N.NN" ou "metric=N.NN"
        4. Exit code : 0 → 1.0, else → 0.0
        """
        # Pytest pass rate
        if metric == "pass_rate" or "passed" in output:
            match = re.search(r"(\d+) passed", output)
            failed = re.search(r"(\d+) failed", output)
            if match:
                passed = int(match.group(1))
                total = passed + (int(failed.group(1)) if failed else 0)
                return passed / total if total > 0 else 0.0

        # JSON
        try:
            data = json.loads(output.strip())
            if metric in data:
                return float(data[metric])
        except (json.JSONDecodeError, ValueError):
            pass

        # Regex générique : "metric_name: 0.85" ou "metric_name=85%"
        patterns = [
            rf"{re.escape(metric)}[:\s=]+([0-9]+\.?[0-9]*%?)",
            r"([0-9]+\.?[0-9]*)%?\s*(?:accuracy|score|rate|pass)",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                val = match.group(1).rstrip("%")
                score = float(val)
                return score / 100 if score > 1.0 else score

        return 0.0

    def _get_git_hash(self) -> str:
        """Hash git du HEAD actuel."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.project_dir, capture_output=True, text=True, check=False
            )
            return result.stdout.strip()[:8]
        except Exception:
            return "unknown"

    def _git_revert_to(self, hash_before: str) -> bool:
        """Reverte au hash précédent via git reset --hard.

        Refuse par défaut : voir src.orchestrator.autoeval.destructive_revert_allowed.
        """
        from src.orchestrator.autoeval import destructive_revert_allowed

        if not destructive_revert_allowed():
            logger.warning(
                "Autoeval: revert to %s REFUSED (ODYSSEUS_AUTOEVAL_ALLOW_RESET is off) — "
                "decision kept, action skipped",
                hash_before,
            )
            return False
        try:
            subprocess.run(
                ["git", "reset", "--hard", hash_before], cwd=self.project_dir, capture_output=True, check=False
            )
            logger.info(f"Autoeval: git reset --hard {hash_before}")
            return True
        except Exception as e:
            logger.error(f"Autoeval: revert failed: {e}")
            return False

    def evaluate_last_change(self, score_baseline: float) -> AutoevalRun:
        """
        Évalue le dernier changement. Keep si meilleur, revert si pire.
        À appeler après un commit de l'agent.
        """
        hash_before = self._get_git_hash()

        result = self.run_eval()
        score_after = result.score

        improved = (score_after > score_baseline) if self.higher_is_better else (score_after < score_baseline)

        run = AutoevalRun(
            iteration=len(self.history) + 1,
            score_before=score_baseline,
            score_after=score_after,
            improved=improved,
            action_taken="kept" if improved else "reverted",
            git_hash_before=hash_before,
            git_hash_after=hash_before if improved else None,
        )

        if not improved:
            logger.warning(f"Autoeval: score {score_baseline:.3f} → {score_after:.3f} — REVERT")
            self._git_revert_to(hash_before)
        else:
            logger.info(f"Autoeval: score {score_baseline:.3f} → {score_after:.3f} — KEPT ✓")

        self.history.append(run)
        return run

    def get_summary(self) -> dict:
        """Résumé de tous les runs."""
        if not self.history:
            return {"runs": 0, "best_score": None}

        best = (
            max(self.history, key=lambda r: r.score_after)
            if self.higher_is_better
            else min(self.history, key=lambda r: r.score_after)
        )

        return {
            "runs": len(self.history),
            "kept": sum(1 for r in self.history if r.action_taken == "kept"),
            "reverted": sum(1 for r in self.history if r.action_taken == "reverted"),
            "best_score": best.score_after,
            "last_score": self.history[-1].score_after,
            "eval_command": self.eval_command,  # Toujours affiché pour traçabilité
        }


def create_from_manifest(project_dir: str) -> Optional["AutoevalLoop"]:
    """Crée un AutoevalLoop depuis un PROJECT.yaml."""
    try:
        from src.project_manifest import load_manifest

        manifest = load_manifest(project_dir)
        if manifest and manifest.eval_command:
            return AutoevalLoop(
                project_dir=project_dir,
                eval_command=manifest.eval_command,
                metric=manifest.metric or "pass_rate",
                higher_is_better=manifest.eval_higher_is_better,
            )
    except Exception as e:
        logger.warning(f"Impossible de créer AutoevalLoop depuis manifest: {e}")
    return None
