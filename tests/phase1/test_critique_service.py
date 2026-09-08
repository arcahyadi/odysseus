"""
tests/phase1/test_critique_service.py

Property-based and unit tests for CritiqueService.

# Feature: phase-1-intelligence-reasoning, Property 8: Critique Fallback Preserves Draft

Requirements: 7.3, 7.4, 7.8, 7.9, 8.6
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from hypothesis import given, settings, strategies as st

from services.critique.critique_service import CritiqueService, SessionCritiqueConfig


# ── Property 8: Critique Fallback Preserves Draft ────────────────────────────

# Feature: phase-1-intelligence-reasoning, Property 8: Critique Fallback Preserves Draft
@given(st.text(min_size=1, max_size=500))
@settings(max_examples=100)
def test_fallback_returns_draft_on_any_error(draft):
    """For any draft and any LLM failure, critique() returns the draft unchanged."""
    async def run():
        svc = CritiqueService()
        with patch("services.critique.critique_service.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("simulated failure")
            )
            with patch.object(svc, "_create_record"):
                with patch.object(svc, "_update_record"):
                    result = await svc.critique(
                        "sess", "msg", "question", draft,
                        "model", "http://localhost", {}, "user"
                    )
        assert result == draft
    asyncio.run(run())


# ── Config precedence ─────────────────────────────────────────────────────────

class TestConfigPrecedence:
    """Req 7.1"""

    def test_session_overrides_global(self):
        svc = CritiqueService()
        svc.set_global(enabled=True)
        svc.set_enabled("sess-1", enabled=False)
        assert svc.is_enabled_for_session("sess-1") is False

    def test_global_fallback_when_no_session_config(self):
        svc = CritiqueService()
        svc.set_global(enabled=True)
        assert svc.is_enabled_for_session("unset-sess") is True

    def test_disabled_by_default(self):
        svc = CritiqueService()
        assert svc.is_enabled_for_session("brand-new") is False

    def test_session_source_returned(self):
        svc = CritiqueService()
        svc.set_enabled("sess-x", True)
        assert svc.get_session_config("sess-x")["source"] == "session"

    def test_global_source_returned_when_no_session(self):
        svc = CritiqueService()
        assert svc.get_session_config("unset")["source"] == "global"


# ── Model resolution ──────────────────────────────────────────────────────────

class TestModelResolution:
    """Req 7.6, 7.7"""

    def test_uses_primary_when_no_override(self):
        svc = CritiqueService()
        model, _ = svc._resolve_critique_model("sess", "gpt-4", "http://api")
        assert model == "gpt-4"

    def test_uses_session_override(self):
        svc = CritiqueService()
        svc.set_enabled("sess", True, critique_model="phi3", critique_endpoint_url="http://local")
        model, url = svc._resolve_critique_model("sess", "gpt-4", "http://api")
        assert model == "phi3"
        assert url == "http://local"

    def test_uses_global_override_over_primary(self):
        svc = CritiqueService()
        svc.set_global(True, "gemma2", "http://g")
        model, _ = svc._resolve_critique_model("sess", "gpt-4", "http://api")
        assert model == "gemma2"


# ── Pipeline unit tests ───────────────────────────────────────────────────────

class TestCritiquePipeline:
    """Req 7.3, 7.4, 7.8, 7.9, 8.6"""

    @pytest.mark.asyncio
    async def test_successful_revision(self):
        svc = CritiqueService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Better answer"}}]}
        mock_resp.raise_for_status = MagicMock()
        with patch("services.critique.critique_service.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with patch.object(svc, "_create_record"):
                with patch.object(svc, "_update_record") as mock_update:
                    result = await svc.critique(
                        "s", "m", "Q?", "Original",
                        "llama3", "http://localhost:11434", {}, "alice"
                    )
        assert result == "Better answer"
        call_kw = mock_update.call_args[1]
        assert call_kw.get("was_revised") is True

    @pytest.mark.asyncio
    async def test_no_revision_passthrough(self):
        svc = CritiqueService()
        draft = "The answer is 42"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": draft}}]}
        mock_resp.raise_for_status = MagicMock()
        with patch("services.critique.critique_service.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with patch.object(svc, "_create_record"):
                with patch.object(svc, "_update_record") as mock_update:
                    result = await svc.critique("s", "m", "Q?", draft, "m", "http://ep", {}, "u")
        assert result == draft
        assert mock_update.call_args[1].get("was_revised") is False

    @pytest.mark.asyncio
    async def test_timeout_returns_original_draft(self):
        svc = CritiqueService()
        draft = "original"
        with patch("services.critique.critique_service.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            with patch.object(svc, "_create_record"):
                with patch.object(svc, "_update_record") as mock_update:
                    result = await svc.critique("s", "m", "Q?", draft, "m", "http://ep", {}, "u")
        assert result == draft
        assert "error" in mock_update.call_args[1]

    @pytest.mark.asyncio
    async def test_record_created_on_failure(self):
        """CritiquePassRecord is always created, even on failure. Req 8.6"""
        svc = CritiqueService()
        with patch("services.critique.critique_service.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=ConnectionError("refused")
            )
            with patch.object(svc, "_create_record") as mock_create:
                with patch.object(svc, "_update_record"):
                    await svc.critique("s", "m", "Q?", "d", "m", "http://ep", {}, "u")
        mock_create.assert_called_once()
