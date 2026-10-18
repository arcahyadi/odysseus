"""Audit routes — read back what the agent loop decided and did.

`GET /api/audit/traces` is the reading half of `src/trace_writer.py`. Until
this item (Sprint 3 v5, item 9 / UC-12) the trail under `data/traces/` was
write-only: `write_trace` existed, nothing read it, and the AUTOEVAL decision
was not written at all. A trail nobody can read is a debugging artefact, not
an audit — and the fiche said so.

Two properties this route must not lose, and why:

* **`require_admin`.** The records carry tool arguments (`args_summary`) and the
  verifier's failure reasons. That is not anonymous telemetry, so the route
  follows the convention of the other sensitive read routes
  (`diagnostics_routes.py`) rather than being public. Before the auth manager
  is configured the answer is 403, not 200 — see `core/middleware.require_admin`.
* **`malformed` is reported, never hidden.** A JSONL file torn by a crash ends
  on a half-written line. Skipping it silently would render an audit cleaner
  than the truth, and the person relying on it is the one an audit exists for.

Filters (`run_id`, `session_id`, `kind`, `day`) exist because an unfiltered
trail is unusable the moment there is more than one run: a decision has to be
joinable back to the run that produced it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from core.middleware import require_admin
from src import trace_writer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/traces")
async def get_audit_traces(
    request: Request,
    run_id: str | None = None,
    session_id: str | None = None,
    kind: str | None = None,
    day: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Return recorded audit traces, most recent last, plus the malformed count.

    `day` is a `YYYY-MM-DD` file name stem. It is only ever used to build a file
    name inside the traces directory — never as part of a caller-supplied path,
    so this is not a file browser. A `day` that does not exist yields an empty
    trail, not a 404: "nothing audited that day" is an answer, not an error.
    """
    require_admin(request)

    # One guard, not two. An earlier version checked the date here *and* in the
    # reader; measured, the route's check masked the reader's, so deleting the
    # reader's guard left all ten route tests green. The invariant lives where
    # the path is built — `read_traces` — and this route only turns its refusal
    # into an answer. Duplicating it would have restored the illusion of a
    # second safety net that nothing measured.
    try:
        traces, malformed = trace_writer.read_traces(
            run_id=run_id,
            session_id=session_id,
            kind=kind,
            limit=limit,
            day=day,
        )
    except ValueError as e:
        return {"ok": False, "error": str(e), "traces": [], "malformed": 0}
    return {"ok": True, "traces": traces, "malformed": malformed, "count": len(traces)}
