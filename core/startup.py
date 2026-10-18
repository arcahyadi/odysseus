# core/startup.py
"""Application startup and shutdown lifecycle.

Extracted from ``app.py`` to keep the FastAPI entrypoint thin.
Uses ``app.state`` to access component managers stored during init.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

from core.constants import AUTH_FILE

logger = logging.getLogger(__name__)


async def run_startup(app):
    """Execute all startup tasks — purge, monitors, warmups, schedulers."""
    _state = app.state
    _state.upload_cleanup_task = None

    logger.info("Application starting up...")

    webhook_manager = _state.webhook_manager
    webhook_manager.set_loop(asyncio.get_running_loop())

    # Purge leftover incognito sessions from previous process
    try:
        from core.database import ChatMessage as _DbMsg
        from core.database import Session as _DbSess
        from core.database import SessionLocal as _SL

        _db = _SL()
        try:
            _ghosts = _db.query(_DbSess).filter(_DbSess.name.in_(("Nobody", "Incognito"))).all()
            for _g in _ghosts:
                _db.query(_DbMsg).filter(_DbMsg.session_id == _g.id).delete()
                _db.delete(_g)
            if _ghosts:
                _db.commit()
                logger.info(f"Purged {len(_ghosts)} leftover incognito session(s)")
        finally:
            _db.close()
    except Exception as e:
        logger.debug(f"Incognito purge skipped: {e}")

    _startup_tasks: list = []
    _state._startup_tasks = _startup_tasks

    # Upload cleanup
    upload_cleanup_func = getattr(_state, "upload_cleanup_func", None)
    if upload_cleanup_func:
        _state.upload_cleanup_task = asyncio.create_task(upload_cleanup_func())

    # Background job monitor
    try:
        from src.bg_monitor import start_bg_monitor

        _startup_tasks.append(start_bg_monitor())
    except Exception as _e:
        logger.warning("Failed to start background-job monitor: %s", _e)

    # MCP server connections (fire-and-forget)
    mcp_manager = _state.mcp_manager

    async def _startup_mcp_connections():
        try:
            from src.builtin_mcp import register_builtin_servers

            await register_builtin_servers(mcp_manager)
        except BaseException as e:
            logger.warning(f"Built-in MCP registration failed (non-critical): {type(e).__name__}: {e}")
        try:
            await asyncio.wait_for(mcp_manager.connect_all_enabled(), timeout=20)
        except TimeoutError:
            logger.warning("User MCP startup timed out (non-critical)")
        except BaseException as e:
            logger.warning(f"MCP startup failed (non-critical): {type(e).__name__}: {e}")
        try:
            await mcp_manager.connect_external_enabled()
        except BaseException as e:
            logger.warning(f"External MCP startup failed (non-critical): {type(e).__name__}: {e}")

    _startup_tasks.append(asyncio.create_task(_startup_mcp_connections()))

    # Pre-warm tool index
    async def _warmup_tool_index():
        try:
            from src.tool_index import get_tool_index

            idx = await asyncio.to_thread(get_tool_index)
            if idx:
                await asyncio.to_thread(idx.get_tools_for_query, "warmup", 8)
                logger.info("[startup] Tool index pre-warmed")
        except Exception as e:
            logger.warning(f"Tool index warmup failed (non-critical): {type(e).__name__}: {e}")

    _startup_tasks.append(asyncio.create_task(_warmup_tool_index()))

    # Warmup endpoint pings
    model_discovery = _state.model_discovery

    async def _warmup_endpoints():
        try:
            import httpx

            urls = await asyncio.to_thread(model_discovery.warmup_ping_urls) if model_discovery else []
            for url in urls:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.get(url)
                    logger.info(f"Warmup ping OK: {url}")
                except Exception as e:
                    logger.debug(f"Warmup ping failed for endpoint: {e}")
        except Exception as e:
            logger.debug(f"Warmup ping skipped: {e}")

    _startup_tasks.append(asyncio.create_task(_warmup_endpoints()))

    # Keep-alive loop
    async def _keepalive_loop():
        while True:
            try:
                await asyncio.sleep(60)
                await _warmup_endpoints()
            except Exception as e:
                logger.warning(f"Keepalive loop error: {e}")
                await asyncio.sleep(300)

    _startup_tasks.append(asyncio.create_task(_keepalive_loop()))

    # Ensure default automation tasks
    task_scheduler = _state.task_scheduler

    async def _ensure_default_tasks():
        owners = set()
        try:
            import json as _json

            auth_path = AUTH_FILE
            with open(auth_path, encoding="utf-8") as f:
                users = _json.load(f).get("users", {})
            owners.update(users.keys())
        except Exception as e:
            logger.debug(f"Default task auth-owner scan: {e}")

        try:
            from core.database import ScheduledTask, SessionLocal
            from src.task_scheduler import HOUSEKEEPING_DEFAULTS

            builtin_names = []
            for defs in HOUSEKEEPING_DEFAULTS.values():
                builtin_names.append(defs["name"])
                builtin_names.extend(defs.get("legacy_names") or [])
            db_seed = SessionLocal()
            try:
                rows = (
                    db_seed.query(ScheduledTask.owner)
                    .filter(
                        (ScheduledTask.action.in_(list(HOUSEKEEPING_DEFAULTS.keys())))
                        | (ScheduledTask.name.in_(builtin_names))
                    )
                    .distinct()
                    .all()
                )
                owners.update(row[0] for row in rows if row[0])
            finally:
                db_seed.close()
        except Exception as e:
            logger.debug(f"Default task existing-owner scan: {e}")

        try:
            for uname in sorted(owners):
                try:
                    await task_scheduler.ensure_defaults(uname)
                except Exception as e:
                    logger.debug(f"ensure_defaults({uname}): {e}")
        except Exception as e:
            logger.debug(f"Default tasks: {e}")

    await _ensure_default_tasks()

    # Skill owner backfill
    try:
        import json as _json

        skills_manager = _state.skills_manager
        auth_path = AUTH_FILE
        with open(auth_path, encoding="utf-8") as f:
            users = _json.load(f).get("users", {})
        primary_owner = None
        for uname, udata in users.items():
            if udata.get("is_admin") is True:
                primary_owner = uname
                break
        if not primary_owner and users:
            primary_owner = next(iter(users))
        if primary_owner:
            changed = skills_manager.backfill_owner(primary_owner, set(users.keys()))
            if changed:
                logger.info("Assigned %s legacy skill file(s) to %s", changed, primary_owner)
    except Exception as e:
        logger.debug(f"Skill owner backfill skipped: {e}")

    # Start scheduled task runner
    _tasks_inprocess = os.environ.get("ODYSSEUS_INPROCESS_TASKS", "1").strip().lower()
    if _tasks_inprocess not in ("0", "false", "no", "off", ""):
        await task_scheduler.start()
    else:
        logger.info(
            "In-process task scheduler disabled (ODYSSEUS_INPROCESS_TASKS=0); drive task firing externally (e.g. cron)."
        )

    # Periodic null-owner sweep
    async def _null_owner_sweep_loop():
        while True:
            try:
                await asyncio.sleep(3600)
                from core.database import _migrate_assign_legacy_owner

                await asyncio.to_thread(_migrate_assign_legacy_owner)
            except Exception as e:
                logger.debug(f"Null-owner sweep skipped: {e}")
                await asyncio.sleep(3600)

    _startup_tasks.append(asyncio.create_task(_null_owner_sweep_loop()))

    # Nightly skill audit
    skills_manager = _state.skills_manager

    async def _skill_audit_nightly_loop():
        while True:
            try:
                from src.settings import get_setting

                hour = int(get_setting("skill_audit_hour", 2) or 2)
            except Exception:
                hour = 2
            now = datetime.now()
            nxt = now.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
            await asyncio.sleep(max(60, (nxt - now).total_seconds()))
            try:
                from src.settings import get_setting

                if not get_setting("skill_audit_nightly", True):
                    continue
                batch = int(get_setting("skill_audit_batch", 8) or 8)
                from routes.skills_routes import run_scheduled_skill_audit

                await run_scheduled_skill_audit(skills_manager, owner=None, max_skills=batch)
            except Exception as e:
                logger.warning(f"Nightly skill audit failed: {e}")

    _startup_tasks.append(asyncio.create_task(_skill_audit_nightly_loop()))

    # Cookbook serve lifecycle
    from src.cookbook_serve_lifecycle import cookbook_serve_lifecycle_loop

    _startup_tasks.append(asyncio.create_task(cookbook_serve_lifecycle_loop()))

    # Channel adapters (Discord/Telegram)
    async def _startup_channel_adapters():
        try:
            from src.channel_bootstrap import bootstrap_channels

            await bootstrap_channels()
        except Exception as e:
            logger.warning(f"Channel adapter bootstrap failed (non-critical): {type(e).__name__}: {e}")

    _startup_tasks.append(asyncio.create_task(_startup_channel_adapters()))

    # Agent catalog
    async def _startup_agent_catalog():
        try:
            if os.environ.get("ODYSSEUS_AGENT_CATALOG", "").strip().lower() in ("1", "true", "yes", "on"):
                from src.orchestrator.registry import AgentRegistry

                registry = AgentRegistry().discover()
                app.state.agent_catalog = registry
                logger.info("Agent catalog loaded: %d agents", len(registry.list_names()) if registry else 0)
        except Exception as e:
            logger.warning(f"Agent catalog load failed (non-critical): {type(e).__name__}: {e}")

    _startup_tasks.append(asyncio.create_task(_startup_agent_catalog()))

    logger.info("Application startup complete")


async def run_shutdown(app):
    """Clean shutdown — cancel tasks, close connections."""
    logger.info("Application shutting down...")

    _state = app.state
    upload_cleanup_task = getattr(_state, "upload_cleanup_task", None)
    if upload_cleanup_task:
        upload_cleanup_task.cancel()
        try:
            await upload_cleanup_task
        except asyncio.CancelledError:
            pass

    # Stop task scheduler
    task_scheduler = _state.task_scheduler
    try:
        await task_scheduler.stop()
    except Exception:
        pass

    # Close webhook manager
    webhook_manager = _state.webhook_manager
    try:
        await webhook_manager.close()
    except Exception as e:
        logger.warning(f"Webhook manager shutdown error: {e}")

    # Disconnect MCP servers
    mcp_manager = _state.mcp_manager
    try:
        await mcp_manager.disconnect_all()
    except Exception as e:
        logger.warning(f"MCP shutdown error: {e}")

    logger.info("Application shutdown complete")
