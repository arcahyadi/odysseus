"""
decision_engine.py — YAML-driven workflow engine (n8n replacement).

IDLE → RUNNING → DONE | ERROR | CANCELLED
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import aiohttp
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.constants import DATA_DIR
from src.opencode_engine import get_event_bus
from src.app_context import app_context


logger = logging.getLogger(__name__)


def _truthy_env(env_key: str) -> bool:
    return os.getenv(env_key, "").strip().lower() in ("1", "true", "yes", "on")


_WORKFLOWS_DIR = Path(DATA_DIR, "workflows")
_WORKFLOW_LOG_DIR = Path(DATA_DIR, "workflow_logs")
for _d in (_WORKFLOWS_DIR, _WORKFLOW_LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Enums ───────────────────────────────────────────────────────────────────
class WorkflowState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class TriggerType(str, Enum):
    EVENT = "event"
    CRON = "cron"
    WEBHOOK = "webhook"
    HEALTH_CHANGE = "health_change"
    MANUAL = "manual"


# ── Dataclasses ─────────────────────────────────────────────────────────────
@dataclass
class StepResult:
    step_id: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    retries: int = 0


@dataclass
class WorkflowRun:
    run_id: str
    workflow_name: str
    state: WorkflowState = WorkflowState.IDLE
    trigger_type: str | None = None
    trigger_payload: dict[str, Any] = field(default_factory=dict)
    steps_completed: int = 0
    steps_total: int = 0
    step_results: dict[str, StepResult] = field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


@dataclass
class WorkflowTrigger:
    type: str
    pattern: str | None = None
    cron: str | None = None
    webhook_path: str | None = None
    health_service: str | None = None
    health_direction: str | None = None


@dataclass
class WorkflowStep:
    id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    timeout: int = 300
    on_error: str = "abort"
    max_retries: int = 0
    backoff_seconds: int = 5


@dataclass
class WorkflowDefinition:
    name: str
    description: str
    version: str
    enabled: bool
    triggers: list[WorkflowTrigger]
    steps: list[WorkflowStep]
    error_handling: dict[str, Any] = field(default_factory=dict)


# ── YAML helpers ────────────────────────────────────────────────────────────
def _parse_duration(val: Any) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if not isinstance(val, str):
        return 300
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(s(?:ec(?:ond)?)?|m(?:in(?:ute)?)?|h(?:r|our)?)?s?$", val.strip().lower())
    if not m:
        return 300
    n, u = float(m.group(1)), (m.group(2) or "s")[0]
    return int(n * (60 if u == "m" else 3600 if u == "h" else 1))


def _parse_error(raw: str) -> tuple[str, int, int]:
    raw = raw.strip().lower()
    if raw in ("abort", "continue"):
        return (raw, 0, 0)
    m = re.match(r"^retry\((\d+),\s*(\d+(?:\.\d+)?)\s*([sm]|sec|min)?\)$", raw)
    if m:
        b = float(m.group(2))
        return ("retry", int(m.group(1)), int(b * 60 if m.group(3) and m.group(3)[0] == "m" else b))
    logger.warning("Unrecognised on_error %r, defaulting abort", raw)
    return ("abort", 0, 0)


def load_workflow_from_yaml(filepath: Path) -> WorkflowDefinition | None:
    try:
        raw = yaml.safe_load(open(filepath, encoding="utf-8"))
    except Exception:
        logger.exception("Failed to parse %s", filepath)
        return None
    if not isinstance(raw, dict):
        return None
    triggers = [
        WorkflowTrigger(
            type=t.get("type", "").strip().lower(),
            pattern=t.get("pattern"),
            cron=t.get("cron"),
            webhook_path=t.get("webhook_path", t.get("path")),
            health_service=t.get("health_service", t.get("service")),
            health_direction=t.get("health_direction", t.get("direction")),
        )
        for t in raw.get("triggers", [])
        if isinstance(t, dict)
    ]
    steps: list[WorkflowStep] = []
    for s in raw.get("steps", []):
        if not isinstance(s, dict) or "id" not in s:
            continue
        strat, retries, backoff = _parse_error(str(s.get("on_error", "abort")))
        steps.append(
            WorkflowStep(
                id=s["id"],
                action=s["action"],
                params=s.get("params", {}),
                timeout=_parse_duration(s.get("timeout", 300)),
                on_error=str(s.get("on_error", "abort")),
                max_retries=retries,
                backoff_seconds=backoff,
            )
        )
    return WorkflowDefinition(
        name=raw.get("name", filepath.stem),
        description=raw.get("description", ""),
        version=str(raw.get("version", "1.0")),
        enabled=bool(raw.get("enabled", True)),
        triggers=triggers,
        steps=steps,
        error_handling=raw.get("error_handling", {}),
    )


# ── Template substitution ───────────────────────────────────────────────────
def _resolve_template(template: str, context: dict[str, Any]) -> str:
    if not isinstance(template, str) or "{{" not in template:
        return template

    def _rep(m: re.Match) -> str:
        val: Any = context
        for p in m.group(1).strip().split("."):
            val = (
                val.get(p, "") if isinstance(val, dict) else getattr(val, p, "") if isinstance(val, StepResult) else ""
            )
        return str(val) if val is not None else ""

    return re.sub(r"\{\{\s*([^}]+)\s*\}\}", _rep, template)


def _resolve_params(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, str):
            out[k] = _resolve_template(v, context)
        elif isinstance(v, dict):
            out[k] = _resolve_params(v, context)
        elif isinstance(v, list):
            out[k] = [_resolve_template(x, context) if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out


# ── Action executors ────────────────────────────────────────────────────────
async def _spawn_agent(params: dict[str, Any]) -> Any:
    from src.opencode_client import stream_agent

    sid = params.get("session_id", str(uuid.uuid4()))
    chunks = []
    async for chunk in stream_agent(
        session_id=sid,
        message=params.get("prompt", ""),
        worktree=params.get("worktree", os.getcwd()),
        mode=params.get("mode", "agent"),
    ):
        chunks.append(str(chunk))
    return {"session_id": sid, "output": "".join(chunks)}


async def _call_tool(params: dict[str, Any]) -> Any:
    tool, args = params.get("tool", ""), params.get("args", params.get("arguments", {}))
    if tool in ("bash", "subprocess"):
        cmd = args if isinstance(args, str) else args.get("command", str(args))
        p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await p.communicate()
        return {
            "stdout": out.decode("utf-8", errors="replace").strip(),
            "stderr": err.decode("utf-8", errors="replace").strip(),
            "returncode": p.returncode,
        }
    if tool == "health_check":
        p = await asyncio.create_subprocess_shell(
            "docker ps --format '{{.Names}} {{.Status}}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await p.communicate()
        s = out.decode("utf-8", errors="replace").strip()
        return {"healthy": "Up" in s, "containers": s}
    from src.mcp_manager import get_mcp_manager

    mgr = get_mcp_manager()
    return await mgr.call_tool(tool, args) if mgr else {"error": "MCP manager unavailable"}


async def _send_alert(params: dict[str, Any]) -> Any:
    ch, title, msg, pri = (
        params.get("channel", "gotify").lower(),
        params.get("title", ""),
        params.get("message", ""),
        params.get("priority", "normal"),
    )

    async def _post(url: str, **kw) -> dict:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, timeout=aiohttp.ClientTimeout(10), **kw) as r:
                    return {"status": r.status, "sent": r.status == 200}
        except Exception as e:
            return {"error": str(e)}

    if ch == "gotify":
        u, tok = os.getenv("GOTIFY_URL", ""), os.getenv("GOTIFY_TOKEN", "")
        if not u or not tok:
            return {"skipped": True, "reason": "GOTIFY credentials not set"}
        return await _post(
            f"{u.rstrip('/')}/message?token={tok}",
            json={"title": title, "message": msg, "priority": {"low": 2, "normal": 5, "high": 8}.get(pri, 5)},
        )
    if ch == "ntfy":
        t = os.getenv("NTFY_TOPIC", "")
        if not t:
            return {"skipped": True, "reason": "NTFY_TOPIC not set"}
        srv = os.getenv("NTFY_SERVER", "https://ntfy.sh")
        return await _post(
            f"{srv.rstrip('/')}/{t}",
            data=msg.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": {"low": "low", "normal": "default", "high": "high"}.get(pri, "default"),
            },
        )
    return {"error": f"Unsupported channel: {ch}"}


async def _docker_action(params: dict[str, Any]) -> Any:
    c = params.get("compose", "docker-compose.yml")
    cmd = f"docker compose -f {c} {params.get('command', 'up -d')}"
    p = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=params.get("cwd", os.getcwd())
    )
    out, err = await p.communicate()
    return {
        "command": cmd,
        "stdout": out.decode("utf-8", errors="replace").strip(),
        "stderr": err.decode("utf-8", errors="replace").strip(),
        "returncode": p.returncode,
    }


async def _webhook(params: dict[str, Any]) -> Any:
    url = params.get("url", "")
    method = params.get("method", "POST").upper()
    if not url:
        return {"error": "No URL provided"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.request(
                method,
                url,
                json=params.get("body", params.get("payload", {})) if method in ("POST", "PUT", "PATCH") else None,
                headers=params.get("headers", {}),
                timeout=aiohttp.ClientTimeout(int(params.get("timeout", 30))),
            ) as r:
                return {"status": r.status, "body": (await r.text())[:2000]}
    except Exception as e:
        return {"error": str(e)}


async def _emit_event(params: dict[str, Any]) -> Any:
    ev = get_event_bus().emit(
        source=params.get("source", "decision_engine"),
        type=params.get("type", params.get("event_type", "custom")),
        data=params.get("data", {}),
    )
    return {"event_id": ev.get("event_id"), "type": params.get("type")}


async def _write_db(params: dict[str, Any]) -> Any:
    table, data = params.get("table", ""), params.get("data", {})
    if not table or not isinstance(data, dict):
        return {"error": "table + data dict required"}
    try:
        from sqlalchemy import text

        from core.database import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text(f"INSERT INTO {table} ({','.join(data)}) VALUES ({','.join(f':{k}' for k in data)})"), data)
            db.commit()
            return {"table": table, "inserted": True}
        finally:
            db.close()
    except Exception as e:
        return {"error": str(e)}


_ACTION_MAP: dict[str, Callable] = {
    "spawn_agent": _spawn_agent,
    "call_tool": _call_tool,
    "send_alert": _send_alert,
    "docker_action": _docker_action,
    "webhook": _webhook,
    "emit_event": _emit_event,
    "write_db": _write_db,
}


# ── Execution ───────────────────────────────────────────────────────────────
async def _execute_step(step: WorkflowStep, ctx: dict[str, Any], run_id: str) -> StepResult:
    fn = _ACTION_MAP.get(step.action)
    if not fn:
        return StepResult(step_id=step.id, success=False, error=f"Unknown action: {step.action}")
    params = _resolve_params(step.params, ctx)
    max_attempts = step.max_retries + 1
    for attempt in range(1, max_attempts + 1):
        t0 = time.monotonic()
        try:
            out = await asyncio.wait_for(fn(params), timeout=step.timeout)
            return StepResult(
                step_id=step.id,
                success=True,
                output=out,
                duration_ms=(time.monotonic() - t0) * 1000,
                retries=attempt - 1,
            )
        except TimeoutError:
            last = f"Step {step.id} timed out after {step.timeout}s"
            logger.warning("WF %s step %s attempt %d/%d: %s", run_id, step.id, attempt, max_attempts, last)
        except asyncio.CancelledError:
            return StepResult(step_id=step.id, success=False, error="Cancelled")
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            logger.exception("WF %s step %s attempt %d/%d failed", run_id, step.id, attempt, max_attempts)
        if attempt < max_attempts:
            await asyncio.sleep(step.backoff_seconds * (2 ** (attempt - 1)))
    return StepResult(step_id=step.id, success=False, error=last)


async def _run_abort_handlers(wf: WorkflowDefinition, ctx: dict[str, Any], run_id: str) -> None:
    for raw in wf.error_handling.get("on_abort", []):
        if not isinstance(raw, dict) or "action" not in raw:
            continue
        step = WorkflowStep(id=f"abort_{raw['action']}", action=raw["action"], params=raw.get("params", {}))
        try:
            await _execute_step(step, ctx, run_id)
        except Exception:
            logger.exception("Abort handler %s failed", step.id)


async def _log_run(wf: WorkflowDefinition, run: WorkflowRun) -> None:
    entry = dict(
        run_id=run.run_id,
        workflow=wf.name,
        version=wf.version,
        state=run.state.value,
        trigger_type=run.trigger_type,
        trigger_payload=run.trigger_payload,
        steps_completed=run.steps_completed,
        steps_total=run.steps_total,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
        step_results={
            sid: {
                "success": s.success,
                "output": str(s.output)[:1000] if s.output else None,
                "error": s.error,
                "duration_ms": s.duration_ms,
                "retries": s.retries,
            }
            for sid, s in run.step_results.items()
        },
    )
    try:
        logf = _WORKFLOW_LOG_DIR / f"workflow-{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"
        with open(logf, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        logger.exception("Failed to log run %s", run.run_id)
    logger.info("Workflow %r → %s (%d/%d steps)", wf.name, run.state.value, run.steps_completed, run.steps_total)


async def _execute_workflow(wf: WorkflowDefinition, trigger_type: str, payload: dict[str, Any]) -> WorkflowRun:
    rid = str(uuid.uuid4())[:12]
    run = WorkflowRun(
        run_id=rid,
        workflow_name=wf.name,
        state=WorkflowState.RUNNING,
        trigger_type=trigger_type,
        trigger_payload=payload,
        steps_total=len(wf.steps),
        started_at=datetime.now(UTC).isoformat(),
    )
    bus = get_event_bus()
    bus.emit("workflow", "workflow_started", {"run_id": rid, "workflow": wf.name, "trigger": trigger_type})
    ctx: dict[str, Any] = {"trigger": payload, "steps": {}}
    for step in wf.steps:
        r = await _execute_step(step, ctx, rid)
        run.step_results[step.id] = r
        ctx["steps"][step.id] = r
        if r.success:
            run.steps_completed += 1
            bus.emit("workflow", "step_completed", {"run_id": rid, "step": step.id, "action": step.action})
        else:
            strat, _, _ = _parse_error(step.on_error)
            if strat == "continue":
                continue
            run.state = WorkflowState.ERROR
            run.error = r.error
            run.finished_at = datetime.now(UTC).isoformat()
            bus.emit(
                "workflow", "workflow_error", {"run_id": rid, "workflow": wf.name, "step": step.id, "error": r.error}
            )
            await _run_abort_handlers(wf, ctx, rid)
            await _log_run(wf, run)
            return run
    run.state = WorkflowState.DONE
    run.finished_at = datetime.now(UTC).isoformat()
    bus.emit("workflow", "workflow_completed", {"run_id": rid, "workflow": wf.name, "steps": run.steps_completed})
    await _log_run(wf, run)
    return run


# ── DecisionEngine ───────────────────────────────────────────────────────
class DecisionEngine:
    """YAML-driven workflow orchestrator with EventBus, cron, webhook triggers.

    Usage:
        engine = DecisionEngine()
        await engine.start(scheduler, webhook_router)
        await engine.trigger_manual("deploy-and-verify")
        await engine.stop()
    """

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._running = False
        self.app_context.caches.bus = get_event_bus()
        self._scheduler: AsyncIOScheduler | None = None
        self._cron_jobs: dict[str, str] = {}
        self._webhook_router: Any | None = None
        self._webhook_routes: set[str] = set()
        self._active_runs: set[str] = set()

    # ── Tool awareness ─────────────────────────────────────────────────
    def get_available_tools(self) -> dict[str, Any]:
        """Return the status of every compose service and integrated tool.

        Reads docker-compose.yml to list expected services, then probes
        each one with a fast TCP connect. Also checks kill-switch env vars
        for optional MCP clients (Serena, CBM, AgentSeal, etc.).

        Returns:
            Dict with keys: services (dict of name→status), mcp_clients
            (dict of name→enabled), graph (dict of tool groupings).
        """
        import socket

        import yaml as _yaml

        compose_path = Path(os.getcwd(), "docker-compose.yml")
        services_status: dict[str, str] = {}

        if compose_path.exists():
            try:
                raw = _yaml.safe_load(compose_path.read_text(encoding="utf-8"))
                svc = raw.get("services", {}) if isinstance(raw, dict) else {}
                for name, cfg in svc.items():
                    if not isinstance(cfg, dict):
                        continue
                    ports = cfg.get("ports", [])
                    host_port = None
                    for p in ports:
                        if isinstance(p, str) and ":" in p:
                            host_port = p.split(":")[0]
                            break
                    if host_port and host_port.isdigit():
                        try:
                            s = socket.create_connection(("127.0.0.1", int(host_port)), timeout=1.0)
                            s.close()
                            services_status[name] = "up"
                        except OSError:
                            services_status[name] = "down"
                    else:
                        services_status[name] = "unknown"
            except Exception:
                services_status = {"error": "Cannot parse docker-compose.yml"}

        mcp_clients = {
            "serena": _truthy_env("ODYSSEUS_SERENA_MCP"),
            "cbm": _truthy_env("ODYSSEUS_CBM"),
            "agentseal": _truthy_env("ODYSSEUS_AGENTSEAL"),
            "graphify": _truthy_env("ODYSSEUS_GRAPHIFY"),
            "scrapling": _truthy_env("SCRAPLING_ENABLED"),
            "kroki": _truthy_env("KROKI_ENABLED"),
            "playwright": _truthy_env("ODYSSEUS_PLAYWRIGHT"),
            "supabase": _truthy_env("ODYSSEUS_SUPABASE"),
            "vaultwarden": _truthy_env("ODYSSEUS_VAULTWARDEN"),
            "browser_harness": _truthy_env("ODYSSEUS_BROWSER_HARNESS"),
        }

        tool_groups = {
            "KNOW": ["explore", "cbm", "graphify", "web_search", "serena"],
            "BUILD": ["executor", "scrapling", "kroki", "bash", "write_file", "serena"],
            "QUALITY": ["reviewer", "security-audit", "agentseal", "pa11y", "k6"],
            "AUTOEVAL": ["gsd-verifier", "k6", "perf"],
        }

        return {
            "services": services_status,
            "mcp_clients": mcp_clients,
            "tool_groups": tool_groups,
        }

    # ── Loading ──────────────────────────────────────────────────────────
    def load_workflows(self, directory: Path | None = None) -> int:
        d = directory or _WORKFLOWS_DIR
        if not d.exists():
            return 0
        count = 0
        for fp in sorted(d.glob("*.yaml")):
            wf = load_workflow_from_yaml(fp)
            if wf and wf.enabled:
                self._workflows[wf.name] = wf
                count += 1
                logger.info(
                    "Loaded %r v%s (%d steps, %d triggers)", wf.name, wf.version, len(wf.steps), len(wf.triggers)
                )
        return count

    def get_workflows(self) -> list[dict[str, Any]]:
        return [
            {
                "name": w.name,
                "description": w.description,
                "version": w.version,
                "enabled": w.enabled,
                "triggers": [{"type": t.type, "pattern": t.pattern} for t in w.triggers],
                "step_count": len(w.steps),
            }
            for w in self._workflows.values()
        ]

    # ── Lifecycle ────────────────────────────────────────────────────────
    async def start(self, scheduler: AsyncIOScheduler | None = None, webhook_router: Any | None = None) -> None:
        self._running = True
        self._scheduler = scheduler or AsyncIOScheduler()
        self._webhook_router = webhook_router
        self.load_workflows()
        await self._register_triggers()
        logger.info("DecisionEngine started — %d workflows", len(self._workflows))

    async def stop(self) -> None:
        self._running = False
        self._active_runs.clear()
        if self._scheduler:
            for jid in self._cron_jobs.values():
                try:
                    self._scheduler.remove_job(jid)
                except Exception:
                    pass
            if self._scheduler.running:
                self._scheduler.shutdown(wait=False)
        logger.info("DecisionEngine stopped")

    # ── Trigger registration ─────────────────────────────────────────────
    async def _register_triggers(self) -> None:
        for wf in self._workflows.values():
            for t in wf.triggers:
                await self._register_trigger(wf, t)

    async def _register_trigger(self, wf: WorkflowDefinition, trigger: WorkflowTrigger) -> None:
        tt = trigger.type
        if tt == TriggerType.EVENT.value and trigger.pattern:
            self.app_context.caches.bus.on(trigger.pattern, _event_handler(self, wf.name, trigger))
            logger.debug("WF %r: event on %r", wf.name, trigger.pattern)
        elif tt == TriggerType.CRON.value and trigger.cron and self._scheduler:
            jid = f"wf_cron_{wf.name}"
            self._scheduler.add_job(
                _cron_job(self, wf.name, trigger),
                trigger="cron",
                id=jid,
                replace_existing=True,
                **_cron_kwargs(trigger.cron),
            )
            self._cron_jobs[wf.name] = jid
            logger.debug("WF %r: cron %r", wf.name, trigger.cron)
        elif tt == TriggerType.WEBHOOK.value and trigger.webhook_path and self._webhook_router:
            await self._register_webhook(wf, trigger)
        elif tt == TriggerType.HEALTH_CHANGE.value and trigger.health_service:
            pat = f"health.{trigger.health_service}.{trigger.health_direction or 'both'}"
            self.app_context.caches.bus.on(pat, _event_handler(self, wf.name, trigger))
            logger.debug("WF %r: health on %r", wf.name, pat)

    async def _register_webhook(self, wf: WorkflowDefinition, trigger: WorkflowTrigger) -> None:
        from fastapi import Request

        path = trigger.webhook_path or f"/webhooks/{wf.name}"
        rname = f"wf_{wf.name}_webhook"
        if rname in self._webhook_routes:
            return

        @self._webhook_router.post(path, name=rname)
        async def _handler(request: Request):
            try:
                body = await request.json()
            except Exception:
                body = {"raw": (await request.body()).decode("utf-8", errors="replace")[:4096]}
            asyncio.get_event_loop().create_task(self._trigger(wf.name, trigger, body))
            return {"status": "accepted", "workflow": wf.name}

        self._webhook_routes.add(rname)
        logger.debug("WF %r: webhook POST %s", wf.name, path)

    # ── Trigger execution ────────────────────────────────────────────────
    async def trigger_manual(self, workflow_name: str, payload: dict[str, Any] | None = None) -> str | None:
        return await self._trigger(workflow_name, WorkflowTrigger(type=TriggerType.MANUAL.value), payload or {})

    async def _trigger(
        self, workflow_name: str, trigger: WorkflowTrigger, payload: dict[str, Any] | None = None
    ) -> str | None:
        if not self._running:
            return None
        wf = self._workflows.get(workflow_name)
        if not wf:
            logger.warning("Unknown workflow: %s", workflow_name)
            return None
        logger.info("Triggering %r via %s", wf.name, trigger.type)
        self._active_runs.add(workflow_name)
        try:
            run = await _execute_workflow(wf, trigger.type, payload or {})
            return run.run_id
        except Exception:
            logger.exception("Workflow %r execution exploded", wf.name)
            return None
        finally:
            self._active_runs.discard(workflow_name)


# ── Cron & event handler factories ──────────────────────────────────────────
def _cron_kwargs(cron_expr: str) -> dict[str, Any]:
    try:
        f = cron_expr.strip().split()
        return (
            {"minute": f[0], "hour": f[1], "day": f[2], "month": f[3], "day_of_week": f[4]}
            if len(f) == 5
            else {"minute": "*/5"}
        )
    except Exception:
        return {"minute": "*/5"}


def _event_handler(engine: DecisionEngine, workflow_name: str, trigger: WorkflowTrigger) -> Callable:
    def _h(event: dict) -> None:
        loop = asyncio.get_event_loop()
        coro = engine._trigger(workflow_name, trigger, event.get("data", {}))
        if loop.is_running():
            loop.create_task(coro)
        else:
            asyncio.run(coro)

    return _h


def _cron_job(engine: DecisionEngine, workflow_name: str, trigger: WorkflowTrigger) -> Callable:
    def _j() -> None:
        loop = asyncio.get_event_loop()
        coro = engine._trigger(workflow_name, trigger)
        if loop.is_running():
            loop.create_task(coro)
        else:
            asyncio.run(coro)

    return _j


# ── Singleton ───────────────────────────────────────────────────────────────
app_context.caches.decision_engine: DecisionEngine | None = None


def get_decision_engine() -> DecisionEngine:
    if app_context.caches.decision_engine is None:
        app_context.caches.decision_engine = DecisionEngine()
    return app_context.caches.decision_engine
