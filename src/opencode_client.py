"""
OpenCode Daemon REST Client v2 — pont Python pour l'API /api/ du daemon.
Auth: HTTP Basic Auth (opencode:<password>)

Architecture:
  odysseus-app (FastAPI:9889) → HTTP → opencode-daemon (REST:9888)

Daemon v2 : toutes les routes sous /api/ , auth Basic requise.
Password défini via `lildax service password <pw>` avant démarrage.
"""

import base64
import json
import logging
import os
from collections.abc import AsyncGenerator
from enum import Enum
from typing import Any

import httpx
from src.app_context import app_context


logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================
DAEMON_HOST = os.environ.get("OPENCODE_DAEMON_HOST", "localhost")
DAEMON_PORT = int(os.environ.get("OPENCODE_DAEMON_PORT", "9888"))
DAEMON_URL = f"http://{DAEMON_HOST}:{DAEMON_PORT}"
DAEMON_TIMEOUT = float(os.environ.get("OPENCODE_DAEMON_TIMEOUT", "300.0"))
DAEMON_PASSWORD = os.environ.get("OPENCODE_DAEMON_PASSWORD", "opencode")


# ============================================================================
# Enums
# ============================================================================
class SessionMode(str, Enum):
    """Modes de session supportés par le daemon v2."""

    PLAN = "plan"
    BUILD = "build"
    RESEARCH = "research"
    CHAT = "chat"
    AUTOEVAL = "autoeval"
    DEBUG = "debug"


# ============================================================================
# Client
# ============================================================================
class OpenCodeDaemonClient:
    """Client HTTP pour l'API REST v2 du daemon OpenCode.

    Tous les endpoints sont sous /api/ . Auth Basic avec username "opencode".
    """

    def __init__(
        self,
        base_url: str = DAEMON_URL,
        timeout: float = DAEMON_TIMEOUT,
        password: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        pw = password or DAEMON_PASSWORD
        self._auth_encoded = base64.b64encode(f"opencode:{pw}".encode()).decode()
        self.app_context.caches.chroma_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=self._headers(),
        )

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {self._auth_encoded}",
        }

    async def close(self):
        await self.app_context.caches.chroma_client.aclose()

    # ====================================================================
    # Health & Status
    # ====================================================================

    async def health(self) -> dict:
        """GET /api/health — état du daemon."""
        try:
            r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/health")
            return r.json() if r.status_code == 200 else {"status": "error", "code": r.status_code}
        except httpx.ConnectError:
            return {"status": "unreachable", "host": self.base_url}

    async def ping(self) -> bool:
        """Vérification rapide : le daemon répond-il ?"""
        try:
            r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/health", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    # ====================================================================
    # Providers & Modèles
    # ====================================================================

    async def list_providers(self) -> dict:
        """GET /api/provider — tous les providers configurés."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/provider")
        r.raise_for_status()
        return r.json()

    async def get_provider(self, provider_id: str) -> dict:
        """GET /api/provider/{providerID} — détail d'un provider."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/provider/{provider_id}")
        r.raise_for_status()
        return r.json()

    async def list_models(self) -> dict:
        """GET /api/model — tous les modèles disponibles."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/model")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Sessions
    # ====================================================================

    async def create_session(
        self,
        mode: SessionMode = SessionMode.CHAT,
        model: str | None = None,
        system_prompt: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """POST /api/session — crée une nouvelle session.

        Retourne le corps complet. L'ID est dans response["data"]["id"].
        """
        payload: dict[str, Any] = {"mode": mode.value if isinstance(mode, SessionMode) else mode}
        if model:
            payload["model"] = model
        if system_prompt:
            payload["systemPrompt"] = system_prompt
        if session_id:
            payload["sessionId"] = session_id

        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_session(self, session_id: str) -> dict:
        """GET /api/session/{sessionID} — récupère une session."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/{session_id}")
        r.raise_for_status()
        return r.json()

    async def list_sessions(self) -> dict:
        """GET /api/session — toutes les sessions (data + cursor)."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session")
        r.raise_for_status()
        return r.json()

    async def delete_session(self, session_id: str) -> bool:
        """DELETE /api/session/{sessionID} — supprime une session."""
        r = await self.app_context.caches.chroma_client.delete(f"{self.base_url}/api/session/{session_id}")
        return r.status_code in (200, 204)

    async def get_active_sessions(self) -> dict:
        """GET /api/session/active — sessions actives."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/active")
        r.raise_for_status()
        return r.json()

    async def get_session_history(self, session_id: str) -> dict:
        """GET /api/session/{sessionID}/history — historique complet."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/{session_id}/history")
        r.raise_for_status()
        return r.json()

    async def get_session_messages(self, session_id: str) -> dict:
        """GET /api/session/{sessionID}/message — messages de la session."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/{session_id}/message")
        r.raise_for_status()
        return r.json()

    async def send_message(
        self,
        session_id: str,
        message: str,
        stream: bool = True,
        timeout: float = 60.0,
    ) -> AsyncGenerator[str, None]:
        """Envoie un message via POST /session/{id}/prompt puis récupère la réponse.

        Architecture :
          1. POST /api/session/{id}/prompt avec {"prompt": {"text": msg}}
             → admet le message, retourne immédiatement (delivery:"steer")
          2. Attend que le message assistant apparaisse dans GET /message
          3. Yield le texte de la réponse

        Args:
            session_id: ID de session existante
            message: texte du message
            stream: réservé (True = full response, pas SSE)
            timeout: temps max d'attente de la réponse

        Yields:
            Chunks avec le texte de la réponse
        """
        import asyncio as _asyncio

        # 1. Admission du prompt
        admit = await self.app_context.caches.chroma_client.post(
            f"{self.base_url}/api/session/{session_id}/prompt",
            json={"prompt": {"text": message}},
        )
        admit.raise_for_status()
        msg_id = admit.json().get("data", {}).get("id", "")
        yield json.dumps({"type": "admitted", "messageId": msg_id}) + "\n"

        # 2. Attendre la réponse assistant (polling)
        deadline = _asyncio.get_event_loop().time() + timeout
        last_count = 0
        while _asyncio.get_event_loop().time() < deadline:
            await _asyncio.sleep(0.3)
            msgs_resp = await self.app_context.caches.chroma_client.get(
                f"{self.base_url}/api/session/{session_id}/message",
            )
            if msgs_resp.status_code != 200:
                continue
            msgs = msgs_resp.json().get("data", [])
            if len(msgs) <= last_count:
                continue
            last_count = len(msgs)
            for m in msgs:
                if m.get("type") == "assistant" and m.get("content"):
                    # Extraire le texte
                    for c in m["content"]:
                        if isinstance(c, dict) and c.get("type") == "text":
                            yield json.dumps({"type": "text", "data": c.get("text", "")}) + "\n"
                    yield json.dumps({"type": "done", "data": m}) + "\n"
                    return

        yield json.dumps({"type": "timeout"}) + "\n"

    async def compact_session(self, session_id: str) -> dict:
        """POST /api/session/{sessionID}/compact — compacte l'historique."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/compact")
        r.raise_for_status()
        return r.json()

    async def interrupt_session(self, session_id: str) -> dict:
        """POST /api/session/{sessionID}/interrupt — interrompt la session."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/interrupt")
        r.raise_for_status()
        return r.json()

    async def wait_session(self, session_id: str) -> dict:
        """POST /api/session/{sessionID}/wait — attend la fin de l'exec."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/wait")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Session Context
    # ====================================================================

    async def get_session_context(self, session_id: str) -> dict:
        """GET /api/session/{sessionID}/context — contexte de session."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/{session_id}/context")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Session Model override
    # ====================================================================

    async def set_session_model(self, session_id: str, model: str) -> dict:
        """POST /api/session/{sessionID}/model — change le modèle."""
        r = await self.app_context.caches.chroma_client.post(
            f"{self.base_url}/api/session/{session_id}/model",
            json={"model": model},
        )
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Session Revert
    # ====================================================================

    async def revert_stage(self, session_id: str) -> dict:
        """POST /api/session/{sessionID}/revert/stage — stage revert."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/revert/stage")
        r.raise_for_status()
        return r.json()

    async def revert_clear(self, session_id: str) -> dict:
        """POST /api/session/{sessionID}/revert/clear — clear revert."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/revert/clear")
        r.raise_for_status()
        return r.json()

    async def revert_commit(self, session_id: str) -> dict:
        """POST /api/session/{sessionID}/revert/commit — commit revert."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/revert/commit")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Session Events (SSE)
    # ====================================================================

    async def session_event_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """GET /api/session/{sessionID}/event — flux SSE d'événements session."""
        async with self.app_context.caches.chroma_client.stream(
            "GET",
            f"{self.base_url}/api/session/{session_id}/event",
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield line + "\n"

    # ====================================================================
    # Agents
    # ====================================================================

    async def list_agents(self) -> dict:
        """GET /api/agent — tous les agents disponibles."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/agent")
        r.raise_for_status()
        return r.json()

    async def set_session_agent(self, session_id: str, agent_id: str) -> dict:
        """POST /api/session/{sessionID}/agent — change l'agent de session."""
        r = await self.app_context.caches.chroma_client.post(
            f"{self.base_url}/api/session/{session_id}/agent",
            json={"agentId": agent_id},
        )
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Permissions
    # ====================================================================

    async def list_permissions(self) -> dict:
        """GET /api/permission/request — permissions en attente."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/permission/request")
        r.raise_for_status()
        return r.json()

    async def list_saved_permissions(self) -> dict:
        """GET /api/permission/saved — permissions sauvegardées."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/permission/saved")
        r.raise_for_status()
        return r.json()

    async def session_permissions(self, session_id: str) -> dict:
        """GET /api/session/{sessionID}/permission — permissions session."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/{session_id}/permission")
        r.raise_for_status()
        return r.json()

    async def reply_permission(self, session_id: str, request_id: str, allow: bool) -> dict:
        """POST /api/session/{sessionID}/permission/{requestID}/reply."""
        r = await self.app_context.caches.chroma_client.post(
            f"{self.base_url}/api/session/{session_id}/permission/{request_id}/reply",
            json={"allow": allow},
        )
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Questions
    # ====================================================================

    async def session_questions(self, session_id: str) -> dict:
        """GET /api/session/{sessionID}/question — questions en attente."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/session/{session_id}/question")
        r.raise_for_status()
        return r.json()

    async def reply_question(self, session_id: str, request_id: str, answers: list[list[str]]) -> dict:
        """POST /api/session/{sessionID}/question/{requestID}/reply."""
        r = await self.app_context.caches.chroma_client.post(
            f"{self.base_url}/api/session/{session_id}/question/{request_id}/reply",
            json={"answers": answers},
        )
        r.raise_for_status()
        return r.json()

    async def reject_question(self, session_id: str, request_id: str) -> dict:
        """POST /api/session/{sessionID}/question/{requestID}/reject."""
        r = await self.app_context.caches.chroma_client.post(f"{self.base_url}/api/session/{session_id}/question/{request_id}/reject")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Filesystem (location-scoped)
    # ====================================================================

    async def fs_list(self, path: str) -> dict:
        """GET /api/fs/list — liste un répertoire."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/fs/list", params={"path": path})
        r.raise_for_status()
        return r.json()

    async def fs_find(self, pattern: str, path: str | None = None) -> dict:
        """GET /api/fs/find — cherche fichiers par pattern."""
        params: dict[str, str] = {"pattern": pattern}
        if path:
            params["path"] = path
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/fs/find", params=params)
        r.raise_for_status()
        return r.json()

    async def fs_read(self, path: str) -> str:
        """GET /api/fs/read/{path} — lit un fichier."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/fs/read/{path.lstrip('/')}")
        r.raise_for_status()
        return r.text

    # ====================================================================
    # Commands
    # ====================================================================

    async def list_commands(self) -> dict:
        """GET /api/command — commandes disponibles."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/command")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Skills
    # ====================================================================

    async def list_skills(self) -> dict:
        """GET /api/skill — skills disponibles."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/skill")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Integrations
    # ====================================================================

    async def list_integrations(self) -> dict:
        """GET /api/integration — intégrations disponibles."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/integration")
        r.raise_for_status()
        return r.json()

    async def get_integration(self, integration_id: str) -> dict:
        """GET /api/integration/{integrationID} — détail intégration."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/integration/{integration_id}")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Credentials
    # ====================================================================

    async def get_credential(self, credential_id: str) -> dict:
        """GET /api/credential/{credentialID} — credential."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/credential/{credential_id}")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # References
    # ====================================================================

    async def list_references(self) -> dict:
        """GET /api/reference — références du projet."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/reference")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Location
    # ====================================================================

    async def get_location(self) -> dict:
        """GET /api/location — localisation courante."""
        r = await self.app_context.caches.chroma_client.get(f"{self.base_url}/api/location")
        r.raise_for_status()
        return r.json()

    # ====================================================================
    # Événements globaux SSE
    # ====================================================================

    async def event_stream(self) -> AsyncGenerator[str, None]:
        """GET /api/event — flux SSE d'événements globaux du daemon."""
        async with self.app_context.caches.chroma_client.stream(
            "GET",
            f"{self.base_url}/api/event",
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield line + "\n"

    # ====================================================================
    # Utilitaires — Run complète (création session + message)
    # ====================================================================

    async def run(
        self,
        message: str,
        mode: SessionMode = SessionMode.CHAT,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Convenience : crée une session + envoie un message.

        Yields les chunks SSE de la réponse.
        """
        session = await self.create_session(
            mode=mode,
            model=model,
            system_prompt=system_prompt,
        )
        session_id = session.get("data", {}).get("id")
        if not session_id:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Pas de sessionId'})}\n\n"
            return

        async for chunk in self.send_message(session_id, message, stream=True):
            yield chunk


# ============================================================================
# Instance globale (singleton)
# ============================================================================
app_context.caches.daemon_client: OpenCodeDaemonClient | None = None


def get_daemon_client() -> OpenCodeDaemonClient:
    """Retourne l'instance unique du client daemon."""
    if app_context.caches.daemon_client is None:
        app_context.caches.daemon_client = OpenCodeDaemonClient()
    return app_context.caches.daemon_client


async def close_daemon_client():
    """Ferme l'instance du client (appelé à l'arrêt)."""
    if app_context.caches.daemon_client:
        await app_context.caches.daemon_client.close()
        app_context.caches.daemon_client = None
