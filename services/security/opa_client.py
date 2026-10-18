"""
OPAClient — Async HTTP client for OpenPolicyAgent (OPA) policy decisions.

Replaces hardcoded phase-lock.yaml lookups with declarative Rego policy queries.
Supports:
  - Tool access checks (phase-aware authorization)
  - Phase transition validation
  - Kill-switch: ODYSSEUS_OPA=off falls back to local YAML enforcement
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# Kill-switch: when OFF, OPAClient is bypassed and callers fall back to
# the existing ToolRegistry (phase-lock.yaml) enforcement.
#
# Default OFF (Sprint 4 item 2). It was `on`, and no production module imports
# this file at all — so the switch reported itself active while nothing ever
# consulted the policy. Cutting it in the *registry* alone would have changed
# what the dashboard displays without changing what the code does, which is the
# one thing a kill-switch table must never do. Both halves move together, and
# `tests/test_killswitch_registry.py` fails if they ever disagree again.
_OPA_ENABLED = os.getenv("ODYSSEUS_OPA", "off").strip().lower()
OPA_ENABLED = _OPA_ENABLED not in {"off", "0", "false", "no"}

# Default OPA endpoint (matches docker-compose profile "security")
OPA_BASE_URL = os.getenv("ODYSSEUS_OPA_URL", "http://127.0.0.1:8181")

# Timeouts
_CONNECT_TIMEOUT = 2.0
_READ_TIMEOUT = 3.0


class OPAClient:
    """Async client for OPA policy engine.

    Usage::

        async with OPAClient() as client:
            result = await client.check_tool_access("BUILD", "write_file", "WRITE")
            if not result["allow"]:
                print(f"Blocked: {result['deny_reason']}")
    """

    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or OPA_BASE_URL).rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                connect=_CONNECT_TIMEOUT,
                sock_read=_READ_TIMEOUT,
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> OPAClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # ── Low-level query ──────────────────────────────────────

    async def _query(self, path: str, data: dict[str, Any]) -> Any:
        """POST a data payload to OPA and return the result."""
        session = await self._ensure_session()
        url = f"{self._base_url}/v1/data/{path}"
        try:
            async with session.post(url, json=data) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("OPA query failed (%s): %s", resp.status, body)
                    return {"result": False, "error": f"HTTP {resp.status}: {body}"}
                payload = await resp.json()
                return payload.get("result", False)
        except TimeoutError:
            logger.warning("OPA timeout for %s — falling back to deny", path)
            return {"result": False, "error": "timeout"}
        except aiohttp.ClientError as exc:
            logger.warning("OPA connection error: %s — falling back to deny", exc)
            return {"result": False, "error": str(exc)}

    # ── Tool access check ────────────────────────────────────

    async def check_tool_access(
        self,
        phase: str,
        tool: str,
        tool_category: str,
        *,
        command: str = "",
        write_path: str = "",
        approved: bool = False,
    ) -> dict[str, Any]:
        """Check whether a tool is allowed in the given phase via OPA.

        Returns::

            {"allow": bool, "deny_reason": str, "phase": str, "tool": str}
        """
        if not OPA_ENABLED:
            return {"allow": True, "deny_reason": "", "phase": phase, "tool": tool}

        input_data = {
            "input": {
                "phase": phase.upper(),
                "tool": tool,
                "tool_category": tool_category.upper(),
                "command": command,
                "write_path": write_path,
                "approved": approved,
            }
        }
        result = await self._query("odysseus/tool/allow", input_data)

        # result may be a bool or a dict with {"result": bool, ...}
        allow = False
        if isinstance(result, bool):
            allow = result
        elif isinstance(result, dict):
            allow = result.get("result", False)

        deny_reason = ""
        if not allow:
            # Fetch deny reason
            deny_data = await self._query("odysseus/tool/deny_reason", input_data)
            if isinstance(deny_data, list) and deny_data:
                deny_reason = deny_data[0]
            elif isinstance(deny_data, str):
                deny_reason = deny_data

        return {
            "allow": allow,
            "deny_reason": deny_reason,
            "phase": phase,
            "tool": tool,
        }

    # ── Phase transition check ────────────────────────────────

    async def check_phase_transition(self, from_phase: str, to_phase: str) -> dict[str, Any]:
        """Check whether a phase transition is valid via OPA.

        Returns::

            {"allow": bool, "deny_reason": str, "from": str, "to": str}
        """
        if not OPA_ENABLED:
            return {
                "allow": True,
                "deny_reason": "",
                "from": from_phase,
                "to": to_phase,
            }

        input_data = {
            "input": {
                "from": from_phase.upper(),
                "to": to_phase.upper(),
            }
        }
        result = await self._query("odysseus/phase/allow_transition", input_data)

        allow = False
        if isinstance(result, bool):
            allow = result
        elif isinstance(result, dict):
            allow = result.get("result", False)

        deny_reason = ""
        if not allow:
            deny_data = await self._query("odysseus/phase/deny_reason", input_data)
            if isinstance(deny_data, list) and deny_data:
                deny_reason = deny_data[0]
            elif isinstance(deny_data, str):
                deny_reason = deny_data

        return {
            "allow": allow,
            "deny_reason": deny_reason,
            "from": from_phase,
            "to": to_phase,
        }

    # ── Health check ─────────────────────────────────────────

    async def health(self) -> bool:
        """Return True if OPA server is reachable."""
        session = await self._ensure_session()
        try:
            async with session.get(f"{self._base_url}/health") as resp:
                return resp.status == 200
        except Exception:
            return False


# ── Module-level convenience ─────────────────────────────────

_global_client: OPAClient | None = None


def get_opa_client() -> OPAClient:
    """Return or create the global OPA client singleton."""
    global _global_client
    if _global_client is None or (_global_client._session and _global_client._session.closed):
        _global_client = OPAClient()
    return _global_client
