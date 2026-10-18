"""SFD §5.3 — Planification intelligente avec décomposition arborescente.

Mission → Objectifs → Sous-projets → Tâches
Chaque élément : identifiant unique, description, Definition of Done, budget, agents, outils.

Stockage YAML/JSON dans le bloc-notes persistant (§5.2.3).
Externalisé dès la création — jamais uniquement dans le contexte de conversation.

Gated behind ODYSSEUS_PLANNING_ENGINE kill-switch (default OFF).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from src.app_context import app_context


logger = logging.getLogger(__name__)


def planning_engine_enabled() -> bool:
    val = os.getenv("ODYSSEUS_PLANNING_ENGINE", "off").strip().lower()
    return val in {"on", "1", "true", "yes"}


PLANNING_DIR = Path("data/plans")
PLANNING_DIR.mkdir(parents=True, exist_ok=True)

# ─── Types ──────────────────────────────────────────────────────────────


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DefinitionOfDone:
    criteria: list[str] = field(default_factory=list)
    eval_command: str | None = None
    metric: str | None = None
    metric_min: float | None = None

    def is_satisfied(self, results: dict | None = None) -> tuple[bool, str]:
        if not self.criteria:
            return True, "No criteria defined"
        if results:
            for c in self.criteria:
                if c not in results:
                    return False, f"Missing result for: {c}"
                if isinstance(results[c], bool) and not results[c]:
                    return False, f"Failed: {c}"
        return True, "All criteria satisfied"


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    dod: DefinitionOfDone = field(default_factory=DefinitionOfDone)
    agent: str | None = None
    tools: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    estimated_effort_hours: float = 0.0
    notes: str = ""


@dataclass
class SubProject:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    tasks: list[Task] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    context_isolation: bool = False  # §5.1.3 — découpage par contexte


@dataclass
class Goal:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    success_metric: str = ""
    sub_projects: list[SubProject] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING


@dataclass
class Mission:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    statement: str = ""
    goals: list[Goal] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = ""


@dataclass
class Plan:
    """Plan complet d'un projet."""

    project_id: str
    mission: Mission = field(default_factory=Mission)
    budgets: dict[str, float] = field(
        default_factory=lambda: {
            "max_iterations": 50,
            "max_tokens": 200000,
            "max_cost_usd": 5.0,
            "max_tool_calls": 200,
            "max_wall_seconds": 3600,
        }
    )
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_file(self) -> None:
        path = PLANNING_DIR / f"{self.project_id}.json"
        data = {
            "project_id": self.project_id,
            "mission": {
                "id": self.mission.id,
                "statement": self.mission.statement,
                "status": self.mission.status.value,
                "created_at": self.mission.created_at,
                "goals": [
                    {
                        "id": g.id,
                        "description": g.description,
                        "success_metric": g.success_metric,
                        "status": g.status.value,
                        "sub_projects": [
                            {
                                "id": sp.id,
                                "name": sp.name,
                                "description": sp.description,
                                "status": sp.status.value,
                                "context_isolation": sp.context_isolation,
                                "tasks": [
                                    {
                                        "id": t.id,
                                        "description": t.description,
                                        "status": t.status.value,
                                        "priority": t.priority.value,
                                        "dod": {"criteria": t.dod.criteria, "eval_command": t.dod.eval_command},
                                        "agent": t.agent,
                                        "tools": t.tools,
                                        "depends_on": t.depends_on,
                                        "estimated_effort_hours": t.estimated_effort_hours,
                                        "notes": t.notes,
                                    }
                                    for t in sp.tasks
                                ],
                            }
                            for sp in g.sub_projects
                        ],
                    }
                    for g in self.mission.goals
                ],
            },
            "budgets": self.budgets,
            "constraints": self.constraints,
            "metadata": self.metadata,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def from_file(cls, project_id: str) -> Plan | None:
        path = PLANNING_DIR / f"{project_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        m = data["mission"]
        plan = cls(project_id=project_id)
        plan.mission = Mission(
            id=m["id"],
            statement=m["statement"],
            status=TaskStatus(m["status"]),
            created_at=m.get("created_at", ""),
            goals=[
                Goal(
                    id=g["id"],
                    description=g["description"],
                    success_metric=g.get("success_metric", ""),
                    status=TaskStatus(g["status"]),
                    sub_projects=[
                        SubProject(
                            id=sp["id"],
                            name=sp.get("name", ""),
                            description=sp.get("description", ""),
                            status=TaskStatus(sp["status"]),
                            context_isolation=sp.get("context_isolation", False),
                            tasks=[
                                Task(
                                    id=t["id"],
                                    description=t["description"],
                                    status=TaskStatus(t["status"]),
                                    priority=TaskPriority(t.get("priority", "medium")),
                                    dod=DefinitionOfDone(
                                        criteria=t.get("dod", {}).get("criteria", []),
                                        eval_command=t.get("dod", {}).get("eval_command"),
                                    ),
                                    agent=t.get("agent"),
                                    tools=t.get("tools", []),
                                    depends_on=t.get("depends_on", []),
                                    estimated_effort_hours=t.get("estimated_effort_hours", 0),
                                    notes=t.get("notes", ""),
                                )
                                for t in sp["tasks"]
                            ],
                        )
                        for sp in g["sub_projects"]
                    ],
                )
                for g in m["goals"]
            ],
        )
        plan.budgets = data.get("budgets", plan.budgets)
        plan.constraints = data.get("constraints", {})
        plan.metadata = data.get("metadata", {})
        return plan

    def progress(self) -> dict[str, Any]:
        """Calcule le progrès du plan."""
        total_tasks = 0
        completed = 0
        for g in self.mission.goals:
            for sp in g.sub_projects:
                for t in sp.tasks:
                    total_tasks += 1
                    if t.status == TaskStatus.COMPLETED:
                        completed += 1
        return {
            "total_tasks": total_tasks,
            "completed": completed,
            "percent": round(completed / max(total_tasks, 1) * 100, 1),
            "goals": len(self.mission.goals),
            "goals_completed": sum(1 for g in self.mission.goals if g.status == TaskStatus.COMPLETED),
        }

    def next_pending_task(self) -> Task | None:
        """Retourne la prochaine tâche à exécuter (respecte les dépendances)."""
        completed_ids: set[str] = set()
        for g in self.mission.goals:
            for sp in g.sub_projects:
                for t in sp.tasks:
                    if t.status == TaskStatus.COMPLETED:
                        completed_ids.add(t.id)

        for g in self.mission.goals:
            if g.status != TaskStatus.PENDING:
                continue
            for sp in g.sub_projects:
                if sp.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                    continue
                for t in sp.tasks:
                    if t.status != TaskStatus.PENDING:
                        continue
                    if all(dep in completed_ids for dep in t.depends_on):
                        return t
        return None


# ─── Planning Engine ────────────────────────────────────────────────────


class PlanningEngine:
    """Moteur de planification avec décomposition arborescente."""

    def create_plan(self, project_id: str, statement: str) -> Plan:
        plan = Plan(project_id=project_id)
        plan.mission = Mission(statement=statement)
        plan.to_file()
        logger.info("Created plan for project %s", project_id)
        return plan

    def load_plan(self, project_id: str) -> Plan | None:
        return Plan.from_file(project_id)

    def decompose_mission(self, plan: Plan, goals: list[str]) -> Plan:
        """Décompose une mission en objectifs."""
        for desc in goals:
            goal = Goal(description=desc)
            plan.mission.goals.append(goal)
        plan.to_file()
        return plan

    def decompose_goal(self, plan: Plan, goal_id: str, sub_projects: list[dict]) -> Plan:
        """Décompose un objectif en sous-projets."""
        for g in plan.mission.goals:
            if g.id == goal_id:
                for sp_data in sub_projects:
                    sp = SubProject(
                        name=sp_data.get("name", ""),
                        description=sp_data.get("description", ""),
                        context_isolation=sp_data.get("context_isolation", False),
                    )
                    g.sub_projects.append(sp)
                break
        plan.to_file()
        return plan

    def add_tasks(self, plan: Plan, sub_project_id: str, tasks_data: list[dict]) -> Plan:
        """Ajoute des tâches à un sous-projet."""
        for g in plan.mission.goals:
            for sp in g.sub_projects:
                if sp.id == sub_project_id:
                    for t_data in tasks_data:
                        task = Task(
                            description=t_data.get("description", ""),
                            priority=TaskPriority(t_data.get("priority", "medium")),
                            dod=DefinitionOfDone(criteria=t_data.get("dod", [])),
                            agent=t_data.get("agent"),
                            tools=t_data.get("tools", []),
                            depends_on=t_data.get("depends_on", []),
                            estimated_effort_hours=t_data.get("effort_hours", 0),
                            notes=t_data.get("notes", ""),
                        )
                        sp.tasks.append(task)
                    break
        plan.to_file()
        return plan

    def update_task_status(self, plan: Plan, task_id: str, status: TaskStatus, results: dict | None = None) -> Plan:
        """Met à jour le statut d'une tâche."""
        for g in plan.mission.goals:
            for sp in g.sub_projects:
                for t in sp.tasks:
                    if t.id == task_id:
                        t.status = status
                        if status == TaskStatus.COMPLETED and t.dod:
                            ok, _ = t.dod.is_satisfied(results)
                            if not ok:
                                logger.warning("Task %s marked complete but DoD not satisfied", task_id)
                        # Cascade : vérifier si le sous-projet est complet
                        if all(tt.status == TaskStatus.COMPLETED for tt in sp.tasks):
                            sp.status = TaskStatus.COMPLETED
                        # Cascade : vérifier si l'objectif est complet
                        if all(ssp.status == TaskStatus.COMPLETED for ssp in g.sub_projects):
                            g.status = TaskStatus.COMPLETED
                        # Cascade : vérifier si la mission est complète
                        if all(gg.status == TaskStatus.COMPLETED for gg in plan.mission.goals):
                            plan.mission.status = TaskStatus.COMPLETED
                        break
        plan.to_file()
        return plan

    def adapt_plan(self, plan: Plan, blocked_task_id: str, reason: str) -> Plan:
        """Adapte le plan en cas de blocage (débat interne §5.3.2)."""
        for g in plan.mission.goals:
            for sp in g.sub_projects:
                for t in sp.tasks:
                    if t.id == blocked_task_id:
                        t.status = TaskStatus.BLOCKED
                        t.notes = f"BLOCKED: {reason}"
                        logger.info("Task %s blocked: %s", t.description, reason)
                        break
        plan.to_file()
        return plan

    def list_plans(self) -> list[str]:
        return [p.stem for p in PLANNING_DIR.glob("*.json")]


# ─── Singleton ───────────────────────────────────────────────────────────

app_context.caches.planning_engine: PlanningEngine | None = None


def get_planning_engine() -> PlanningEngine:
    if app_context.caches.planning_engine is None:
        app_context.caches.planning_engine = PlanningEngine()
    return app_context.caches.planning_engine
