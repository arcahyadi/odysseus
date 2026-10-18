"""
Budget Enforcer — Track les tokens/itérations/coûts et coupe la loop si dépassement.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from src.project_manifest import ProjectBudget

logger = logging.getLogger(__name__)


@dataclass
class BudgetUsage:
    tokens_used: int = 0
    iterations: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0


class BudgetEnforcer:
    """Thread-safe budget tracker pour un run agent."""

    def __init__(self, budget: ProjectBudget, run_id: str):
        self.budget = budget
        self.run_id = run_id
        self.usage = BudgetUsage()
        self._lock = threading.Lock()
        self._paused = False

    def consume_tokens(self, count: int, cost_usd: float = 0.0) -> dict:
        """Enregistre la consommation de tokens. Retourne {'ok': bool, 'reason': str}."""
        with self._lock:
            self.usage.tokens_used += count
            self.usage.cost_usd += cost_usd
            if self.usage.tokens_used > self.budget.max_tokens:
                reason = f"Token budget exceeded: {self.usage.tokens_used} / {self.budget.max_tokens}"
                logger.warning("[%s] %s", self.run_id, reason)
                return {"ok": False, "reason": reason}
            if self.usage.cost_usd > self.budget.max_cost_usd:
                reason = f"Cost budget exceeded: ${self.usage.cost_usd:.4f} / ${self.budget.max_cost_usd:.4f}"
                logger.warning("[%s] %s", self.run_id, reason)
                return {"ok": False, "reason": reason}
            return {"ok": True, "reason": ""}

    def consume_iteration(self) -> dict:
        """Incrémente le compteur d'itérations. Retourne {'ok': bool, 'reason': str}."""
        with self._lock:
            self.usage.iterations += 1
            if self.usage.iterations > self.budget.max_iterations:
                reason = f"Iteration budget exceeded: {self.usage.iterations} / {self.budget.max_iterations}"
                logger.warning("[%s] %s", self.run_id, reason)
                return {"ok": False, "reason": reason}
            return {"ok": True, "reason": ""}

    def consume_tool_call(self) -> dict:
        """Incrémente le compteur de tool calls. Retourne {'ok': bool, 'reason': str}."""
        with self._lock:
            self.usage.tool_calls += 1
            if self.usage.tool_calls > self.budget.max_tool_calls:
                reason = f"Tool call budget exceeded: {self.usage.tool_calls} / {self.budget.max_tool_calls}"
                logger.warning("[%s] %s", self.run_id, reason)
                return {"ok": False, "reason": reason}
            return {"ok": True, "reason": ""}

    def is_budget_ok(self) -> dict:
        """Vérifie si on est dans les limites. Retourne {'ok': bool, 'reason': str, 'percent': float}."""
        with self._lock:
            checks = [
                (self.usage.tokens_used, self.budget.max_tokens, "tokens"),
                (self.usage.iterations, self.budget.max_iterations, "iterations"),
                (self.usage.tool_calls, self.budget.max_tool_calls, "tool_calls"),
            ]
            # Cost check (float)
            if self.budget.max_cost_usd > 0:
                cost_pct = (self.usage.cost_usd / self.budget.max_cost_usd) * 100
                if cost_pct > 100:
                    return {
                        "ok": False,
                        "reason": f"Cost budget exceeded ({cost_pct:.1f}%)",
                        "percent": cost_pct,
                    }

            max_pct = 0.0
            for used, limit, label in checks:
                if limit <= 0:
                    continue
                pct = (used / limit) * 100
                max_pct = max(max_pct, pct)
                if pct > 100:
                    return {
                        "ok": False,
                        "reason": f"{label} budget exceeded ({pct:.1f}%)",
                        "percent": pct,
                    }
            return {"ok": True, "reason": "", "percent": max_pct}

    def get_usage_report(self) -> dict:
        """Rapport de consommation actuel vs budgets."""
        with self._lock:
            return {
                "run_id": self.run_id,
                "usage": {
                    "tokens_used": self.usage.tokens_used,
                    "iterations": self.usage.iterations,
                    "cost_usd": round(self.usage.cost_usd, 6),
                    "tool_calls": self.usage.tool_calls,
                },
                "budget": {
                    "max_tokens": self.budget.max_tokens,
                    "max_iterations": self.budget.max_iterations,
                    "max_cost_usd": self.budget.max_cost_usd,
                    "max_tool_calls": self.budget.max_tool_calls,
                    "alert_at_percent": self.budget.alert_at_percent,
                },
                "percent": {
                    "tokens": round(
                        (self.usage.tokens_used / self.budget.max_tokens * 100) if self.budget.max_tokens > 0 else 0,
                        1,
                    ),
                    "iterations": round(
                        (self.usage.iterations / self.budget.max_iterations * 100)
                        if self.budget.max_iterations > 0
                        else 0,
                        1,
                    ),
                    "cost_usd": round(
                        (self.usage.cost_usd / self.budget.max_cost_usd * 100) if self.budget.max_cost_usd > 0 else 0,
                        1,
                    ),
                    "tool_calls": round(
                        (self.usage.tool_calls / self.budget.max_tool_calls * 100)
                        if self.budget.max_tool_calls > 0
                        else 0,
                        1,
                    ),
                },
                "paused": self._paused,
            }

    def alert_threshold_reached(self) -> bool:
        """True si on a atteint le seuil d'alerte (alert_at_percent)."""
        with self._lock:
            threshold = self.budget.alert_at_percent
            checks = [
                (self.usage.tokens_used, self.budget.max_tokens),
                (self.usage.iterations, self.budget.max_iterations),
                (self.usage.cost_usd, self.budget.max_cost_usd),
                (self.usage.tool_calls, self.budget.max_tool_calls),
            ]
            for used, limit in checks:
                if limit > 0 and (used / limit * 100) >= threshold:
                    return True
            return False


class BudgetRegistry:
    """Registry global des BudgetEnforcer actifs (un par run)."""

    _instance: Optional["BudgetRegistry"] = None
    _enforcers: dict[str, BudgetEnforcer] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BudgetRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register(self, run_id: str, enforcer: BudgetEnforcer) -> None:
        with self._lock:
            self._enforcers[run_id] = enforcer
            logger.debug("BudgetRegistry: registered run %s", run_id)

    def get(self, run_id: str) -> BudgetEnforcer | None:
        with self._lock:
            return self._enforcers.get(run_id)

    def unregister(self, run_id: str) -> None:
        with self._lock:
            self._enforcers.pop(run_id, None)
            logger.debug("BudgetRegistry: unregistered run %s", run_id)

    def auto_pause_if_exceeded(self, run_id: str) -> bool:
        """Auto-pause le run si budget dépassé. Retourne True si pausé."""
        enforcer = self.get(run_id)
        if enforcer is None:
            return False
        status = enforcer.is_budget_ok()
        if not status["ok"]:
            with enforcer._lock:
                enforcer._paused = True
            logger.warning("BudgetRegistry: auto-paused run %s — %s", run_id, status["reason"])
            return True
        return False
