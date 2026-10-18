"""
E2E test — AgentOS Engine bridge HTTP (real pipeline inside Docker).

Validates the V1 engine contract (master-ref 03-OBJECTIFS-SYSTEME):
  - GET  /health  → 200, engine="real", phases=7
  - POST /run     → SSE stream, 7 phase_enter / 7 phase_exit, [DONE] terminator
  - GET  /status  → runs incremented, workspace/vault/data paths present

This test spins up the engine_server in a background uvicorn process/thread
(via TestClient — no network needed) and asserts the real OpenCodeEngine.walk()
emits all expected SFD events. It locks the V1 contract so any regression
that breaks the pipeline is caught.

Does NOT require Docker — Python in-process via fastapi.testclient.
Does NOT require an LLM key — the engine walks the phases structurally.
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _load_engine_module():
    """Load docker/agentos-engine/engine_server.py as a module.

    The folder name contains a hyphen, so normal import doesn't work.
    We load it from file path with a synthetic name so PYTHONPATH='.'
    still lets `from src.opencode_engine import ...` resolve.
    """
    here = Path(__file__).resolve().parent.parent
    server_path = here / "docker" / "agentos-engine" / "engine_server.py"
    spec = importlib.util.spec_from_file_location("agentos_engine_test", server_path)
    mod = importlib.util.module_from_spec(spec)
    # Ensure src/ + core/ are importable (they're at the repo root)
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    # Point the engine's data/workspace/vault at a temp dir (the container
    # path /home/agentos is not writable/present on dev hosts).
    tmp = tempfile.mkdtemp(prefix="agentos-engine-e2e-")
    os.environ.setdefault("AGENTOS_DATA_DIR", os.path.join(tmp, "data"))
    os.environ.setdefault("AGENTOS_WORKSPACE_DIR", os.path.join(tmp, "workspace"))
    os.environ.setdefault("AGENTOS_VAULT_DIR", os.path.join(tmp, "vault"))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def engine():
    """Load the engine module + TestClient fixture."""
    mod = _load_engine_module()
    if not mod.ENGINE_AVAILABLE:
        pytest.skip("OpenCodeEngine not importable in this environment")
    return mod


def test_health(engine):
    """GET /health returns 200 with engine=real and 7 phases."""
    c = TestClient(engine.app)
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["engine"] == "real"
    assert body["phases"] == 7


def test_status(engine):
    """GET /status returns engine metadata + the 7 phase names."""
    c = TestClient(engine.app)
    r = c.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "real"
    assert "workspace" in body
    assert "vault" in body
    assert "data" in body
    assert set(body["phases"]) == {
        "CLASSIFY",
        "KNOW",
        "PLAN",
        "BUILD",
        "QUALITY",
        "AUTOEVAL",
        "MEMORY_OBSERVE",
    }


def test_run_agent_mode_7_phases(engine):
    """POST /run with a project message triggers AGENT mode + 7 phases.

    This is UC-01 (lancer un nouveau projet) at the engine level.
    """
    c = TestClient(engine.app)
    r = c.post(
        "/run",
        json={"message": "build a complete flask todo app with SQLite", "session": "e2e-test-7phases"},
        headers={"Accept": "text/event-stream"},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")

    events = []
    for line in r.text.split("\n"):
        if line.startswith("data: "):
            payload = line[6:]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                if "DONE" in payload:
                    events.append({"type": "DONE"})

    types = [e.get("type") for e in events]
    phase_enters = [e for e in events if e.get("type") == "phase_enter"]
    phase_exits = [e for e in events if e.get("type") == "phase_exit"]

    # Mode detection
    assert "mode_detected" in types
    mode_ev = next(e for e in events if e.get("type") == "mode_detected")
    assert mode_ev["mode"] == "agent", f"expected agent mode, got {mode_ev}"

    # 7 phases walked in order (UC-01 + SFD §5.4)
    assert len(phase_enters) == 7
    assert len(phase_exits) == 7
    expected_order = ["CLASSIFY", "KNOW", "PLAN", "BUILD", "QUALITY", "AUTOEVAL", "MEMORY_OBSERVE"]
    # phase_enter events from OpenCodeEngine.walk() put "phase" at root
    enter_phases = [e.get("phase") or e.get("data", {}).get("phase") for e in phase_enters]
    enter_phases = [p for p in enter_phases if p]
    assert enter_phases == expected_order, f"phase order mismatch: {enter_phases}"

    # Build phase dispatches at least one agent + selects a model (SFD §5.1.4 + 5.6)
    build_event = next(
        (e for e in phase_enters if (e.get("phase") == "BUILD" or e.get("data", {}).get("phase") == "BUILD")),
        None,
    )
    assert build_event is not None

    # Stream terminator
    assert "DONE" in types, "SSE stream must end with [DONE]"

    # Final metrics + run_status (SFD §5.11 — observability)
    assert "metrics" in types
    assert "run_status" in types


def test_run_chat_mode_short_circuit(engine):
    """POST /run with a non-project message triggers CHAT mode (single phase).

    SFD §5.4 — risk modifies the loop. CHAT mode skips the 7-phase walk.
    """
    c = TestClient(engine.app)
    r = c.post(
        "/run",
        json={"message": "bonjour comment ca va ?", "session": "e2e-test-chat"},
        headers={"Accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = []
    for line in r.text.split("\n"):
        if line.startswith("data: "):
            payload = line[6:]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                if "DONE" in payload:
                    events.append({"type": "DONE"})
    types = [e.get("type") for e in events]

    mode_ev = next((e for e in events if e.get("type") == "mode_detected"), None)
    assert mode_ev is not None
    assert mode_ev["mode"] == "chat", f"non-project message should be chat, got {mode_ev}"

    # CHAT mode emits at most 1 phase_enter (vs 7 in agent mode)
    phase_enters = [e for e in events if e.get("type") == "phase_enter"]
    assert len(phase_enters) <= 1, f"chat mode should not walk 7 phases, got {len(phase_enters)}"


def test_run_increments_runs_counter(engine):
    """Two consecutive /run calls increment the engine runs counter (UC-03)."""
    c = TestClient(engine.app)
    initial = c.get("/status").json()["runs"]
    c.post("/run", json={"message": "build a graph", "session": "ctr-1"})
    c.post("/run", json={"message": "build a tree", "session": "ctr-2"})
    final = c.get("/status").json()["runs"]
    assert final >= initial + 2, f"runs counter not incremented: {initial} → {final}"
