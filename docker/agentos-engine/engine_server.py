"""
AgentOS Engine Bridge Server — runs inside agentos-engine container.

Receives agent requests via HTTP, runs the REAL OpenCodeEngine pipeline,
returns SSE stream.

Contrat bridge (master-ref 03-OBJECTIFS-SYSTEME):
  POST /run { message, session }
  → SSE stream: phase_enter/phase_exit/agent_dispatch/model_selected/...
  → data: [DONE]
  → traces JSONL persistés dans /home/agentos/data/traces/
  → memory [observed] dans /home/agentos/obsidian-vault/topics/
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

# Add the engine source to path (we COPY src/ + core/ into /home/agentos/)
sys.path.insert(0, "/home/agentos")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("agentos-engine")

# ====================================================================
# Paths (Docker volumes)
# ====================================================================
# Overridable via env (tests dev-host; container defaults are /home/agentos/*)
DATA_DIR = Path(os.environ.get("AGENTOS_DATA_DIR", "/home/agentos/data"))
WORKSPACE_DIR = Path(os.environ.get("AGENTOS_WORKSPACE_DIR", "/home/agentos/workspace"))
VAULT_DIR = Path(os.environ.get("AGENTOS_VAULT_DIR", "/home/agentos/obsidian-vault"))
TRACE_DIR = DATA_DIR / "traces"

for d in [DATA_DIR, WORKSPACE_DIR, VAULT_DIR, TRACE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Override memory writer base path so facts land in the vault volume
os.environ.setdefault("OBSIDIAN_VAULT_PATH", str(VAULT_DIR))

# ====================================================================
# Import the REAL pipeline
# ====================================================================
try:
    from src.opencode_engine import PHASES, OpenCodeEngine

    ENGINE_AVAILABLE = True
    logger.info("OpenCodeEngine loaded — real pipeline active")
except Exception as e:
    ENGINE_AVAILABLE = False
    PHASES = ["CLASSIFY", "KNOW", "PLAN", "BUILD", "QUALITY", "AUTOEVAL", "MEMORY_OBSERVE"]
    logger.error(f"OpenCodeEngine import failed: {e}. Fallback to stub mode.")
    logger.error("Engine will emit phases without real agent dispatch.")

# App
app = FastAPI(title="AgentOS Engine", version="1.0.0")

# State
sessions: dict = {}
runs = 0


# ====================================================================
# Helpers
# ====================================================================
def _write_trace(session_id: str, message: str, phase_events: list, duration_ms: int):
    """Persist run trace as JSONL for auditability (UC-12)."""
    trace_file = TRACE_DIR / f"events-{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"
    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "session": session_id,
                    "message": message[:200],
                    "phases": PHASES,
                    "duration_ms": duration_ms,
                    "runs_total": runs,
                    "events_count": len(phase_events),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _write_observed_fact(domain: str, fact: str):
    """Write an [observed] fact to the vault (memory provenance P16)."""
    topics_dir = VAULT_DIR / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    fp = topics_dir / f"{domain}.md"
    entry = f"- [observed] {fact}"
    if fp.exists():
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        if entry in content:
            return
        content = content.rstrip() + f"\n{entry}\n"
    else:
        content = f"---\nname: {domain}\ndescription: Facts about {domain}\nsources: [engine]\n---\n\n{entry}\n"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)


# ====================================================================
# Real pipeline — wraps OpenCodeEngine.walk()
# ====================================================================
async def run_pipeline_real(message: str, session_id: str):
    """Run the real OpenCodeEngine.walk() and forward SSE events."""
    global runs
    runs += 1
    start_time = time.time()
    phase_events: list = []

    # Build the engine instance
    engine = OpenCodeEngine(
        session_id=session_id,
        message=message,
        worktree=str(WORKSPACE_DIR),
    )

    # Agent stream stub — in the real engine, agent_stream_fn is a callable
    # provided by the host (chat_routes passes the LLM stream). Inside the
    # isolated Docker engine, we don't have a live LLM key by default, so
    # we provide a no-op generator that the engine can still walk through.
    # BUILD phase will emit phase_active + forward whatever chunks this yields.
    async def _no_op_agent_stream():
        # In production, this would call OpenCode CLI subprocess.
        # For V1, we yield a status event per phase so the client sees progress.
        yield f"data: {json.dumps({'type': 'agent_yield', 'note': 'engine isolated, no live LLM'})}\n\n"
        await asyncio.sleep(0.05)

    # Buffer events for audit + live streaming
    async for chunk in engine.walk(_no_op_agent_stream):
        phase_events.append(chunk)
        yield chunk

    # Final markers expected by the SSE client
    elapsed_ms = int((time.time() - start_time) * 1000)
    yield f"data: {json.dumps({'type': 'metrics', 'data': {'total_tokens': 0, 'response_time': round(elapsed_ms / 1000, 2), 'engine': 'real'}})}\n\n"
    yield f"data: {json.dumps({'type': 'run_status', 'phase': None, 'phase_active': False, 'drift': 'low'})}\n\n"
    yield "data: [DONE]\n\n"

    # Persist trace + observed fact
    _write_trace(session_id, message, phase_events, elapsed_ms)
    _write_observed_fact("runs", f"Engine run #{runs} — session {session_id[:8]} — {elapsed_ms}ms — {message[:80]}")


# ====================================================================
# Fallback stub pipeline (if engine import failed)
# ====================================================================
async def run_pipeline_stub(message: str, session_id: str):
    """Fallback when the real engine can't load."""
    global runs
    runs += 1
    start_time = time.time()
    yield f"data: {json.dumps({'type': 'mode_detected', 'mode': 'agent', 'note': 'stub fallback'})}\n\n"
    for idx, phase in enumerate(PHASES):
        yield f"data: {json.dumps({'type': 'phase_enter', 'phase': phase, 'index': idx + 1, 'total': 7})}\n\n"
        await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'type': 'phase_exit', 'phase': phase})}\n\n"
    elapsed_ms = int((time.time() - start_time) * 1000)
    yield f"data: {json.dumps({'type': 'metrics', 'data': {'response_time': round(elapsed_ms / 1000, 2), 'engine': 'stub'}})}\n\n"
    yield "data: [DONE]\n\n"
    _write_trace(session_id, message, [], elapsed_ms)


# ====================================================================
# API endpoints
# ====================================================================
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "runs": runs,
        "engine": "real" if ENGINE_AVAILABLE else "stub",
        "phases": len(PHASES),
        "agents_loaded": getattr(OpenCodeEngine, "_agents", None) and len(OpenCodeEngine._agents) or "n/a",
    }


@app.post("/run")
async def run(request: Request):
    """Run the agent pipeline and stream SSE events.

    Body: { "message": "build a flask todo app", "session": "uuid-..." }
    Returns: text/event-stream of pipeline events.
    """
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session", str(uuid.uuid4()))
    sessions[session_id] = {"message": message, "started_at": time.time()}
    logger.info(f"Run start session={session_id[:8]} mode=agent message={message[:60]!r}")

    fn = run_pipeline_real if ENGINE_AVAILABLE else run_pipeline_stub
    return StreamingResponse(
        fn(message, session_id),
        media_type="text/event-stream",
        headers={"X-Engine": "real" if ENGINE_AVAILABLE else "stub", "X-Session": session_id},
    )


@app.get("/status")
async def status():
    return {
        "runs": runs,
        "engine": "real" if ENGINE_AVAILABLE else "stub",
        "workspace": str(WORKSPACE_DIR),
        "vault": str(VAULT_DIR),
        "data": str(DATA_DIR),
        "sessions": len(sessions),
        "phases": list(PHASES),
    }


@app.get("/")
async def root():
    return {"name": "AgentOS Engine", "version": "1.0.0", "engine": "real" if ENGINE_AVAILABLE else "stub"}


# ====================================================================
# Main
# ====================================================================
if __name__ == "__main__":
    port = int(os.environ.get("AGENTOS_BRIDGE_PORT", "7001"))
    host = os.environ.get("AGENTOS_BRIDGE_HOST", "0.0.0.0")
    logger.info(f"AgentOS Engine Bridge starting on {host}:{port} (engine={'real' if ENGINE_AVAILABLE else 'stub'})")
    uvicorn.run(app, host=host, port=port, log_level="info")
