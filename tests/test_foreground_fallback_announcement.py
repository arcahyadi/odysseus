"""Foreground fallback announcement (SPEC 3, 2026-09-12).

When the per-user foreground fallback policy (foreground_fallback_enabled +
foreground_model_fallbacks) swaps models on 408/425/429/5xx, the swap used to
be silent in the rendered reply: the ``fallback`` SSE event and post-hoc
metadata recorded it, but the chat transcript showed nothing. The chat stream
route now emits exactly one unobtrusive line naming the answering model,
before the answering model's first content delta, and persists it with the
reply.

The announcement is emitted by the chat route (the owner of the foreground
surface) — not inside agent_loop — so a swap can never be announced twice for
one request, and headless agent consumers (which never pass fallbacks) see no
synthetic text.
"""

import asyncio
import json

import pytest
from fastapi import HTTPException

import src.foreground_model_routing as foreground_model_routing
from src.foreground_model_routing import (
    FOREGROUND_AVAILABILITY_STATUSES,
    foreground_fallback_notice_line,
)
from tests.test_foreground_model_routing import _RouteRequest, _chat_stream_endpoint


# ── pure helper: wording ──────────────────────────────────────────────────

def test_notice_line_names_both_models():
    assert foreground_fallback_notice_line("selected-model", "backup-model") == (
        "[Model fallback: selected-model unavailable; answered by backup-model.]"
    )


def test_notice_line_prefers_endpoint_label_for_same_model_swap():
    # Same model on another account/endpoint: model names would read as a
    # no-op, so the endpoint label carries the distinction.
    assert foreground_fallback_notice_line(
        "selected-model", "selected-model", answered_by_label="Account two"
    ) == "[Model fallback: selected-model unavailable; answered by Account two.]"


def test_notice_line_without_any_identity_still_names_a_route():
    line = foreground_fallback_notice_line(None, None)
    assert "answered by a fallback route" in line


def test_notice_line_same_model_without_label_says_another_endpoint():
    # Repeating the identical model name would read as a no-op.
    assert foreground_fallback_notice_line("selected-model", "selected-model") == (
        "[Model fallback: selected-model unavailable; answered by another endpoint.]"
    )


# ── non-stream /api/chat: announcement at reply start (W2) ───────────────

@pytest.mark.asyncio
async def test_nonstream_chat_announces_fallback_at_reply_start(monkeypatch):
    import src.llm_core as llm_core
    from src.request_models import ChatRequest
    from tests.test_foreground_model_routing import _chat_endpoint

    monkeypatch.setattr(foreground_model_routing, "_load_policy_preferences", lambda owner: {
        "foreground_fallback_enabled": True,
        "foreground_model_fallbacks": [
            {"endpoint_id": "backup", "model": "backup-model"},
        ],
    })
    monkeypatch.setattr(
        foreground_model_routing,
        "resolve_fallback_entries",
        lambda *args, **kwargs: [("https://backup.example/v1", "backup-model", {})],
    )

    async def fake_call(url, model, messages, **kwargs):
        if model == "selected-model":
            raise HTTPException(503, "selected unavailable")
        return "backup answer"

    monkeypatch.setattr(llm_core, "llm_call_async", fake_call)
    endpoint, saved = _chat_endpoint(monkeypatch)

    response = await endpoint(
        _RouteRequest("chat"),
        ChatRequest(message="hello", session="session-1"),
    )

    assert response["response"] == (
        "[Model fallback: selected-model unavailable; answered by backup-model.]\n"
        "backup answer"
    )
    assert saved[-1].content.startswith("[Model fallback:")
    assert response["model"] == "backup-model"
    assert response["requested_model"] == "selected-model"


@pytest.mark.asyncio
async def test_nonstream_chat_no_announcement_without_swap(monkeypatch):
    import src.llm_core as llm_core
    from src.request_models import ChatRequest
    from tests.test_foreground_model_routing import _chat_endpoint

    monkeypatch.setattr(
        foreground_model_routing,
        "_load_policy_preferences",
        lambda owner: {},
    )

    async def fake_call(url, model, messages, **kwargs):
        return "primary answer"

    monkeypatch.setattr(llm_core, "llm_call_async", fake_call)
    endpoint, _saved = _chat_endpoint(monkeypatch)

    response = await endpoint(
        _RouteRequest("chat"),
        ChatRequest(message="hello", session="session-1"),
    )

    assert response["response"] == "primary answer"
    assert response["model"] == response["requested_model"] == "selected-model"


# ── chat route: announcement on real eligibility-driven swaps ─────────────

def _drive_chat_stream(monkeypatch, primary_lines, backup_lines):
    """Run /api/chat_stream in chat mode with the REAL
    stream_llm_with_fallback; only the per-provider stream is stubbed, so
    candidate eligibility (408/425/429/5xx vs 400) is exercised for real."""

    async def fake_stream_llm(url, model, messages, **kwargs):
        lines = primary_lines if model == "selected-model" else backup_lines
        for line in lines:
            yield line

    import routes.chat_routes as chat_routes
    import src.llm_core as llm_core

    captured = {}
    endpoint = _chat_stream_endpoint(monkeypatch, "chat", captured)
    # Re-point the route at the real fallback wrapper; the harness had
    # stubbed it with a chunk player.
    monkeypatch.setattr(
        chat_routes, "stream_llm_with_fallback", llm_core.stream_llm_with_fallback
    )
    monkeypatch.setattr(llm_core, "stream_llm", fake_stream_llm)
    monkeypatch.setattr(foreground_model_routing, "_load_policy_preferences", lambda owner=None: {
        "foreground_fallback_enabled": True,
        "foreground_model_fallbacks": [
            {"endpoint_id": "backup", "model": "backup-model"},
        ],
    })
    monkeypatch.setattr(
        foreground_model_routing,
        "resolve_fallback_entries",
        lambda *args, **kwargs: [("https://backup.example/v1", "backup-model", {})],
    )

    async def run():
        response = await endpoint(_RouteRequest("chat"))
        return [chunk async for chunk in response.body_iterator]

    return asyncio.run(run())


_SUCCESS_LINES = ['data: {"delta": "primary answer"}\n\n', "data: [DONE]\n\n"]
_BACKUP_LINES = ['data: {"delta": "backup answer"}\n\n', "data: [DONE]\n\n"]


def _error_lines(status):
    return [f'event: error\ndata: {json.dumps({"status": status, "error": "unavailable"})}\n\n']


def _notice_deltas(chunks):
    return [
        json.loads(chunk[6:])["delta"]
        for chunk in chunks
        if chunk.startswith("data: ")
        and chunk != "data: [DONE]\n\n"
        and '"delta"' in chunk
        and json.loads(chunk[6:]).get("type") is None
        and "Model fallback:" in json.loads(chunk[6:]).get("delta", "")
    ]


@pytest.mark.parametrize("status", sorted(FOREGROUND_AVAILABILITY_STATUSES))
def test_announcement_emitted_on_each_eligible_failure_status(monkeypatch, status):
    chunks = _drive_chat_stream(monkeypatch, _error_lines(status), _BACKUP_LINES)
    notices = _notice_deltas(chunks)
    assert notices == [
        "[Model fallback: selected-model unavailable; answered by backup-model.]\n"
    ]
    # Exactly one line, and it precedes the answering model's content.
    notice_idx = next(i for i, c in enumerate(chunks) if "Model fallback:" in c)
    answer_idx = next(i for i, c in enumerate(chunks) if '"delta": "backup answer"' in c)
    assert notice_idx < answer_idx


def test_no_announcement_on_success(monkeypatch):
    chunks = _drive_chat_stream(monkeypatch, _SUCCESS_LINES, _BACKUP_LINES)
    assert _notice_deltas(chunks) == []
    assert any('"delta": "primary answer"' in chunk for chunk in chunks)


def test_no_announcement_on_ineligible_failure_without_swap(monkeypatch):
    # 400 is not an availability status: no fallback fires, the error is
    # terminal, and no announcement may be fabricated.
    chunks = _drive_chat_stream(monkeypatch, _error_lines(400), _BACKUP_LINES)
    assert _notice_deltas(chunks) == []
    assert not any('"delta": "backup answer"' in chunk for chunk in chunks)


# ── agent mode: one line even if several rounds report the swap ───────────

@pytest.mark.asyncio
async def test_agent_mode_announces_once_across_repeated_fallback_events(monkeypatch):
    captured = {}
    chunks_in = [
        'data: {"type": "fallback", "round": 1, "selected_model": "selected-model", "answered_by": "backup-model"}\n\n',
        'data: {"delta": "backup narration"}\n\n',
        'data: {"type": "fallback", "round": 2, "selected_model": "selected-model", "answered_by": "backup-model"}\n\n',
        'data: {"delta": "backup final answer"}\n\n',
        "data: [DONE]\n\n",
    ]
    endpoint = _chat_stream_endpoint(monkeypatch, "agent", captured, agent_chunks=chunks_in)
    response = await endpoint(_RouteRequest("agent"))
    emitted = [chunk async for chunk in response.body_iterator]

    notices = _notice_deltas(emitted)
    assert notices == [
        "[Model fallback: selected-model unavailable; answered by backup-model.]\n"
    ]
