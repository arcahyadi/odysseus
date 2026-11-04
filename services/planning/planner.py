"""
services/planning/planner.py

Goal decomposition via LLM + Plan/PlanStep persistence.

Requirements: 5.1, 5.2, 5.3, 5.4
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Optional

import httpx

from core.database import Plan, PlanStep, SessionLocal, utcnow_naive

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = (
    'You are a planning assistant. Break the following goal into an ordered list of '
    '2 to 50 concrete, actionable steps. Return JSON only — no markdown fences, no explanation:\n'
    '{{"steps": [{{"title": "...", "description": "..."}}]}}\n'
    'Goal: {goal}'
)

# Strips ```json ... ``` or ``` ... ``` fences from LLM output.
_FENCE_RE = re.compile(r"^```[a-z]*\s*(.*?)\s*```$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    m = _FENCE_RE.match(text.strip())
    return m.group(1) if m else text.strip()


def _build_completion_url(endpoint_url: str) -> str:
    """
    Build the chat/completions URL from endpoint_url.

    - Strips trailing slashes.
    - If the URL already contains '/v1', appends only '/chat/completions'.
    - Otherwise appends '/v1/chat/completions'.
    """
    base = endpoint_url.rstrip("/")
    if "/v1" in base:
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


async def decompose_goal(
    goal: str,
    endpoint_url: str,
    model: str,
    headers: dict = {},
) -> list[dict]:
    """
    Call the LLM at endpoint_url to decompose *goal* into steps.

    Returns a list of {"title": str, "description": str} dicts.
    Raises ValueError if step count is outside [2, 50] or on LLM/parse failure.

    Requirements: 5.3
    """
    prompt = DECOMPOSE_PROMPT.format(goal=goal)
    url = _build_completion_url(endpoint_url)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"LLM request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unexpected LLM response structure: {exc}") from exc

    content = _strip_fences(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}\nRaw: {content!r}") from exc

    steps: list[dict] = parsed.get("steps", [])

    if len(steps) < 2:
        raise ValueError(
            f"Plan must have at least 2 steps; LLM returned {len(steps)}."
        )
    if len(steps) > 50:
        raise ValueError(
            f"Plan must have at most 50 steps; LLM returned {len(steps)}."
        )

    return steps


async def create_plan(
    owner: str,
    goal: str,
    endpoint_url: str,
    model: str,
    headers: dict = {},
) -> Plan:
    """
    Decompose *goal* into steps via LLM, then persist Plan + PlanStep records
    in a single DB transaction.

    Returns the new Plan ORM object.

    Requirements: 5.1, 5.2, 5.4
    """
    steps = await decompose_goal(goal, endpoint_url, model, headers)

    db = SessionLocal()
    try:
        plan_id = str(uuid.uuid4())
        plan = Plan(
            id=plan_id,
            owner=owner,
            title=goal[:120],
            goal=goal,
            status="pending",
            current_step_index=0,
            model=model,
            endpoint_url=endpoint_url,
        )
        db.add(plan)

        for i, step in enumerate(steps):
            plan_step = PlanStep(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                order_index=i,
                title=step.get("title", "")[:120],
                description=step.get("description"),
                status="pending",
            )
            db.add(plan_step)

        db.commit()
        db.refresh(plan)
        logger.info(
            "Created plan %s for owner=%s with %d steps", plan_id, owner, len(steps)
        )
        return plan
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
