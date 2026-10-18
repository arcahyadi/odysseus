"""n8n workflow integration routes.

Kill-switched behind ODYSSEUS_N8N (default OFF). When off, the trigger
endpoint returns 503 Service Unavailable. When on, it proxies workflow
trigger requests to the local n8n instance via its webhook API.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/n8n", tags=["n8n"])

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
_TRUTHY = {"1", "true", "yes", "on"}


def _n8n_enabled() -> bool:
    return os.environ.get("ODYSSEUS_N8N", "off").strip().lower() in _TRUTHY


class WorkflowTriggerRequest(BaseModel):
    """Optional payload forwarded to the n8n webhook node."""

    data: dict[str, Any] | None = None


class WorkflowTriggerResponse(BaseModel):
    workflow_id: str
    status: str
    result: dict[str, Any] | None = None


@router.post("/trigger/{workflow_id}", response_model=WorkflowTriggerResponse)
async def trigger_workflow(
    workflow_id: str,
    body: WorkflowTriggerRequest | None = None,
) -> WorkflowTriggerResponse:
    """Trigger an n8n workflow by its webhook URL.

    The workflow must have a **Webhook** trigger node configured with URL
    path ``/webhook/{workflow_id}``. This endpoint proxies the request and
    returns the n8n execution result.

    Requires ``ODYSSEUS_N8N=on``.
    """
    if not _n8n_enabled():
        raise HTTPException(
            status_code=503,
            detail="n8n integration is disabled. Set ODYSSEUS_N8N=on to enable.",
        )

    webhook_url = f"{N8N_BASE_URL}/webhook/{workflow_id}"
    payload = body.model_dump() if body else {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="n8n webhook timed out")
    except httpx.HTTPStatusError as exc:
        logger.warning("n8n workflow %s returned %s", workflow_id, exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"n8n returned {exc.response.status_code}: {exc.response.text[:500]}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach n8n. Is the n8n container running? (profile: automation)",
        )

    try:
        result = resp.json()
    except ValueError:
        result = {"raw": resp.text}

    return WorkflowTriggerResponse(
        workflow_id=workflow_id,
        status="executed",
        result=result,
    )


@router.get("/health")
async def n8n_health() -> dict[str, Any]:
    """Check if n8n is reachable and the kill-switch state."""
    enabled = _n8n_enabled()
    if not enabled:
        return {"enabled": False, "reachable": False, "reason": "kill-switch OFF"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{N8N_BASE_URL}/healthz")
            reachable = resp.status_code == 200
    except Exception:
        reachable = False

    return {"enabled": True, "reachable": reachable}
