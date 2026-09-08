"""
services/planning/executor.py

Sequential plan step execution with pause/cancel/retry support.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from core.database import Plan, PlanStep, SessionLocal, utcnow_naive

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("PLAN_STEP_MAX_RETRIES", "2"))


class PlanExecutor:
    def __init__(self) -> None:
        # plan_id -> bool  (True = cancel requested)
        self._cancelled: dict[str, bool] = {}
        # plan_id -> bool  (True = paused)
        self._paused: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def pause(self, plan_id: str) -> None:
        """Flag *plan_id* as paused. The execute loop will spin until resumed."""
        self._paused[plan_id] = True

    def resume(self, plan_id: str) -> None:
        """Clear the paused flag for *plan_id*."""
        self._paused.pop(plan_id, None)

    def cancel(self, plan_id: str) -> None:
        """Flag *plan_id* for cancellation at the next loop iteration."""
        self._cancelled[plan_id] = True

    # ------------------------------------------------------------------
    # Main execution loop
    # ------------------------------------------------------------------

    async def execute(
        self,
        plan_id: str,
        owner: str,
        endpoint_url: str = "",
        model: str = "",
        headers: dict = {},
    ) -> None:
        """
        Sequential execution of plan steps.

        - Skips steps already in status 'done' or 'skipped' (resumption support).
        - Retries failed steps up to MAX_RETRIES before marking the plan
          'paused_on_failure'.
        - Sets plan status to 'completed' when all steps are done/skipped.
        - Checks the _cancelled flag at the top of every iteration.
        - Checks the _paused flag; if paused, sleeps 1 s and retries the check.

        Requirements: 6.1, 6.3, 6.4, 6.5, 6.6
        """
        # Load plan and its steps ordered by order_index.
        db = SessionLocal()
        try:
            plan: Optional[Plan] = db.query(Plan).filter_by(id=plan_id, owner=owner).first()
            if plan is None:
                logger.error("Plan %s not found for owner=%s", plan_id, owner)
                return

            steps: list[PlanStep] = (
                db.query(PlanStep)
                .filter_by(plan_id=plan_id)
                .order_by(PlanStep.order_index)
                .all()
            )
        finally:
            db.close()

        # Mark plan as running
        self._set_plan_status(plan_id, "running")

        for step in steps:
            # --- Pause check ---
            while self._paused.get(plan_id):
                await asyncio.sleep(1.0)

            # --- Cancel check ---
            if self._cancelled.get(plan_id):
                self._set_plan_status(plan_id, "cancelled")
                logger.info("Plan %s cancelled before step %s", plan_id, step.id)
                return

            # --- Skip already-terminal steps (resumption) ---
            if step.status in ("done", "skipped"):
                continue

            # --- Execute with retries ---
            retry = 0
            while retry <= MAX_RETRIES:
                # Re-check pause/cancel inside retry loop too
                while self._paused.get(plan_id):
                    await asyncio.sleep(1.0)

                if self._cancelled.get(plan_id):
                    self._set_plan_status(plan_id, "cancelled")
                    logger.info(
                        "Plan %s cancelled during step %s retry %d",
                        plan_id, step.id, retry,
                    )
                    return

                try:
                    await self._execute_step(plan, step, owner, endpoint_url, model, headers)
                    # Success — reload status from DB to confirm
                    fresh_status = self._get_step_status(step.id)
                    if fresh_status == "done":
                        break
                    # If _execute_step left it as something other than done,
                    # treat as failure and allow retry.
                    raise RuntimeError(f"Step ended with unexpected status: {fresh_status!r}")
                except Exception as exc:
                    retry += 1
                    logger.warning(
                        "Step %s failed (attempt %d/%d): %s",
                        step.id, retry, MAX_RETRIES + 1, exc,
                    )
                    if retry > MAX_RETRIES:
                        # Exhausted retries — halt plan
                        self._set_step_error(step.id, str(exc))
                        self._set_plan_status(plan_id, "paused_on_failure")
                        logger.warning(
                            "Plan %s paused_on_failure after step %s exhausted retries",
                            plan_id, step.id,
                        )
                        return
                    # Brief back-off before next retry
                    await asyncio.sleep(1.0)

        # All steps processed — check if truly all done/skipped
        if self._all_steps_terminal(plan_id):
            self._set_plan_status(plan_id, "completed")
            logger.info("Plan %s completed", plan_id)
        else:
            # Some steps remain pending — shouldn't normally happen, but be safe
            self._set_plan_status(plan_id, "paused_on_failure")

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        plan: Plan,
        step: PlanStep,
        owner: str,
        endpoint_url: str,
        model: str,
        headers: dict,
    ) -> None:
        """
        Execute a single PlanStep.

        Stub implementation: output = "Completed: {step.description}".
        Sets step.status to 'running', then 'done' on success, 'failed' on
        exception. Persists started_at, ended_at, and output before marking done.

        Requirements: 6.2
        """
        db = SessionLocal()
        try:
            db_step: Optional[PlanStep] = db.query(PlanStep).filter_by(id=step.id).first()
            if db_step is None:
                raise RuntimeError(f"PlanStep {step.id} not found in DB")

            # Mark running
            db_step.status = "running"
            db_step.started_at = utcnow_naive()
            db.commit()

            # --- Stub execution ---
            description = db_step.description or db_step.title
            output = f"Completed: {description}"

            # Persist output
            db_step.output = output
            db_step.ended_at = utcnow_naive()
            db_step.status = "done"
            db.commit()

            # Reflect in-memory object for the caller
            step.status = "done"
            step.output = output

        except Exception as exc:
            # Mark as failed and persist
            try:
                if db_step is not None:
                    db_step.status = "failed"
                    db_step.ended_at = utcnow_naive()
                    db_step.error_detail = str(exc)
                    db.commit()
                    step.status = "failed"
            except Exception:
                db.rollback()
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # DB helper methods
    # ------------------------------------------------------------------

    def _set_plan_status(self, plan_id: str, status: str) -> None:
        db = SessionLocal()
        try:
            plan = db.query(Plan).filter_by(id=plan_id).first()
            if plan:
                plan.status = status
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to set plan %s status to %s", plan_id, status)
        finally:
            db.close()

    def _get_step_status(self, step_id: str) -> str:
        db = SessionLocal()
        try:
            step = db.query(PlanStep).filter_by(id=step_id).first()
            return step.status if step else "unknown"
        finally:
            db.close()

    def _set_step_error(self, step_id: str, error: str) -> None:
        db = SessionLocal()
        try:
            step = db.query(PlanStep).filter_by(id=step_id).first()
            if step:
                step.status = "failed"
                step.error_detail = error
                step.ended_at = utcnow_naive()
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to set error on step %s", step_id)
        finally:
            db.close()

    def _all_steps_terminal(self, plan_id: str) -> bool:
        """Return True if every step for *plan_id* is in a terminal status."""
        db = SessionLocal()
        try:
            non_terminal = (
                db.query(PlanStep)
                .filter(
                    PlanStep.plan_id == plan_id,
                    ~PlanStep.status.in_(["done", "skipped", "failed"]),
                )
                .count()
            )
            return non_terminal == 0
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

plan_executor = PlanExecutor()
