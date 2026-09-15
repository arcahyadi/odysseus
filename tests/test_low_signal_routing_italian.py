"""Low-signal routing must not send Italian requests to a naked model.

2026-09-12 E2E (SPEC 1): "dimmi tutti gli applicativi craftale" — 23 input
tokens, no system prompt, no tools, no RAG — hallucinated "logistica/WMS" and
"flotte navali". Root cause: ``_classify_agent_request``'s domain rules are
English-only, so a generic Italian imperative matched zero domains, was
classified low-signal, and took the direct low-signal path whose message list
for generic (non-finetune) models was ``[{"role": "user", ...}]`` — nothing
else.

Two fixes ship together:
  1. structural — the direct path always carries at least a short base system
     prompt (``_direct_low_signal_messages``), whatever the language;
  2. pragmatic — Italian request verbs/nouns mark a real request so it reaches
     the standard path (multilingual fastembed RAG can still select tools).
"""

import json

import src.agent_loop as al
from src.foreground_model_routing import FOREGROUND_AVAILABILITY_STATUSES


# ── classifier: Italian requests are not low-signal ───────────────────────

def test_italian_generic_question_not_low_signal():
    # The exact E2E repro: no English domain word anywhere.
    intent = al._classify_agent_request([], "dimmi tutti gli applicativi craftale")
    assert intent["low_signal"] is False
    # No domain is forced: the English counterparts ("tell me", "list") seed
    # none either — multilingual RAG retrieval does the tool selection.
    assert intent["domains"] == set()


def test_italian_request_verbs_keep_standard_path():
    for text in (
        "mostrami le note di ieri",
        "elencami tutti i contatti",
        "cerca le ultime notizie",
        "crea un documento",
        "verifica lo stato degli endpoint",
        "cerco informazioni sul server",
        "verifico le impostazioni",
    ):
        intent = al._classify_agent_request([], text)
        assert intent["low_signal"] is False, text


def test_italian_nouns_seed_matching_domains():
    intent = al._classify_agent_request([], "leggi la nota")
    assert "notes_calendar_tasks" in intent["domains"]
    intent = al._classify_agent_request([], "apri il documento")
    assert "documents" in intent["domains"]
    # "email" already matched the English rule; Italian usage must keep working.
    intent = al._classify_agent_request([], "leggi le email di oggi")
    assert "email" in intent["domains"]


def test_italian_requests_in_existing_conversation_stay_contextual():
    messages = [
        {"role": "user", "content": "cerca le email di ieri"},
        {"role": "assistant", "content": "eccole"},
        {"role": "user", "content": "mostrami la prima"},
    ]
    intent = al._classify_agent_request(messages, "mostrami la prima")
    assert intent["low_signal"] is False


# ── backward compat: English low-signal classification is unchanged ───────

def test_english_casual_chat_still_low_signal():
    for text in (
        "hey there, how are you",
        "tell me a joke",
        "what is the meaning of life",
        "???" ,
    ):
        intent = al._classify_agent_request([], text)
        assert intent["low_signal"] is True, text
        assert intent["domains"] == set()


def test_english_domain_requests_still_classified():
    intent = al._classify_agent_request([], "show me the last 5 emails")
    assert intent["low_signal"] is False
    assert "email" in intent["domains"]


def test_english_sentences_never_match_the_italian_gate():
    # None of the gate words are English words; English text must not flip.
    for text in (
        "create a note about the meeting",
        "verify the api token",
        "show the documents folder",
    ):
        # These legitimately match English domain rules anyway; the point is
        # the gate itself stays silent on English.
        assert not al._ITALIAN_REQUEST_RE.search(text.lower()), text


# ── structural: the direct path is never naked ────────────────────────────

def test_direct_low_signal_messages_generic_model_gets_base_prompt():
    messages = al._direct_low_signal_messages(
        [{"role": "user", "content": "dimmi qualcosa"}],
        "dimmi qualcosa",
        qwen_finetune=False,
    )
    assert messages[0]["role"] == "system"
    assert messages[0]["_agent_injected"] == "prompt"
    assert "Odysseus" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "dimmi qualcosa"}


def test_direct_low_signal_messages_qwen_finetune_keeps_tuned_prompt():
    sentinel = [{"role": "system", "content": "tuned minimal prompt"}]
    original = al._minimal_odysseus_general_messages
    try:
        al._minimal_odysseus_general_messages = (
            lambda messages, include_memory=False: sentinel
        )
        out = al._direct_low_signal_messages(
            [{"role": "user", "content": "ciao"}], "ciao", qwen_finetune=True
        )
    finally:
        al._minimal_odysseus_general_messages = original
    assert out is sentinel


def test_direct_low_signal_path_sends_system_prompt(monkeypatch):
    """Worst case end-to-end: "ciao" is low-signal (no English domain, no
    request verb, not a casual-opener greeting) on a fresh conversation with a
    generic model — it still takes the cheap direct path, but the request must
    never be naked again."""
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10)
    monkeypatch.setattr(al, "_is_odysseus_qwen_model", lambda model: False)
    seen_messages = []

    async def fake_stream(candidates, messages, **kwargs):
        seen_messages.append(list(messages))
        yield 'data: {"delta": "Ciao! Come posso aiutarti?"}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", fake_stream)

    chunks = []
    async def run():
        async for chunk in al.stream_agent_loop(
            "https://selected.example/v1",
            "generic-model",
            [{"role": "user", "content": "ciao"}],
            relevant_tools=set(),
            fallback_statuses=FOREGROUND_AVAILABILITY_STATUSES,
            fallback_on_empty=False,
            _is_teacher_run=True,
        ):
            chunks.append(chunk)

    import asyncio

    asyncio.run(run())

    metrics = json.loads(next(
        chunk for chunk in chunks if '"type": "metrics"' in chunk
    )[6:])["data"]
    assert metrics["direct_low_signal"] is True
    assert seen_messages and seen_messages[0][0]["role"] == "system"
    assert "Odysseus" in seen_messages[0][0]["content"]
    assert seen_messages[0][-1] == {"role": "user", "content": "ciao"}


def test_italian_request_bypasses_direct_path_entirely(monkeypatch):
    """The E2E repro must NOT take the naked/cheap path at all: it deserves
    the standard agent path with prompt assembly and tool retrieval."""
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10)

    async def fake_stream(candidates, messages, **kwargs):
        yield 'data: {"delta": "Ecco gli applicativi..."}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", fake_stream)

    chunks = []
    async def run():
        async for chunk in al.stream_agent_loop(
            "https://selected.example/v1",
            "generic-model",
            [{"role": "user", "content": "dimmi tutti gli applicativi craftale"}],
            fallback_statuses=FOREGROUND_AVAILABILITY_STATUSES,
            fallback_on_empty=False,
            _is_teacher_run=True,
        ):
            chunks.append(chunk)

    import asyncio

    asyncio.run(run())
    metrics = json.loads(next(
        chunk for chunk in chunks if '"type": "metrics"' in chunk
    )[6:])["data"]
    # The direct path stamps direct_low_signal=True into its metrics.
    assert metrics.get("direct_low_signal") is not True
