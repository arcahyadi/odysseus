"""SPEC-2: the persisted session ``rag`` flag must drive chat retrieval.

``POST /session`` accepts ``rag`` and stores it on the session row, but the
chat path used to read only the per-request ``use_rag`` form field — and the
composer's global RAG toggle defaults to OFF, posting ``use_rag=false`` on
every send. Sessions built on an indexed knowledge layer therefore got zero
retrieval no matter what the flag said.

Coverage here:
* route-level wiring — POST /api/chat_stream with a rag=true session and
  use_rag=false must hand a TRUTHY use_rag to build_context_preface (calling
  ``_resolve_use_rag`` directly would not catch the call site being deleted,
  which is the same failure class as the original bug);
* flag precedence (image sessions hard-off, flagless sessions unchanged);
* the retrieval block it feeds (owner/k=5 contract, threshold filtering,
  bounded 10k injection) with the ChromaDB layer fully mocked — no live
  ChromaDB required;
* the build_chat_context suppression gates (incognito, blocked tool
  preprocessing, research spin-off, low-signal) still win over the flag and
  now reach the processor even when the request never sent use_rag.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from routes.chat_routes import _resolve_use_rag
from src.chat_processor import ChatProcessor
from src.prompt_security import untrusted_context_message


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


def test_flag_override_log_fires_once_per_session(caplog):
    """The composer posts use_rag=false on every send — the announcement must
    not repeat turn after turn for the same session."""
    import routes.chat_routes as chat_routes

    caplog.set_level("INFO", logger="routes.chat_routes")
    sess = _session(rag=True)
    chat_routes._RAG_FLAG_ANNOUNCED_SESSIONS.clear()
    try:
        for _ in range(3):
            _resolve_use_rag(sess, "false")
        announcements = [
            r for r in caplog.records
            if "rag=true" in r.getMessage() and "composer RAG toggle" in r.getMessage()
        ]
        assert len(announcements) == 1
        # A different session still gets its own one-time announcement.
        _resolve_use_rag(SimpleNamespace(id="sess-2", rag=True), "false")
        announcements = [
            r for r in caplog.records
            if "rag=true" in r.getMessage() and "composer RAG toggle" in r.getMessage()
        ]
        assert len(announcements) == 2
    finally:
        chat_routes._RAG_FLAG_ANNOUNCED_SESSIONS.clear()


# --------------------------------------------------------------------------- #
# ROUTE WIRING — the endpoint must actually consume the flag
# --------------------------------------------------------------------------- #

class _FakeChatHandler:
    def validate_and_extract_preset(self, preset_id):
        return (0.7, 1024, None, None)

    async def preprocess_message(self, message, att_ids, sess, **kwargs):
        return (message, message, message, [], [])

    def update_session_name_if_needed(self, sess, text):
        pass


class _StreamRequest:
    """Minimal stand-in for the FastAPI Request the stream endpoint needs."""

    def __init__(self, form_fields):
        self.headers = {"content-type": "application/x-www-form-urlencoded"}
        self.state = SimpleNamespace(current_user="admin")
        self.app = SimpleNamespace(state=SimpleNamespace())
        self._form = form_fields

    async def form(self):
        return self._form


async def _run_chat_stream(monkeypatch, sess, form_fields):
    """Drive POST /api/chat_stream through the REAL build_chat_context.

    Returns the use_rag value that reached chat_processor.build_context_preface
    ("NOT_PASSED" when the kwarg was omitted, so the processor default applies).
    Only the route's DB/IO side quests are stubbed — the use_rag path under
    test (form field → _resolve_use_rag → build_chat_context → processor) is
    the real shipped code.
    """
    from routes.chat_routes import setup_chat_routes
    import routes.chat_routes as chat_routes
    import routes.chat_helpers as chat_helpers

    captured = {}

    def fake_preface(**kwargs):
        captured["use_rag"] = kwargs.get("use_rag", "NOT_PASSED")
        return [], [], []

    chat_processor = SimpleNamespace(build_context_preface=fake_preface)
    router = setup_chat_routes(
        session_manager=SimpleNamespace(get_session=lambda sid: sess),
        chat_handler=_FakeChatHandler(),
        chat_processor=chat_processor,
        memory_manager=SimpleNamespace(),
        research_handler=SimpleNamespace(),
        upload_handler=SimpleNamespace(),
    )
    endpoint = next(
        route.endpoint
        for route in router.routes
        if route.path == "/api/chat_stream" and "POST" in route.methods
    )

    # Neutralize the route's DB/IO side quests — this test pins the use_rag
    # wiring, not session-ownership, endpoint recovery, or the run manager.
    monkeypatch.setattr(chat_routes, "_verify_session_owner", lambda request, sid, **kw: None)
    monkeypatch.setattr(chat_routes, "_clear_orphaned_session_endpoint", lambda s, owner=None: False)
    monkeypatch.setattr(chat_routes, "_recover_empty_session_model", lambda s, sid, owner=None: False)
    monkeypatch.setattr(chat_routes, "_is_image_generation_session", lambda s, owner=None: False)
    monkeypatch.setattr(chat_routes, "resolve_session_auth", lambda s, sid, owner=None: None)
    monkeypatch.setattr(chat_routes, "get_session_mode", lambda sid: None)
    monkeypatch.setattr(chat_routes, "set_session_mode", lambda sid, mode: None)

    async def _subscribe(session_id, run):
        return
        yield  # pragma: no cover — makes this an (empty) async generator

    monkeypatch.setattr(chat_routes.agent_runs, "start", lambda sid, agen: SimpleNamespace(run_id="test-run"))
    monkeypatch.setattr(chat_routes.agent_runs, "subscribe", _subscribe)

    # Stub build_chat_context's heavyweight collaborators only.
    async def fake_maybe_compact(sess, endpoint_url, model, messages, headers, owner=None, **kwargs):
        return messages, 8192, False

    monkeypatch.setattr(chat_helpers, "load_prefs_for_user", lambda owner: {"memory_enabled": True})
    monkeypatch.setattr(chat_helpers, "_normalize_model_id_from_cache", lambda s: None)
    monkeypatch.setattr(chat_helpers, "normalize_model_id", lambda endpoint_url, model, **kw: None)
    monkeypatch.setattr(chat_helpers, "maybe_compact", fake_maybe_compact)
    monkeypatch.setattr(chat_helpers, "trim_for_context", lambda messages, context_length: messages)
    monkeypatch.setattr(chat_helpers, "fire_message_event", lambda *a, **k: None)
    import src.user_time as user_time

    monkeypatch.setattr(
        user_time,
        "current_datetime_context_message",
        lambda now_utc=None: {"role": "user", "content": "[time]"},
        raising=False,
    )

    request = _StreamRequest(form_fields)
    response = await endpoint(request)
    assert response is not None
    return captured["use_rag"]


def _stream_session(rag):
    sess = SimpleNamespace(
        id="sess-rag-1",
        name="Knowledge chat",
        model="gpt-4o-mini",
        endpoint_url="http://model.local/v1/chat/completions",
        headers={},
        history=[],
        owner="admin",
        rag=rag,
    )
    sess.get_context_messages = lambda: []
    sess.add_message = lambda m: sess.history.append(m)
    return sess


@pytest.mark.asyncio
async def test_chat_stream_wires_session_rag_flag_into_preface(monkeypatch):
    """rag=true session + composer use_rag=false → the context preface still
    gets a TRUTHY use_rag. Deleting the _resolve_use_rag call site in the
    endpoint must fail this test."""
    seen = await _run_chat_stream(
        monkeypatch,
        sess=_stream_session(rag=True),
        form_fields={
            "message": "cosa è successo al bus?",
            "session": "sess-rag-1",
            "mode": "chat",
            "use_rag": "false",
        },
    )
    assert seen is True


@pytest.mark.asyncio
async def test_chat_stream_without_flag_respects_use_rag_false(monkeypatch):
    """Flagless session + composer use_rag=false → preface receives False
    (the pre-fix behavior, unchanged)."""
    seen = await _run_chat_stream(
        monkeypatch,
        sess=_stream_session(rag=False),
        form_fields={
            "message": "cosa è successo al bus?",
            "session": "sess-rag-1",
            "mode": "chat",
            "use_rag": "false",
        },
    )
    assert seen is False


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
    # Expected ceiling derived from the wrapper itself: guard header/footer
    # around a body that is at most 10000 chars + the "[Truncated]" marker.
    wrapper_overhead = len(untrusted_context_message("retrieved documents", "")["content"])
    expected_max = wrapper_overhead + 10000 + len("\n[Truncated]")
    assert len(injected["content"]) <= expected_max
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


def test_rag_unavailable_warning_is_throttled(caplog, monkeypatch):
    """Two retrievals inside the throttle window → exactly one WARNING."""
    import src.chat_processor as chat_processor_module

    monkeypatch.setattr(chat_processor_module, "_last_rag_unavailable_log", 0.0)
    docs = SimpleNamespace(rag_manager=None)
    processor = ChatProcessor(memory_manager=MagicMock(), personal_docs_manager=docs)
    with caplog.at_level("WARNING", logger="src.chat_processor"):
        _build_preface(processor)
        _build_preface(processor)
    warnings = [
        r for r in caplog.records
        if "rag_manager is unavailable" in r.getMessage()
    ]
    assert len(warnings) == 1


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
# build_chat_context — suppressions still win over the session flag, and the
# gate-computed False must reach the processor even when the request never
# sent use_rag (the composer only posts the field when the toggle is OFF).
# --------------------------------------------------------------------------- #

async def _gate_probe(monkeypatch, *, sess=None, message="cosa è successo al bus?", **ctx_kwargs):
    """Run build_chat_context with a recording processor; return the use_rag
    value it received ("NOT_PASSED" = kwarg omitted, processor default True)."""
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

    async def fake_maybe_compact(sess, endpoint_url, model, messages, headers, owner=None, **kwargs):
        return messages, 8192, False

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

    if sess is None:
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
        message=message,
        session_id=getattr(sess, "id", "sess-1"),
        **ctx_kwargs,
    )
    return ctx, seen


@pytest.mark.asyncio
async def test_incognito_suppresses_rag_even_for_flagged_sessions(monkeypatch):
    """Session flag forced "true" by _resolve_use_rag + incognito → the gate
    still wins and the processor receives use_rag=False."""
    ctx, seen = await _gate_probe(monkeypatch, use_rag=_resolve_use_rag(_session(rag=True), "false"), incognito=True)
    assert ctx.rag_sources == []
    assert seen["use_rag"] is False


@pytest.mark.asyncio
async def test_incognito_suppresses_default_on_rag_when_field_absent(monkeypatch):
    """W2 regression: the composer only posts use_rag when the toggle is OFF,
    so RAG-toggle-ON + incognito sends NO field — the gate-computed False must
    still reach the processor instead of falling through to its True default."""
    _, seen = await _gate_probe(monkeypatch, use_rag=None, incognito=True)
    assert seen["use_rag"] is False


@pytest.mark.asyncio
async def test_blocked_tool_preprocessing_suppresses_rag_when_field_absent(monkeypatch):
    _, seen = await _gate_probe(monkeypatch, use_rag=None, allow_tool_preprocessing=False)
    assert seen["use_rag"] is False


@pytest.mark.asyncio
async def test_research_spinoff_suppresses_rag_when_field_absent(monkeypatch):
    sess = _gate_session(
        history=[SimpleNamespace(role="system", metadata={"research_spinoff_from": "src"})]
    )
    _, seen = await _gate_probe(monkeypatch, sess=sess, use_rag=None)
    assert seen["use_rag"] is False


@pytest.mark.asyncio
async def test_low_signal_greeting_suppresses_rag_when_field_absent(monkeypatch):
    _, seen = await _gate_probe(monkeypatch, message="hey", use_rag=None)
    assert seen["use_rag"] is False


@pytest.mark.asyncio
async def test_no_gates_no_field_keeps_processor_default_on(monkeypatch):
    """No gate fires and the request sent no field → retrieval stays enabled
    via the processor default (pre-existing behavior, unchanged)."""
    _, seen = await _gate_probe(monkeypatch, use_rag=None)
    assert seen["use_rag"] in (True, "NOT_PASSED")


def _gate_session(history):
    sess = SimpleNamespace(
        id="sess-1",
        rag=False,
        endpoint_url="http://model.local/v1/chat/completions",
        model="test-model",
        headers={},
        history=history,
        owner="admin",
    )
    sess.get_context_messages = lambda: []
    return sess
