import asyncio
import json
import logging
import os
import uuid
from typing import Optional
import httpx

from core.database import CritiquePassRecord, SessionLocal, utcnow_naive

logger = logging.getLogger(__name__)

CRITIQUE_PROMPT = """You are a quality reviewer evaluating an AI assistant's response.

Evaluate the following response for:
1. Factual accuracy (internal consistency check only — do not introduce external claims)
2. Completeness (does it fully address the user's question?)
3. Tone appropriateness (is the tone helpful, clear, and professional?)

Original user question:
{user_question}

Draft response:
{draft}

If the response is satisfactory, return it exactly as-is.
If there are clear deficiencies, return a revised response that corrects them.
Return ONLY the final response text — no commentary, no preamble, no explanation."""


class SessionCritiqueConfig:
    """In-memory per-session critique configuration."""

    def __init__(self):
        self.enabled: bool = False
        self.critique_model: Optional[str] = None
        self.critique_endpoint_url: Optional[str] = None


class CritiqueService:
    def __init__(self):
        # session_id -> SessionCritiqueConfig
        self._session_configs: dict[str, SessionCritiqueConfig] = {}
        self._global_enabled: bool = False
        self._global_critique_model: Optional[str] = None
        self._global_critique_endpoint_url: Optional[str] = None

    def is_enabled_for_session(self, session_id: str) -> bool:
        """Check if critique is enabled; session-level overrides global. Req 7.1"""
        cfg = self._session_configs.get(session_id)
        if cfg is not None:
            return cfg.enabled
        return self._global_enabled

    def set_enabled(
        self,
        session_id: str,
        enabled: bool,
        critique_model: Optional[str] = None,
        critique_endpoint_url: Optional[str] = None,
    ) -> None:
        """Persist per-session config in memory. Req 7.5"""
        cfg = self._session_configs.get(session_id)
        if cfg is None:
            cfg = SessionCritiqueConfig()
            self._session_configs[session_id] = cfg
        cfg.enabled = enabled
        if critique_model is not None:
            cfg.critique_model = critique_model
        if critique_endpoint_url is not None:
            cfg.critique_endpoint_url = critique_endpoint_url

    def set_global(
        self,
        enabled: bool,
        critique_model: Optional[str] = None,
        critique_endpoint_url: Optional[str] = None,
    ) -> None:
        """Update global critique configuration. Req 7.1"""
        self._global_enabled = enabled
        if critique_model is not None:
            self._global_critique_model = critique_model
        if critique_endpoint_url is not None:
            self._global_critique_endpoint_url = critique_endpoint_url

    def get_session_config(self, session_id: str) -> dict:
        """Return current config for a session (for GET endpoint). Req 7.1"""
        cfg = self._session_configs.get(session_id)
        if cfg:
            return {
                "enabled": cfg.enabled,
                "critique_model": cfg.critique_model,
                "critique_endpoint_url": cfg.critique_endpoint_url,
                "source": "session",
            }
        return {
            "enabled": self._global_enabled,
            "critique_model": self._global_critique_model,
            "critique_endpoint_url": self._global_critique_endpoint_url,
            "source": "global",
        }

    def get_global_config(self) -> dict:
        return {
            "enabled": self._global_enabled,
            "critique_model": self._global_critique_model,
            "critique_endpoint_url": self._global_critique_endpoint_url,
        }

    def _resolve_critique_model(
        self, session_id: str, primary_model: str, endpoint_url: str
    ):
        """Returns (model, endpoint_url) for the critique pass. Req 7.6, 7.7"""
        cfg = self._session_configs.get(session_id)
        if cfg and cfg.critique_model:
            return cfg.critique_model, cfg.critique_endpoint_url or endpoint_url
        if self._global_critique_model:
            return self._global_critique_model, self._global_critique_endpoint_url or endpoint_url
        return primary_model, endpoint_url

    async def critique(
        self,
        session_id: str,
        message_id: str,
        user_question: str,
        draft: str,
        primary_model: str,
        endpoint_url: str,
        headers: dict,
        owner: str,
    ) -> str:
        """
        Run a critique pass on the draft response.
        Falls back to returning draft unchanged on ANY error or timeout.
        Persists a CritiquePassRecord in all paths.
        Requirements: 7.2–7.9, 8.6
        """
        critique_model, critique_endpoint = self._resolve_critique_model(
            session_id, primary_model, endpoint_url
        )
        record_id = str(uuid.uuid4())
        self._create_record(
            record_id, session_id, message_id, owner,
            primary_model, critique_model, draft,
        )
        try:
            prompt = CRITIQUE_PROMPT.format(user_question=user_question, draft=draft)
            url = self._build_url(critique_endpoint)
            payload = {
                "model": critique_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await asyncio.wait_for(
                    client.post(url, json=payload, headers=headers),
                    timeout=30.0,
                )
                response.raise_for_status()
            data = response.json()
            revised = data["choices"][0]["message"]["content"].strip()
            was_revised = revised != draft.strip()
            self._update_record(record_id, revised=revised, was_revised=was_revised)
            return revised
        except Exception as exc:
            logger.warning(
                "CritiquePass failed for session=%s, returning draft: %s",
                session_id,
                exc,
            )
            self._update_record(record_id, error=str(exc))
            return draft

    def _build_url(self, endpoint_url: str) -> str:
        base = endpoint_url.rstrip("/")
        if "/v1" in base:
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def _create_record(
        self,
        record_id: str,
        session_id: str,
        message_id: str,
        owner: str,
        primary_model: str,
        critique_model: str,
        original_draft: str,
    ) -> None:
        db = SessionLocal()
        try:
            db.add(
                CritiquePassRecord(
                    id=record_id,
                    session_id=session_id,
                    message_id=message_id,
                    owner=owner,
                    primary_model=primary_model,
                    critique_model=critique_model,
                    original_draft=original_draft,
                    was_revised=False,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _update_record(
        self,
        record_id: str,
        revised: Optional[str] = None,
        was_revised: Optional[bool] = None,
        error: Optional[str] = None,
    ) -> None:
        db = SessionLocal()
        try:
            record = db.query(CritiquePassRecord).filter_by(id=record_id).first()
            if record:
                if revised is not None:
                    record.revised_response = revised
                if was_revised is not None:
                    record.was_revised = was_revised
                if error is not None:
                    record.error_detail = error
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


# Module-level singleton
critique_service = CritiqueService()
