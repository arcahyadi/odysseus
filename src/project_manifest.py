"""
Project Manifest — Charge et valide un PROJECT.yaml par projet.
Définit les budgets, l'objectif, et l'eval_command.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProjectBudget:
    max_tokens: int = 100_000  # tokens totaux pour ce projet
    max_iterations: int = 50  # rounds d'agent max
    max_cost_usd: float = 5.0  # coût max en dollars
    max_tool_calls: int = 200  # tool calls max
    alert_at_percent: int = 80  # alerte à 80% du budget


@dataclass
class ProjectManifest:
    name: str
    objective: str  # Ce qu'on veut atteindre
    done_definition: str  # Définition mesurable de "terminé"
    constraints: list[str] = field(default_factory=list)
    budgets: ProjectBudget = field(default_factory=ProjectBudget)
    eval_command: str | None = None  # Commande figée (jamais modifiée par l'agent)
    metric: str | None = None  # Métrique unique (ex: "pytest_pass_rate")
    eval_higher_is_better: bool = True


def load_manifest(project_dir: str) -> ProjectManifest | None:
    """Charge PROJECT.yaml depuis un répertoire projet."""
    path = Path(project_dir) / "PROJECT.yaml"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return None

    budgets_data = data.get("budgets", {}) or {}
    budgets = ProjectBudget(
        max_tokens=int(budgets_data.get("max_tokens", 100_000)),
        max_iterations=int(budgets_data.get("max_iterations", 50)),
        max_cost_usd=float(budgets_data.get("max_cost_usd", 5.0)),
        max_tool_calls=int(budgets_data.get("max_tool_calls", 200)),
        alert_at_percent=int(budgets_data.get("alert_at_percent", 80)),
    )

    return ProjectManifest(
        name=str(data.get("name", "")),
        objective=str(data.get("objective", "")),
        done_definition=str(data.get("done_definition", "")),
        constraints=list(data.get("constraints", [])),
        budgets=budgets,
        eval_command=data.get("eval_command"),
        metric=data.get("metric"),
        eval_higher_is_better=bool(data.get("eval_higher_is_better", True)),
    )


def save_manifest(manifest: ProjectManifest, project_dir: str) -> None:
    """Sauvegarde PROJECT.yaml."""
    path = Path(project_dir) / "PROJECT.yaml"
    data = {
        "name": manifest.name,
        "objective": manifest.objective,
        "done_definition": manifest.done_definition,
        "constraints": manifest.constraints,
        "budgets": {
            "max_tokens": manifest.budgets.max_tokens,
            "max_iterations": manifest.budgets.max_iterations,
            "max_cost_usd": manifest.budgets.max_cost_usd,
            "max_tool_calls": manifest.budgets.max_tool_calls,
            "alert_at_percent": manifest.budgets.alert_at_percent,
        },
        "eval_command": manifest.eval_command,
        "metric": manifest.metric,
        "eval_higher_is_better": manifest.eval_higher_is_better,
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
