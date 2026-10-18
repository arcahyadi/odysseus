"""
Governance — Budgets granulaires, auto-pause, heartbeat, approval gates.
Patterns inspirés de Paperclip.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GovernanceManager:
    """Gestion des budgets agents + auto-pause + heartbeat."""

    def __init__(self, db_session_factory):
        self.get_db = db_session_factory

    # ---- Budgets ----

    def register_agent_run(
        self,
        agent_id: str,
        run_id: str,
        project_id: str | None = None,
        max_tokens: int = 100000,
        max_cost_usd: float = 5.0,
        max_iterations: int = 50,
    ) -> dict:
        """Enregistre un run agent avec ses budgets."""
        from core.database import AgentBudget

        with self.get_db() as db:
            budget = AgentBudget(
                agent_id=agent_id,
                run_id=run_id,
                project_id=project_id,
                max_tokens=max_tokens,
                max_cost_usd=max_cost_usd,
                max_iterations=max_iterations,
            )
            db.add(budget)
            db.commit()
            return {
                "ok": True,
                "run_id": run_id,
                "agent_id": agent_id,
                "max_tokens": max_tokens,
                "max_cost_usd": max_cost_usd,
                "max_iterations": max_iterations,
            }

    def consume_budget(self, run_id: str, tokens: int = 0, cost_usd: float = 0.0, iterations: int = 0) -> dict:
        """
        Met à jour la consommation.
        Retourne {'ok': bool, 'status': str, 'reason': str, 'percent': float}
        Auto-pause si budget dépassé.
        """
        from core.database import AgentBudget

        with self.get_db() as db:
            budget = db.query(AgentBudget).filter(AgentBudget.run_id == run_id).first()
            if not budget:
                return {"ok": False, "status": "not_found", "reason": "run_id not found", "percent": 0.0}

            if budget.status == "exhausted":
                return {
                    "ok": False,
                    "status": "exhausted",
                    "reason": budget.paused_reason or "budget exhausted",
                    "percent": 100.0,
                }

            budget.tokens_used = (budget.tokens_used or 0) + tokens
            budget.cost_usd = (budget.cost_usd or 0.0) + cost_usd
            budget.iterations = (budget.iterations or 0) + iterations

            # Compute highest consumption percent
            pct_tokens = (budget.tokens_used / budget.max_tokens * 100) if budget.max_tokens else 0
            pct_cost = (budget.cost_usd / budget.max_cost_usd * 100) if budget.max_cost_usd else 0
            pct_iter = (budget.iterations / budget.max_iterations * 100) if budget.max_iterations else 0
            percent = max(pct_tokens, pct_cost, pct_iter)

            reason = ""
            if percent >= 100:
                budget.status = "exhausted"
                budget.paused_reason = f"budget exhausted ({percent:.1f}%)"
                budget.paused_at = datetime.utcnow()
                reason = budget.paused_reason
                db.commit()
                return {"ok": False, "status": "exhausted", "reason": reason, "percent": percent}
            elif percent >= (budget.alert_at_percent or 80):
                reason = f"alert threshold reached ({percent:.1f}%)"

            db.commit()
            return {"ok": True, "status": budget.status, "reason": reason, "percent": percent}

    def get_budget_status(self, run_id: str) -> dict | None:
        """Statut budget d'un run."""
        from core.database import AgentBudget

        with self.get_db() as db:
            budget = db.query(AgentBudget).filter(AgentBudget.run_id == run_id).first()
            if not budget:
                return None
            return {
                "run_id": run_id,
                "agent_id": budget.agent_id,
                "status": budget.status,
                "tokens_used": budget.tokens_used,
                "max_tokens": budget.max_tokens,
                "cost_usd": budget.cost_usd,
                "max_cost_usd": budget.max_cost_usd,
                "iterations": budget.iterations,
                "max_iterations": budget.max_iterations,
                "paused_reason": budget.paused_reason,
            }

    def is_agent_paused(self, agent_id: str) -> bool:
        """Vérifie si un agent est auto-pausé (au moins un run exhausted/paused)."""
        from core.database import AgentBudget

        with self.get_db() as db:
            count = (
                db.query(AgentBudget)
                .filter(
                    AgentBudget.agent_id == agent_id,
                    AgentBudget.status.in_(["exhausted", "paused"]),
                )
                .count()
            )
            return count > 0

    # ---- Heartbeat ----

    def update_heartbeat(
        self,
        agent_id: str,
        task_id: str | None,
        context_snapshot: dict,
        checklist: list,
        last_action: str,
        next_run_in_seconds: int = 300,
    ) -> None:
        """Met à jour le heartbeat d'un agent (contexte pour le prochain réveil)."""
        from core.database import AgentHeartbeat

        now = datetime.utcnow()
        with self.get_db() as db:
            hb = db.query(AgentHeartbeat).filter(AgentHeartbeat.agent_id == agent_id).first()
            if hb is None:
                hb = AgentHeartbeat(agent_id=agent_id)
                db.add(hb)

            hb.task_id = task_id
            hb.context_snapshot = json.dumps(context_snapshot, ensure_ascii=False)
            hb.checklist = json.dumps(checklist, ensure_ascii=False)
            hb.last_action = last_action
            hb.last_run_at = now
            hb.next_run_at = now + timedelta(seconds=next_run_in_seconds)
            hb.run_count = (hb.run_count or 0) + 1
            db.commit()

    def get_heartbeat_context(self, agent_id: str) -> dict | None:
        """
        Retourne le contexte à injecter au réveil de l'agent.
        Pattern "Memento Man" : l'agent est amnésique, on lui donne sa checklist.
        """
        from core.database import AgentHeartbeat

        with self.get_db() as db:
            hb = db.query(AgentHeartbeat).filter(AgentHeartbeat.agent_id == agent_id).first()
            if not hb:
                return None
            return {
                "agent_id": agent_id,
                "task_id": hb.task_id,
                "context_snapshot": json.loads(hb.context_snapshot) if hb.context_snapshot else {},
                "checklist": json.loads(hb.checklist) if hb.checklist else [],
                "last_action": hb.last_action,
                "last_run_at": hb.last_run_at.isoformat() if hb.last_run_at else None,
                "next_run_at": hb.next_run_at.isoformat() if hb.next_run_at else None,
                "run_count": hb.run_count,
            }

    # ---- Goal ancestry ----

    def create_task_with_ancestry(self, project_id: str, task_name: str, description: str, agent_id: str) -> dict:
        """Crée une tâche avec son ancestry_path complet."""
        from core.database import GoalProject, GoalTask

        with self.get_db() as db:
            project = db.query(GoalProject).filter(GoalProject.id == project_id).first()
            if not project:
                return {"ok": False, "error": "project not found"}

            goal = project.goal
            mission = goal.mission if goal else None

            parts = []
            if mission:
                parts.append(mission.name)
            if goal:
                parts.append(goal.name)
            parts.append(project.name)
            parts.append(task_name)
            ancestry_path = " > ".join(parts)

            task = GoalTask(
                project_id=project_id,
                name=task_name,
                description=description,
                agent_id=agent_id,
                ancestry_path=ancestry_path,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return {"ok": True, "task_id": task.id, "ancestry_path": ancestry_path}

    def get_ancestry(self, task_id: str) -> str:
        """Retourne le chemin complet mission > goal > project > task."""
        from core.database import GoalTask

        with self.get_db() as db:
            task = db.query(GoalTask).filter(GoalTask.id == task_id).first()
            if not task:
                return ""
            return task.ancestry_path or ""

    # ---- Approval gates ----

    def request_approval(self, action_description: str, risk_level: str, agent_id: str, run_id: str) -> dict:
        """
        Pour les actions destructives : log l'approbation requise.
        Retourne {'approved': bool, 'gate_id': str, 'message': str}
        En mode auto : auto-approve tout sauf DESTRUCTIVE.
        En mode interactive : retourner pending pour les actions DESTRUCTIVE.
        """
        gate_id = str(uuid.uuid4())
        risk_upper = risk_level.upper()

        if risk_upper == "DESTRUCTIVE":
            logger.warning(
                "[APPROVAL GATE %s] DESTRUCTIVE action requested by agent=%s run=%s: %s",
                gate_id,
                agent_id,
                run_id,
                action_description,
            )
            return {
                "approved": False,
                "gate_id": gate_id,
                "message": f"DESTRUCTIVE action requires manual approval: {action_description}",
            }

        logger.info(
            "[APPROVAL GATE %s] Auto-approved risk=%s agent=%s: %s",
            gate_id,
            risk_level,
            agent_id,
            action_description,
        )
        return {
            "approved": True,
            "gate_id": gate_id,
            "message": f"Auto-approved ({risk_level}): {action_description}",
        }
