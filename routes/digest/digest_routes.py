"""
routes/digest/digest_routes.py

Auto-digest API: generate, list, search, get by date.
Requirements: 6.5–6.7, 7.1–7.2
"""
import asyncio
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.digest.digest_service import digest_service
from src.auth_helpers import get_current_user
from src.task_endpoint import resolve_task_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digest")


class GenerateRequest(BaseModel):
    date: Optional[str] = None      # "YYYY-MM-DD" or omit for yesterday
    model: Optional[str] = None
    endpoint_url: Optional[str] = None


# NOTE: /search must be registered BEFORE /{date} to avoid path ambiguity.

@router.get("/search")
def search_digests(request: Request, q: str = ""):
    """Full-text search over digests. Req 7.1, 7.2"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="q parameter is required and must not be blank")
    results = digest_service.search(user, q)
    return {"digests": results, "count": len(results)}


@router.post("/generate", status_code=202)
async def generate_digest(request: Request, body: GenerateRequest = None):
    """On-demand digest generation. Req 6.5"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    body = body or GenerateRequest()
    target_date = None
    if body.date:
        try:
            target_date = date.fromisoformat(body.date)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid date: {body.date!r}")

    # Resolve an endpoint before scheduling. DigestService.generate uses
    # endpoint_url/model verbatim and does not resolve defaults, so passing the
    # UI's empty body straight through built the URL "/v1/chat/completions" and
    # always persisted status="failed" - "Generate now" could never succeed.
    # Caller-supplied values still win, as fallbacks.
    try:
        url, model, headers = resolve_task_endpoint(
            body.endpoint_url, body.model, None, owner=user
        )
    except Exception as exc:
        logger.warning("digest generate: endpoint resolution failed: %s", exc)
        url, model, headers = body.endpoint_url, body.model, None

    if not url or not model:
        raise HTTPException(
            status_code=503,
            detail="No model endpoint available for digest generation. "
                   "Set a default model in Settings.",
        )

    # Name the row generate() is about to create, so the id we hand back is
    # pollable instead of a freshly-minted uuid that never matches.
    digest_id = digest_service.pending_id(user, target_date)

    asyncio.create_task(digest_service.generate(
        owner=user,
        target_date=target_date,
        endpoint_url=url,
        model=model,
        headers=headers,
        digest_id=digest_id,
    ))
    return {"ok": True, "digest_id": digest_id, "status": "pending"}


@router.get("/")
def list_digests(request: Request, limit: int = 30, offset: int = 0):
    """List digests for current user. Req 6.6"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    digests = digest_service.list_digests(user, limit=limit, offset=offset)
    return {"digests": digests, "total": len(digests)}


@router.get("/{digest_date}")
def get_digest_by_date(digest_date: str, request: Request):
    """Get a single digest by date. Req 6.7"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    digest = digest_service.get_by_date(user, digest_date)
    if digest is None:
        raise HTTPException(status_code=404, detail=f"No digest found for date {digest_date!r}")
    return digest
