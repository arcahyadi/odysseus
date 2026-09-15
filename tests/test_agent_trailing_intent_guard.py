"""Trailing-intent continuation guard + workspace browser-tool prune.

2026-08-27 stall class (session 3cd660b2): qwen3.5:9b emitted a native-XML
tool call with a mismatched closing tag; Ollama's parsers (qwen35.go +
qwen3coder.go) failed and SILENTLY DROPPED it, so the round ended clean
(HTTP 200, finish=stop) with only the narration ("Let me create them:")
delivered. The agent loop read "0 tool calls + substantive text" as a
final answer and the turn completed without ever running the action.

Two layers ship together:
  1. `_trailing_intent_retry_needed` — one firm recovery round when a
     0-tool round ends on about-to-act narration (tools were offered,
     nothing called all turn, cap 1 per turn).
  2. `_prune_browser_tools_for_workspace_turn` — the failing round carried
     59 tools (Terminus + 30 browser MCP via forced-tools) vs 10-18 on
     healthy rounds; workspace turns drop browser MCP names unless the
     turn's words name browser actions.
"""

import asyncio
import json

import src.agent_loop as al


# ── pure function: trigger conditions ────────────────────────────────────

def test_retry_needed_on_incident_shape():
    # The exact incident shape: short narration ending on a dangling colon.
    assert al._trailing_intent_retry_needed(
        round_text="Let me create them:",
        tools_sent_count=59,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_retry_needed_on_verb_without_colon():
    assert al._trailing_intent_retry_needed(
        round_text="I'll save all six tasks in your todo list now",
        tools_sent_count=12,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    assert al._trailing_intent_retry_needed(
        round_text="Now I run the migration",
        tools_sent_count=3,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    assert al._trailing_intent_retry_needed(
        round_text="going to add the entries",
        tools_sent_count=3,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_retry_blocked_when_already_used():
    # Hard cap 1 — the guard can never loop.
    assert not al._trailing_intent_retry_needed(
        round_text="Let me create them:",
        tools_sent_count=59,
        tool_calls_this_turn=0,
        retry_used=True,
    )


def test_retry_blocked_without_tools_sent():
    # Narration-only is legitimate when no tools were offered.
    assert not al._trailing_intent_retry_needed(
        round_text="Let me create them:",
        tools_sent_count=0,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_retry_blocked_after_tool_calls_in_turn():
    # Post-tool summaries ("Here are your emails:") end with a colon too —
    # zero tool calls for the WHOLE turn is what makes the colon suspicious.
    assert not al._trailing_intent_retry_needed(
        round_text="Here are your emails:",
        tools_sent_count=25,
        tool_calls_this_turn=2,
        retry_used=False,
    )


def test_retry_blocked_on_substantive_answer():
    # Long text, fenced content, or plain answers are not dangling intents.
    assert not al._trailing_intent_retry_needed(
        round_text="Sure! " + "x" * 500 + ":",
        tools_sent_count=25,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    assert not al._trailing_intent_retry_needed(
        round_text="Here is the script:\n```python\nprint(1)\n```",
        tools_sent_count=25,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    assert not al._trailing_intent_retry_needed(
        round_text="The answer is 42.",
        tools_sent_count=25,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_retry_blocked_on_empty_text():
    assert not al._trailing_intent_retry_needed(
        round_text="   ",
        tools_sent_count=25,
        tool_calls_this_turn=0,
        retry_used=False,
    )


# ── pure function: browser-tool prune ────────────────────────────────────

_BROWSER_MIX = {
    "bash", "read_file", "todowrite",
    "mcp__builtin_browser__browser_navigate",
    "mcp__builtin_browser__browser_click",
    "mcp__builtin_browser__browser_snapshot",
    "builtin_browser",
}


def test_prune_drops_browser_tools_on_plain_workspace_turn():
    # "fill"/"submit" alone trip the ROUTE layer's loose browser-intent
    # regex (that is how 30 Playwright tools got forced), but this prune
    # must keep them only for real browser wording.
    dropped = al._prune_browser_tools_for_workspace_turn(
        _BROWSER_MIX, "create six tasks, fill in priorities and submit"
    )
    assert dropped == {
        "mcp__builtin_browser__browser_navigate",
        "mcp__builtin_browser__browser_click",
        "mcp__builtin_browser__browser_snapshot",
        "builtin_browser",
    }


def test_prune_keeps_browser_tools_on_real_browser_wording():
    for text in (
        "clone the repo, then open the site and click the login button",
        "use the browser to fill out the form",
        "take a screenshot of the page",
        "scrape the listings with playwright",
    ):
        assert al._prune_browser_tools_for_workspace_turn(_BROWSER_MIX, text) == set()


def test_prune_handles_empty_tools():
    assert al._prune_browser_tools_for_workspace_turn(None, "anything") == set()
    assert al._prune_browser_tools_for_workspace_turn(set(), "") == set()


# ── replay-style integration through the real loop ───────────────────────

def _collect(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


def _types(chunks):
    out = []
    for c in chunks:
        if c.startswith("data: ") and not c.startswith("data: [DONE]"):
            try:
                out.append(json.loads(c[6:]))
            except Exception:
                pass
    return out


def _patch_common(monkeypatch):
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_exec(block, *a, **k):
        return (block.tool_type, {"output": "ok", "exit_code": 0})
    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)


def _run_loop(monkeypatch, round_texts, max_rounds=6, **extra):
    """Round items are consumed in order; the last one repeats if needed.

    A str item is streamed as a text delta; a dict item is streamed as a
    native tool_calls chunk (the structured channel an API-model route
    uses — fenced blocks are skipped for those routes).
    """
    state = {"n": 0}

    async def _fake_stream(_candidates, messages, **kwargs):
        i = min(state["n"], len(round_texts) - 1)
        state["n"] += 1
        item = round_texts[i]
        if isinstance(item, dict):
            yield f'data: {json.dumps({"type": "tool_calls", "calls": item["calls"]})}\n\n'
        else:
            yield f'data: {json.dumps({"delta": item})}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "http://x/v1", "qwen3.5:9b",
        [{"role": "user", "content": "create six todo tasks"}],
        max_rounds=max_rounds,
        relevant_tools={"bash", "todowrite"},
        **extra,
    )
    return _types(_collect(gen))


_RECOVERED_CALL = {
    "calls": [{
        "name": "update_plan",
        "arguments": json.dumps({"plan": "- [ ] tasks created"}),
    }],
}


def test_recovery_narration_then_tool_call_then_done(monkeypatch):
    """The incident replayed: narration-only round -> guard fires -> the
    re-roll makes the tool call -> turn completes with real work done."""
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        [
            "Let me create them:",          # round 1: dropped call
            _RECOVERED_CALL,                # round 2: recovered call
            "Done — created all six tasks.",  # round 3: final answer
        ],
    )
    retries = [e for e in events if e.get("type") == "trailing_intent_retry"]
    assert len(retries) == 1, events
    assert retries[0]["round"] == 1
    # The recovered round actually executed a tool.
    assert any(e.get("type") == "tool_start" for e in events), events
    # Turn finished normally — no guards tripping at the end.
    assert not any(e.get("type") == "rounds_exhausted" for e in events), events
    assert not any(e.get("type") == "intent_nudge_exhausted" for e in events), events


def test_guard_caps_at_one_retry(monkeypatch):
    """If the re-roll also fails, the turn ends — the guard cannot loop."""
    _patch_common(monkeypatch)
    events = _run_loop(monkeypatch, ["Let me create them:"] * 5, max_rounds=8)
    retries = [e for e in events if e.get("type") == "trailing_intent_retry"]
    assert len(retries) == 1, events


def test_post_tool_summary_never_triggers_guard(monkeypatch):
    """Round 2 summary ending in ':' after real tool work is legitimate."""
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        [
            _RECOVERED_CALL,
            "Here are your emails:",
        ],
    )
    assert not any(e.get("type") == "trailing_intent_retry" for e in events), events
    assert any(e.get("type") == "tool_start" for e in events), events


def test_no_tools_sent_never_triggers_guard(monkeypatch):
    """guide_only turns ship no tool schemas — narration-only is correct."""
    from src.tool_policy import ToolPolicy
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        ["Let me create them:"],
        tool_policy=ToolPolicy(mode="guide_only"),
    )
    assert not any(e.get("type") == "trailing_intent_retry" for e in events), events


def test_guard_skipped_when_nudge_system_message_present(monkeypatch):
    """The guard's own retry round must not re-trigger on its output shape:
    after the retry the turn has no tool calls yet, but retry_used blocks
    a second fire even if the text still dangles."""
    _patch_common(monkeypatch)
    events = _run_loop(
        monkeypatch,
        ["Let me create them:", "Let me create them:", "Done."],
        max_rounds=4,
    )
    retries = [e for e in events if e.get("type") == "trailing_intent_retry"]
    assert len(retries) == 1, events


# ── 2026-09-03 stall class: long future-tense narration, no colon ────────
# Live failing texts (gemma4-thinker, EthGlobal/Wave sessions): 1-3k chars
# of planning prose ending on "I will analyze the srcs directory…", "I am
# diving into the code now.", "we'll focus on identifying…". The old
# total-length cap silenced all of them; the verb list lacked
# analyze/investigate/conduct/dive/report and the "we'll" prefix.

def test_long_narration_i_will_analyze_fires():
    body = (
        "To perform the deep dive into how Hedera fits into the Wave "
        "project, we need to move from general concepts to concrete code "
        "analysis. I will examine how the AI agents process information "
        "and issue commands, where the execution layer waits on block "
        "confirmations, and how external services are called. " + "x" * 900
        + " I am diving into the code now. I will analyze the srcs "
        "directory to identify these components."
    )
    assert al._trailing_intent_retry_needed(
        round_text=body,
        tools_sent_count=22,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_well_prefix_and_identify_fires():
    assert al._trailing_intent_retry_needed(
        round_text="Based on our previous plan, we'll focus on identifying "
                   "the specific decision and execution loops next.",
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_conduct_deepdive_and_report_fires():
    assert al._trailing_intent_retry_needed(
        round_text="I will now conduct a deep-dive into the codebase and "
                   "report back with a map of integration points.",
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_long_answer_early_intent_only_does_not_fire():
    # Genuine long answer that mentioned an intent early then delivered:
    # the closing window has no intent phrase, so no re-roll.
    body = (
        "I will check the logs in a moment, but here is the full answer "
        "you asked for. " + "The analysis shows consistent upward trends "
        "across all measured services. " * 30 + "In summary, everything is "
        "healthy and no action is needed."
    )
    assert not al._trailing_intent_retry_needed(
        round_text=body,
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )


# ── Review follow-up (2026-09-03): honest morphology + boundary pins ─────
# The first widening used VERB(?:ing)? which cannot spell English e-drop
# ("diving" ≠ "dive"+"ing") — "I am diving into the code now." did NOT
# fire while tests passed via second phrases. Stem alternations fix it.
# The prefix group also lacked a leading \b, so i'?ll matched the "ill"
# inside "will" — activated on long tails once the total-length cap went
# away.

def test_diving_standalone_fires():
    # THE live sentence, alone — pins the morphology fix.
    assert al._trailing_intent_retry_needed(
        round_text="I am diving into the code now.",
        tools_sent_count=22,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_will_substring_does_not_fire():
    # Reviewer's concrete false-positive: "will trigger" must need a real
    # subject prefix, not the "ill" inside "will".
    assert not al._trailing_intent_retry_needed(
        round_text="The Dokploy webhook will trigger a rebuild on push, "
                   "so no action is needed.",
        tools_sent_count=25,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_long_colon_ending_with_intent_tail_fires_via_regex():
    # >400 chars ending in ".": colon branch is gated by length, but the
    # intent verb in the closing window fires the regex path.
    body = ("Summary of the review follows. " + "y" * 450
            + " Next: I will analyze the failing module.")
    assert al._trailing_intent_retry_needed(
        round_text=body,
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_long_fenced_with_intent_tail_does_not_fire():
    # Fence gate still suppresses long texts regardless of intent tail.
    body = ("Here is the plan:\n```\nstep 1\nstep 2\n```\n" + "z" * 450
            + " I will analyze it after.")
    assert not al._trailing_intent_retry_needed(
        round_text=body,
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_im_running_statement_is_bounded_tradeoff():
    # "I'm running ..." fires by design (present continuous ≈ about-to);
    # statements like "I'm running late" are the accepted cost, bounded
    # by the cap-1 retry and the tools_sent>0 precondition.
    assert al._trailing_intent_retry_needed(
        round_text="I'm running late but here is the full summary you "
                   "asked for, everything checks out.",
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )


# ── Italian twin (2026-09-12 SPEC 1/3 companion) ─────────────────────────
# The same silent-tool-drop class with Italian narration: qwen3.5 answering
# in Italian ends the round on "Ora controllo i file." and the parser-dropped
# tool call never runs. The English regex alone never matched these.

def test_retry_needed_on_italian_discourse_marker_present():
    assert al._trailing_intent_retry_needed(
        round_text="Ora controllo i file del workspace.",
        tools_sent_count=12,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    assert al._trailing_intent_retry_needed(
        round_text="Adesso verifico gli endpoint configurati.",
        tools_sent_count=8,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_retry_needed_on_italian_progressive():
    assert al._trailing_intent_retry_needed(
        round_text="Sto creando la nota che hai chiesto.",
        tools_sent_count=5,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    assert al._trailing_intent_retry_needed(
        round_text="Stiamo ancora esaminando i log.",
        tools_sent_count=5,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_retry_needed_on_italian_future_tense():
    assert al._trailing_intent_retry_needed(
        round_text="Verificherò gli endpoint e ti farò sapere.",
        tools_sent_count=9,
        tool_calls_this_turn=0,
        retry_used=False,
    )
    # Accent-dropped model typo ("creero") must still match.
    assert al._trailing_intent_retry_needed(
        round_text="Creero il documento subito.",
        tools_sent_count=9,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_italian_final_answers_do_not_fire():
    # Bare present/noun forms ("il controllo" = the check) and completed
    # statements stay quiet — the false-positive budget is the same as the
    # English guard's.
    assert not al._trailing_intent_retry_needed(
        round_text="Ho finito: ecco il riepilogo completo della verifica.",
        tools_sent_count=9,
        tool_calls_this_turn=0,
        retry_used=False,
    )


def test_italian_long_narration_intent_tail_fires():
    body = ("Riepilogo della situazione. " + "x" * 450
            + " Poi controllo le configurazioni.")
    assert al._trailing_intent_retry_needed(
        round_text=body,
        tools_sent_count=10,
        tool_calls_this_turn=0,
        retry_used=False,
    )
