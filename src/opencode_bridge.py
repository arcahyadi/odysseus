"""Odysseus <-> AgentOS Engine Bridge.

Routes: if AGENTOS_ENGINE_HOST is set, delegates to the isolated engine.
Otherwise, uses the internal agent stream (legacy mode for dev).
"""

import json
import logging
import os
from collections.abc import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

ENGINE_HOST = os.environ.get("AGENTOS_ENGINE_HOST", "")
ENGINE_PORT = int(os.environ.get("AGENTOS_ENGINE_PORT", "7001"))
ENGINE_URL = f"http://{ENGINE_HOST}:{ENGINE_PORT}" if ENGINE_HOST else ""


class OpenCodeBridge:
    """Bridge to AgentOS Engine (isolated) or internal agent stream."""

    def __init__(self, session_id: str, message: str, worktree: str | None = None):
        self.session_id = session_id
        self.message = message
        self.worktree = worktree

    async def stream(self, agent_stream=None) -> AsyncGenerator[str, None]:
        """Stream agent response — from engine if available, else internal."""

        if ENGINE_URL:
            # Route to isolated engine
            async for chunk in self._stream_from_engine():
                yield chunk
        elif agent_stream:
            # Legacy: use internal agent stream
            async for chunk in agent_stream:
                yield chunk
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No engine or agent stream available'})}\n\n"

    async def _stream_from_engine(self) -> AsyncGenerator[str, None]:
        """Call AgentOS Engine HTTP endpoint and forward SSE stream."""
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream(
                    "POST", f"{ENGINE_URL}/run", json={"message": self.message, "session": self.session_id}
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            yield line + "\n"
        except httpx.ConnectError:
            logger.error(f"Cannot connect to engine at {ENGINE_URL}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Engine unreachable at {ENGINE_URL}'})}\n\n"
        except Exception as e:
            logger.error(f"Engine error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    async def health(self) -> dict:
        """Check engine health."""
        if not ENGINE_URL:
            return {"engine": "internal", "status": "ok"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{ENGINE_URL}/health")
                return r.json()
        except:
            return {"engine": ENGINE_URL, "status": "unreachable"}
