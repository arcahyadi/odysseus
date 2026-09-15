"""SPEC-2: the persisted session ``rag`` flag must drive chat retrieval.

``POST /session`` accepts ``rag`` and stores it on the session row, but the
chat path used to read only the per-request ``use_rag`` form field — and the
composer's global RAG toggle defaults to OFF, posting ``use_rag=false`` on
every send. Sessions built on an indexed knowledge layer therefore got zero
retrieval no matter what the flag said. These tests pin the fix
(``_resolve_use_rag`` in routes/chat_routes.py) and the retrieval block it
feeds (``ChatProcessor.build_context_preface``), with the ChromaDB-backed
rag layer fully mocked — no live ChromaDB is required.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from routes.chat_routes import _resolve_use_rag
from src.chat_processor import ChatProcessor


def _session(rag=None):
    if rag is None:
        # A session-like object that predates the flag entirely.
        return SimpleNamespace(id="sess-noflag")
    return SimpleNamespace(id="sess-1", rag=rag)


# --------------------------------------------------------------------------- #
# _resolve_use_rag — flag consumption and precedence
# --------------------------------------------------------------------------- #

def test_session_rag_flag_overrides_composer_toggle_off():
    """The core fix: rag=true sessions retrieve even when the composer posts
    use_rag=false (the composer toggle's default state)."""
    assert _resolve_use_rag(_session(rag=True), "false") == "true"


def test_session_rag_flag_enables_when_request_silent():
    assert _resolve_use_rag(_session(rag=True), None) == "true"


def test_session_without_flag_keeps_request_value():
    """No flag on the session → behavior is byte-for-byte the old one."""
    assert _resolve_use_rag(_session(rag=False), "false") == "false"
    assert _resolve_use_rag(_session(rag=False), None) is None
    assert _resolve_use_rag(_session(rag=False), "true") == "true"


def test_session_object_without_rag_attribute_is_tolerated():
    assert _resolve_use_rag(_session(rag=None), "false") == "false"


def test_image_generation_sessions_stay_hard_off():
    """Image turns never reach a text model — the forced-off must survive the
    session flag (previously this was an unconditional use_rag="false")."""
    assert _resolve_use_rag(
        _session(rag=True), "true", image_generation_session=True
    ) == "false"


# --------------------------------------------------------------------------- #
# ChatProcessor.build_context_preface — retrieval + bounded injection
# --------------------------------------------------------------------------- #

def _processor_with_rag(search_return):
    rag_manager = MagicMock()
    rag_manager.search = MagicMock(return_value=search_return)
    docs = SimpleNamespace(rag_manager=rag_manager)
    processor = ChatProcessor(memory_manager=MagicMock(), personal_docs_manager=docs)
    return processor, rag_manager


def _session_stub():
    return SimpleNamespace(endpoint_url="http://local", model="test", headers={})


def _hit(text, similarity, filename="notes.md"):
    return {
        "id": f"id-{filename}-{similarity}",
        "document": text,
        "metadata": {"filename": filename, "source": f"/data/{filename}"},
        "similarity": similarity,
    }


def _build_preface(processor, **kwargs):
    return processor.build_context_preface(
        message="cosa è successo al bus?",
        session=_session_stub(),
        use_rag=kwargs.pop("use_rag", True),
        use_memory=False,
        use_skills=False,
        **kwargs,
    )


def test_rag_search_called_with_owner_and_k5():
    processor, rag_manager = _processor_with_rag([])
    _build_preface(processor, owner="admin")
    rag_manager.search.assert_called_once_with(
        "cosa è successo al bus?", k=5, owner="admin"
    )


def test_above_threshold_chunks_are_injected_with_provenance():
    processor, _ = _processor_with_rag([
        _hit("Il bus 42 è stato dirottato martedì.", 0.8),
        _hit("Note secondarie sul bus.", 0.2),  # below threshold
    ])
    preface, rag_sources, _web = _build_preface(processor, owner="admin")

    injected = [m for m in preface if (m.get("metadata") or {}).get("source") == "retrieved documents"]
    assert len(injected) == 1, "exactly one retrieved-documents context message"
    content = injected[0]["content"]
    assert "Il bus 42 è stato dirottato martedì." in content
    assert "Note secondarie sul bus." not in content, "below-threshold chunks must not leak"
    assert len(rag_sources) == 1
    assert rag_sources[0]["filename"] == "notes.md"
    assert rag_sources[0]["similarity"] == 0.8


def test_all_results_below_threshold_inject_nothing():
    processor, rag_manager = _processor_with_rag([_hit("irrelevant", 0.1)])
    preface, rag_sources, _ = _build_preface(processor)
    rag_manager.search.assert_called_once()
    assert rag_sources == []
    assert not [
        m for m in preface
        if (m.get("metadata") or {}).get("source") == "retrieved documents"
    ]


def test_injection_is_bounded_to_10000_chars():
    big = "x" * 9000
    processor, _ = _processor_with_rag([
        _hit(big, 0.9, filename="a.md"),
        _hit(big, 0.85, filename="b.md"),
    ])
    preface, rag_sources, _ = _build_preface(processor)
    injected = next(
        m for m in preface
        if (m.get("metadata") or {}).get("source") == "retrieved documents"
    )
    assert len(injected["content"]) < 12000
    assert "[Truncated]" in injected["content"]


def test_use_rag_false_never_touches_the_rag_layer():
    processor, rag_manager = _processor_with_rag([_hit("text", 0.9)])
    _build_preface(processor, use_rag=False)
    rag_manager.search.assert_not_called()


def test_missing_rag_manager_logs_loud_and_skips(caplog, monkeypatch):
    """No ChromaDB → warning (throttled), never an exception, no injection."""
    import src.chat_processor as chat_processor_module

    # Reset the 60s throttle so the assertion holds no matter what ran before.
    monkeypatch.setattr(chat_processor_module, "_last_rag_unavailable_log", 0.0)
    docs = SimpleNamespace(rag_manager=None)
    processor = ChatProcessor(memory_manager=MagicMock(), personal_docs_manager=docs)
    with caplog.at_level("WARNING", logger="src.chat_processor"):
        preface, rag_sources, _ = _build_preface(processor)
    assert rag_sources == []
    assert "rag_manager is unavailable" in caplog.text


def test_rag_manager_exception_does_not_break_the_turn(caplog):
    rag_manager = MagicMock()
    rag_manager.search = MagicMock(side_effect=RuntimeError("chroma down"))
    processor = ChatProcessor(
        memory_manager=MagicMock(),
        personal_docs_manager=SimpleNamespace(rag_manager=rag_manager),
    )
    with caplog.at_level("WARNING", logger="src.chat_processor"):
        preface, rag_sources, _ = _build_preface(processor)
    assert rag_sources == []
    assert len(preface) == 1  # preset-less: only the prompt-safety policy
    assert "RAG retrieval failed" in caplog.text


# --------------------------------------------------------------------------- #
# build_chat_context — suppressions still win over the session flag
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_incognito_still_suppresses_rag_for_flagged_sessions(monkeypatch):
    """The session flag only ever ENABLES retrieval: privacy gates inside
    build_chat_context must keep turning it off (incognito, blocked tool
    preprocessing, research spin-off, low-signal greetings)."""
    import routes.chat_helpers as chat_helpers
    from routes.chat_helpers import PreprocessedMessage, PresetInfo

    seen = {}

    async def fake_preprocess(chat_handler, message, att_ids, sess, **kwargs):
        return PreprocessedMessage(
            enhanced_message=message,
            user_content=message,
            text_for_context=message,
            youtube_transcripts=[],
            attachment_meta=[],
        )

    def fake_preface(**kwargs):
        seen["use_rag"] = kwargs.get("use_rag", "NOT_PASSED")
        return [], [], []

    monkeypatch.setattr(chat_helpers, "preprocess", fake_preprocess)
    monkeypatch.setattr(
        chat_helpers,
        "extract_preset",
        lambda chat_handler, preset_id: PresetInfo(
            temperature=0.7, max_tokens=1024, system_prompt=None, character_name=None
        ),
    )
    monkeypatch.setattr(chat_helpers, "add_user_message", lambda *a, **k: None)
    monkeypatch.setattr(
        chat_helpers, "load_prefs_for_user", lambda owner: {"memory_enabled": True}
    )
    monkeypatch.setattr(chat_helpers, "_normalize_model_id_from_cache", lambda sess: None)
    monkeypatch.setattr(
        chat_helpers, "normalize_model_id", lambda endpoint_url, model, **kw: None
    )

    async def fake_maybe_compact(sess, endpoint_url, model, messages, headers, owner=None, **kwargs):
        return messages, 8192, False

    monkeypatch.setattr(chat_helpers, "maybe_compact", fake_maybe_compact)
    monkeypatch.setattr(
        chat_helpers, "trim_for_context", lambda messages, context_length: messages
    )
    monkeypatch.setattr(
        chat_helpers, "build_uploaded_file_manifest", lambda *a, **k: []
    )
    monkeypatch.setattr(chat_helpers, "fire_message_event", lambda *a, **k: None)
    import src.user_time as user_time

    monkeypatch.setattr(
        user_time,
        "current_datetime_context_message",
        lambda now_utc=None: {"role": "user", "content": "[time]"},
        raising=False,
    )

    # Session with the rag flag consumed by _resolve_use_rag ("true"), sent
    # into build_chat_context with incognito=True.
    sess = SimpleNamespace(
        id="sess-1",
        rag=True,
        endpoint_url="http://model.local/v1/chat/completions",
        model="test-model",
        headers={},
        history=[],
        owner="admin",
    )
    sess.get_context_messages = lambda: []

    ctx = await chat_helpers.build_chat_context(
        sess=sess,
        request=SimpleNamespace(state=SimpleNamespace()),
        chat_handler=SimpleNamespace(),
        chat_processor=SimpleNamespace(build_context_preface=fake_preface),
        message="cosa è successo al bus?",
        session_id="sess-1",
        use_rag=_resolve_use_rag(sess, "false"),
        incognito=True,
    )
    assert ctx.rag_sources == []
    assert seen["use_rag"] is False, "incognito must suppress retrieval even for rag=true sessions"
