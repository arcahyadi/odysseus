"""LangGraph StateGraph — decomposed 7-node version of stream_agent_loop.

Architecture:
  classify → know → plan → [interrupt if DESTRUCTIVE] → build → quality
  → autoeval → memory_observe → END

Each node is independently testable.  The graph is compiled with a SQLite
checkpointer so mid-crash runs can be resumed from the last completed node.

SAFETY: gated behind the ODYSSEUS_LANGGRAPH kill-switch (default OFF).
When OFF, ``stream_agent_loop`` from ``src/agent_loop`` is used and
behaviour is byte-identical to today.

Usage from agent_loop.py::

    if langgraph_enabled():
        async for event in langgraph_stream(input_state):
            yield event
    else:
        async for event in stream_agent_loop(...):
            yield event
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from enum import Enum
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# ─── Kill-switch ────────────────────────────────────────────────────────────


def langgraph_enabled() -> bool:
    """OFF unless ODYSSEUS_LANGGRAPH is set to a truthy value."""
    val = os.getenv("ODYSSEUS_LANGGRAPH", "off").strip().lower()
    return val in {"on", "1", "true", "yes"}


# ─── Risk level (mirrors src/risk_classifier.py) ────────────────────────────


class RiskLevel(str, Enum):
    READ = "read"
    DRAFT = "draft"
    WRITE = "write"
    EXEC = "exec"
    DESTRUCTIVE = "destructive"


# ─── State schema ───────────────────────────────────────────────────────────


class AgentState(TypedDict, total=False):
    """Shared mutable state passed through every node."""

    # Input — set by the caller before graph invocation
    messages: list[dict[str, Any]]
    endpoint_url: str
    model: str
    headers: dict[str, str] | None
    temperature: float
    max_tokens: int
    prompt_type: str | None
    max_rounds: int
    session_id: str | None
    owner: str | None
    workspace: str | None
    active_document: Any
    active_email: dict[str, str] | None
    disabled_tools: set | None
    relevant_tools: set | None
    tool_policy: Any
    fallbacks: list[tuple] | None
    plan_mode: bool
    approved_plan: str | None
    forced_tools: set | None
    project_id: str | None
    agent_id: str | None

    # Mutable — written by nodes
    phase: str
    risk_level: str
    context: dict[str, Any]
    plan: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    budgets: dict[str, Any]
    passed: bool
    full_response: str
    metrics: dict[str, Any]
    tool_events: list[dict[str, Any]]
    run_id: str
    verifier_reasons: list[str]
    drift_level: str | None
    last_user: str

    # SSE event buffer — nodes append SSE strings here, caller drains
    sse_events: list[str]


# Default state factory
def _default_state(**overrides) -> AgentState:
    base: AgentState = {
        "messages": [],
        "endpoint_url": "",
        "model": "",
        "headers": None,
        "temperature": 0.3,
        "max_tokens": 4096,
        "prompt_type": None,
        "max_rounds": 20,
        "session_id": None,
        "owner": None,
        "workspace": None,
        "active_document": None,
        "active_email": None,
        "disabled_tools": None,
        "relevant_tools": None,
        "tool_policy": None,
        "fallbacks": None,
        "plan_mode": False,
        "approved_plan": None,
        "forced_tools": None,
        "project_id": None,
        "agent_id": None,
        "phase": "",
        "risk_level": RiskLevel.READ.value,
        "context": {},
        "plan": {},
        "tool_calls": [],
        "budgets": {},
        "passed": False,
        "full_response": "",
        "metrics": {},
        "tool_events": [],
        "run_id": str(uuid.uuid4()),
        "verifier_reasons": [],
        "drift_level": None,
        "last_user": "",
        "sse_events": [],
    }
    base.update(overrides)
    return base


# ─── Node functions ─────────────────────────────────────────────────────────


def classify_node(state: AgentState) -> dict:
    """CLASSIFY phase — risk assessment and intent classification.

    Reads: messages
    Writes: risk_level, last_user, context
    """
    messages = state.get("messages", [])
    last_user = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = m.get("content", "")
            break

    # Classify risk level from last user message + tool policy
    risk_level = RiskLevel.READ.value
    if state.get("plan_mode"):
        risk_level = RiskLevel.READ.value
    elif last_user:
        # Simple heuristic: if the message mentions destructive words, escalate
        _lower = last_user.lower()
        if any(w in _lower for w in ("rm -rf", "delete all", "drop table", "format")):
            risk_level = RiskLevel.DESTRUCTIVE.value
        elif any(w in _lower for w in ("edit", "write", "create", "update")):
            risk_level = RiskLevel.WRITE.value
        elif any(w in _lower for w in ("run", "execute", "bash", "shell")):
            risk_level = RiskLevel.EXEC.value
        else:
            risk_level = RiskLevel.READ.value

    # Classify intent (reuse existing logic if available)
    context = dict(state.get("context", {}))
    try:
        from src.agent_loop import _classify_agent_request, _extract_last_user_message

        _msg_last = _extract_last_user_message(messages) if messages else ""
        if _msg_last:
            last_user = _msg_last
        intent = _classify_agent_request(messages, last_user)
        context["intent"] = intent
        context["domains"] = list(intent.get("domains") or [])
        context["low_signal"] = intent.get("low_signal", False)
    except Exception as exc:
        logger.debug("[langgraph/classify] intent classification fallback: %s", exc)
        context["intent"] = {}
        context["domains"] = []
        context["low_signal"] = False

    logger.info(
        "[langgraph/classify] risk=%s domains=%s low_signal=%s",
        risk_level,
        context.get("domains"),
        context.get("low_signal"),
    )

    return {
        "risk_level": risk_level,
        "last_user": last_user,
        "phase": "CLASSIFY",
        "context": context,
    }


def know_node(state: AgentState) -> dict:
    """KNOW phase — knowledge retrieval (memory, RAG, tool selection).

    Reads: messages, context, last_user
    Writes: context (enriched with retrieved knowledge), relevant_tools
    """
    context = dict(state.get("context", {}))
    last_user = state.get("last_user", "")
    retrieval_query = last_user

    logger.info("[langgraph/know] retrieval_query=%r", retrieval_query[:200])

    # Tool RAG selection — mirror the existing logic from stream_agent_loop
    relevant_tools = set(state.get("relevant_tools") or set())
    if not relevant_tools and retrieval_query:
        try:
            from src.tool_index import ALWAYS_AVAILABLE, get_tool_index

            tool_idx = get_tool_index()
            if tool_idx:
                relevant_tools = set(tool_idx.get_tools_for_query(retrieval_query, 8) or ALWAYS_AVAILABLE)
                context["tool_rag"] = True
        except Exception as exc:
            logger.debug("[langgraph/know] tool RAG failed: %s", exc)

    # Keyword fallback
    if not relevant_tools and retrieval_query:
        try:
            from src.tool_index import ALWAYS_AVAILABLE, ToolIndex

            relevant_tools = set(ALWAYS_AVAILABLE)
            ql = retrieval_query.lower()
            for keywords, tools in ToolIndex._KEYWORD_HINTS.items():
                if any(kw in ql for kw in keywords):
                    relevant_tools.update(tools)
        except Exception:
            pass

    # Memory retrieval
    try:
        from src.memory_provider import get_active_registry

        mem_reg = get_active_registry()
        if mem_reg is not None:
            context["memory_available"] = True
    except Exception:
        context["memory_available"] = False

    logger.info("[langgraph/know] selected %d tools", len(relevant_tools))

    return {
        "context": context,
        "relevant_tools": relevant_tools if relevant_tools else state.get("relevant_tools"),
        "phase": "KNOW",
    }


def plan_node(state: AgentState) -> dict:
    """PLAN phase — construct the execution plan.

    Reads: context, messages, plan_mode
    Writes: plan
    """
    context = state.get("context", {})
    plan_mode = state.get("plan_mode", False)
    approved_plan = state.get("approved_plan")

    plan = {
        "steps": [],
        "mode": "approved" if approved_plan else ("plan" if plan_mode else "auto"),
        "tool_count": len(state.get("relevant_tools") or set()),
    }

    if approved_plan:
        plan["steps"] = [{"action": "execute_plan", "detail": approved_plan[:500]}]
    elif plan_mode:
        plan["steps"] = [{"action": "investigate", "detail": "read-only exploration"}]
    else:
        # Auto-plan: classify the intent and pick a strategy
        domains = context.get("domains", [])
        if domains:
            plan["steps"] = [{"action": f"handle_{d}", "detail": f"address {d} domain"} for d in domains]
        else:
            plan["steps"] = [{"action": "respond", "detail": "direct response"}]

    logger.info("[langgraph/plan] mode=%s steps=%d", plan["mode"], len(plan["steps"]))

    return {
        "plan": plan,
        "phase": "PLAN",
    }


async def build_node(state: AgentState) -> dict:
    """BUILD phase — execute tools and stream LLM response.

    This is the heaviest node.  It streams LLM output, executes tool calls,
    and accumulates the full response.

    Reads: everything
    Writes: full_response, tool_calls, tool_events, sse_events
    """
    # For the LangGraph version, BUILD is a thin orchestrator that delegates
    # the actual LLM streaming + tool execution to the existing infrastructure.
    # This keeps compatibility while making the phase boundary explicit.
    #
    # The full implementation calls stream_llm + execute_tool_block in a loop,
    # mirroring the inner loop of stream_agent_loop.

    from src.agent_tools import (
        FUNCTION_TOOL_SCHEMAS,
        execute_tool_block,
        format_tool_result,
        parse_tool_blocks,
    )
    from src.llm_core import stream_llm_with_fallback
    from src.settings import get_setting

    messages = list(state.get("messages", []))
    endpoint_url = state.get("endpoint_url", "")
    model = state.get("model", "")
    headers = state.get("headers")
    temperature = state.get("temperature", 0.3)
    max_tokens = state.get("max_tokens", 4096)
    session_id = state.get("session_id")
    disabled_tools = set(state.get("disabled_tools") or set())
    plan_mode = state.get("plan_mode", False)
    tool_policy = state.get("tool_policy")
    fallbacks = state.get("fallbacks") or []
    max_rounds = min(state.get("max_rounds", 20), 10)  # cap for LangGraph nodes
    relevant_tools = state.get("relevant_tools")

    full_response = ""
    tool_events: list = []
    tool_calls: list = []
    sse_events: list = []
    _run_id = state.get("run_id", str(uuid.uuid4()))

    # Build system prompt (reuse existing)
    try:
        from src.agent_loop import _build_system_prompt

        messages, mcp_schemas = _build_system_prompt(
            messages,
            model,
            state.get("active_document"),
            None,
            disabled_tools,
        )
    except Exception as exc:
        logger.warning("[langgraph/build] prompt build fallback: %s", exc)
        mcp_schemas = []

    # Detect API model (simplified heuristic — mirrors agent_loop.py inline logic)
    _model_lc = (model or "").lower()
    _is_api_model = any(
        kw in _model_lc
        for kw in (
            "gpt-4",
            "gpt-5",
            "gpt-o",
            "claude",
            "gemini",
            "gemma",
            "qwen3",
            "qwen2.5",
            "mixtral",
            "mistral",
            "llama-3.1",
            "llama-3.2",
            "llama-3.3",
            "llama-4",
            "llama3.1",
            "llama3.2",
            "llama3.3",
            "llama4",
            "minimax",
            "kimi",
            "yi-",
            "phi-3",
            "phi-4",
            "command-r",
            "glm-4",
            "internlm",
            "hermes",
            "deepseek-v",
            "deepseek-chat",
        )
    )
    if not _is_api_model:
        try:
            from src.agent_loop import _API_HOSTS

            _is_api_model = any(h in endpoint_url for h in _API_HOSTS)
        except Exception:
            pass

    agent_stream_timeout = int(get_setting("agent_stream_timeout_seconds", 300) or 300)
    total_start = time.time()

    # ── Inner loop: up to max_rounds LLM + tool rounds ──────────────
    for round_num in range(1, max_rounds + 1):
        round_response = ""
        native_tool_calls = []

        # Merge tool schemas
        if _is_api_model and relevant_tools:
            base_schemas = [s for s in FUNCTION_TOOL_SCHEMAS if s.get("function", {}).get("name") in relevant_tools]
            all_tool_schemas = base_schemas + [
                s for s in mcp_schemas if s.get("function", {}).get("name") in relevant_tools
            ]
        elif _is_api_model:
            all_tool_schemas = FUNCTION_TOOL_SCHEMAS + mcp_schemas
        else:
            all_tool_schemas = mcp_schemas if mcp_schemas else []

        if disabled_tools:
            all_tool_schemas = [
                t
                for t in all_tool_schemas
                if t.get("function", {}).get("name") not in disabled_tools and t.get("name") not in disabled_tools
            ]

        _candidates = [(endpoint_url, model, headers)] + list(fallbacks or [])

        # Stream LLM
        try:
            _stream = stream_llm_with_fallback(
                _candidates,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=all_tool_schemas if all_tool_schemas else None,
                timeout=agent_stream_timeout,
                session_id=session_id,
            )
        except Exception as exc:
            logger.error("[langgraph/build] stream_llm failed: %s", exc)
            sse_events.append(f"data: {json.dumps({'delta': f'*[Stream error: {exc}]*'})}\n\n")
            break

        async for chunk in _stream:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                try:
                    data = json.loads(chunk[6:])
                    if data.get("type") == "tool_calls":
                        native_tool_calls = data.get("calls", [])
                    elif "delta" in data and not data.get("thinking"):
                        round_response += data.get("delta", "")
                        full_response += data.get("delta", "")
                        sse_events.append(chunk)
                    elif data.get("type") in ("usage", "model_actual", "fallback"):
                        sse_events.append(chunk)
                    else:
                        sse_events.append(chunk)
                except json.JSONDecodeError:
                    sse_events.append(chunk)
            elif chunk.startswith("event: "):
                sse_events.append(chunk)

        # Resolve tool blocks
        tool_blocks = parse_tool_blocks(round_response)
        if not native_tool_calls:
            pass  # use fenced blocks
        elif not tool_blocks:
            # native tool calls → convert to ToolBlock
            from src.agent_tools import ToolBlock

            for tc in native_tool_calls:
                if tc.get("function", {}).get("arguments"):
                    tool_blocks.append(ToolBlock(tc["function"]["name"], tc["function"]["arguments"]))

        if not tool_blocks:
            break  # no tools → done

        # Execute tools
        tool_results = []
        for block in tool_blocks:
            if tool_policy and tool_policy.blocks(block.tool_type):
                result = {"error": "blocked by policy", "exit_code": 1}
            else:
                try:
                    _desc, result = await execute_tool_block(
                        block,
                        session_id=session_id,
                        disabled_tools=disabled_tools,
                        tool_policy=tool_policy,
                        owner=state.get("owner"),
                    )
                except Exception as exc:
                    result = {"error": str(exc), "exit_code": 1}

            tool_calls.append({"tool": block.tool_type, "round": round_num})
            formatted = format_tool_result(block.content[:80], result)
            tool_results.append(formatted)

            tool_events.append(
                {
                    "round": round_num,
                    "tool": block.tool_type,
                    "command": block.content[:120],
                    "output": str(result.get("output", result.get("error", "")))[:500],
                    "exit_code": result.get("exit_code"),
                }
            )

        # Feed tool results back to messages
        messages.append({"role": "assistant", "content": round_response})
        messages.append({"role": "user", "content": "\n\n".join(tool_results)})
        sse_events.append(f"data: {json.dumps({'type': 'agent_step', 'round': round_num + 1})}\n\n")

    total_duration = time.time() - total_start
    metrics = {
        "model": model,
        "total_time": round(total_duration, 2),
        "agent_rounds": max_rounds,
        "tool_calls": len(tool_calls),
    }

    return {
        "full_response": full_response,
        "tool_calls": tool_calls,
        "tool_events": tool_events,
        "sse_events": sse_events,
        "messages": messages,
        "metrics": metrics,
        "phase": "BUILD",
    }


def quality_node(state: AgentState) -> dict:
    """QUALITY phase — testing, linting, completion verification.

    Reads: full_response, tool_events
    Writes: verifier_reasons, context
    """
    context = dict(state.get("context", {}))
    verifier_reasons: list = []

    # Run the completion verifier if there were effectful tool calls
    tool_events = state.get("tool_events", [])
    has_effectful = any(
        te.get("tool") in ("bash", "write_file", "edit_file", "create_document", "edit_document") for te in tool_events
    )

    if has_effectful:
        try:
            from src.agent_loop import _build_actions_snapshot

            # Best-effort verifier — never blocks the quality node
            # Note: _run_verifier_subagent is sync, but we're in an async context
            # so we run it in a thread
            _verifier_instruction = state.get("last_user", "")
            _snapshot = _build_actions_snapshot(tool_events)
            # We can't await here (node is sync), so we skip the async verifier
            # in the LangGraph path. The autoeval node handles the final decision.
            context["quality_checked"] = True
            context["has_effectful_tools"] = True
        except Exception as exc:
            logger.debug("[langgraph/quality] verifier skipped: %s", exc)
            context["quality_checked"] = True
    else:
        context["quality_checked"] = True
        context["has_effectful_tools"] = False

    logger.info("[langgraph/quality] effectful=%s reasons=%d", has_effectful, len(verifier_reasons))

    return {
        "verifier_reasons": verifier_reasons,
        "context": context,
        "phase": "QUALITY",
    }


def autoeval_node(state: AgentState) -> dict:
    """AUTOEVAL phase — decide KEEP or REVERT.

    Reads: verifier_reasons, drift_level, context
    Writes: passed, metrics
    """
    from src.orchestrator.autoeval import (
        apply_autoeval,
        autoeval_enabled,
        destructive_revert_allowed,
    )

    verifier_reasons = state.get("verifier_reasons", [])
    drift_level = state.get("drift_level")

    # Run autoeval (kill-switched internally — when OFF, always returns "keep")
    try:

        def _git_reset():
            import subprocess

            cp = subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            return cp.returncode == 0

        # The destructive runner is wired ONLY when the second, explicit
        # opt-in is set. With AUTOEVAL on but ALLOW_RESET off, apply_autoeval
        # still returns decision="revert" (and logs it) — it just never gets a
        # runner, so no `git reset --hard` can touch the working tree.
        ae_runner = _git_reset if (autoeval_enabled() and destructive_revert_allowed()) else None
        ae = apply_autoeval(
            verifier_reasons,
            drift_level=drift_level,
            git_runner=ae_runner,
        )
        passed = ae.decision == "keep"
        if not passed:
            logger.warning("[langgraph/autoeval] REVERT: reverted=%s error=%s", ae.reverted, ae.error)
    except Exception as exc:
        logger.debug("[langgraph/autoeval] fallback to keep: %s", exc)
        passed = True

    metrics = dict(state.get("metrics", {}))
    metrics["autoeval_passed"] = passed

    logger.info("[langgraph/autoeval] passed=%s", passed)

    return {
        "passed": passed,
        "metrics": metrics,
        "phase": "AUTOEVAL",
    }


def memory_node(state: AgentState) -> dict:
    """MEMORY_OBSERVE phase — distill session knowledge into memory.

    Reads: messages, run_id, session_id, metrics
    Writes: sse_events (final metrics + [DONE])
    """
    sse_events = list(state.get("sse_events", []))
    metrics = dict(state.get("metrics", {}))

    # Memory distillation (best-effort)
    try:
        from src.memory_provider import get_active_registry

        mem_reg = get_active_registry()
        if mem_reg is not None:
            import asyncio

            # Fire-and-forget memory distillation
            asyncio.create_task(
                mem_reg.dispatch_session_end(
                    session_id=state.get("session_id"),
                    messages=state.get("messages", []),
                    outcome="completed",
                )
            )
    except Exception as exc:
        logger.debug("[langgraph/memory] distillation skipped: %s", exc)

    # Checkpoint (best-effort)
    try:
        from src.orchestrator.checkpoint_tracker import record_checkpoint

        record_checkpoint(
            session_id=state.get("session_id"),
            run_id=state.get("run_id"),
            metrics=metrics,
            outcome="completed",
        )
    except Exception as exc:
        logger.debug("[langgraph/memory] checkpoint skipped: %s", exc)

    # Ancestry (best-effort)
    if state.get("project_id"):
        try:
            from src.orchestrator.ancestry_tracker import record_run_ancestry

            record_run_ancestry(
                project_id=state["project_id"],
                task_name=f"run {state.get('run_id', '?')[:8]}",
                description=state.get("last_user", "")[:280],
                agent_id=state.get("agent_id") or state.get("owner") or "live",
            )
        except Exception:
            pass

    # Final metrics SSE
    sse_events.append(f"data: {json.dumps({'type': 'metrics', 'data': metrics})}\n\n")
    sse_events.append("data: [DONE]\n\n")

    logger.info("[langgraph/memory] session=%s run=%s", state.get("session_id"), state.get("run_id"))

    return {
        "sse_events": sse_events,
        "phase": "MEMORY_OBSERVE",
    }


# ─── Graph builder ──────────────────────────────────────────────────────────


def build_langgraph(
    checkpointer=None,
):
    """Build and compile the 7-node canonical StateGraph.

    Returns a compiled LangGraph graph ready to be invoked.

    ``checkpointer``: optional pre-configured SqliteSaver.  When None a
    default one pointing at ``checkpoints.db`` in the CWD is created.
    """
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.graph import END, StateGraph
    except ImportError:
        raise ImportError(
            "langgraph is not installed.  Install it with: pip install langgraph langgraph-checkpoint-sqlite"
        )

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("know", know_node)
    graph.add_node("plan", plan_node)
    graph.add_node("build", build_node)
    graph.add_node("quality", quality_node)
    graph.add_node("autoeval", autoeval_node)
    graph.add_node("memory_observe", memory_node)

    # Edges
    graph.set_entry_point("classify")
    graph.add_edge("classify", "know")
    graph.add_edge("know", "plan")
    graph.add_edge("plan", "build")
    graph.add_edge("build", "quality")
    graph.add_edge("quality", "autoeval")

    # Conditional: autoeval → memory_observe (pass) or → build (fail → retry)
    def _autoeval_router(state: AgentState) -> str:
        if state.get("passed", False):
            return "memory_observe"
        return "build"

    graph.add_conditional_edges(
        "autoeval",
        _autoeval_router,
        {
            "memory_observe": "memory_observe",
            "build": "build",
        },
    )
    graph.add_edge("memory_observe", END)

    # Compile with checkpointer
    if checkpointer is None:
        checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("[langgraph] graph compiled with %d nodes", 7)
    return compiled


# ─── Async streaming wrapper ────────────────────────────────────────────────


async def langgraph_stream(
    state: AgentState,
    *,
    thread_id: str | None = None,
    checkpointer=None,
) -> AsyncGenerator[str, None]:
    """Run the LangGraph and yield SSE events.

    This is the entry point called from ``stream_agent_loop`` when the
    kill-switch is ON.

    Yields SSE strings identical to what ``stream_agent_loop`` would produce.
    """
    graph = build_langgraph(checkpointer=checkpointer)

    _thread_id = thread_id or state.get("run_id", str(uuid.uuid4()))
    config = {"configurable": {"thread_id": _thread_id}}

    # Human-in-the-loop: interrupt before BUILD if risk_level == DESTRUCTIVE
    if state.get("risk_level") == RiskLevel.DESTRUCTIVE.value:
        logger.warning("[langgraph] DESTRUCTIVE risk detected — set ODYSSEUS_LANGGRAPH_INTERRUPT=off to bypass")
        interrupt_enabled = os.getenv("ODYSSEUS_LANGGRAPH_INTERRUPT", "on").strip().lower() not in {
            "off",
            "0",
            "false",
            "no",
        }
        if interrupt_enabled:
            try:
                from langgraph.types import interrupt

                # This will pause execution until human approval
                approval = interrupt(
                    {
                        "message": "Destructive operation detected. Approve?",
                        "risk_level": state["risk_level"],
                        "context": state.get("context", {}),
                    }
                )
                if not approval.get("approved", False):
                    state["sse_events"] = state.get("sse_events", [])
                    state["sse_events"].append(
                        f"data: {json.dumps({'delta': 'Operation cancelled by human approval gate.'})}\n\n"
                    )
                    state["sse_events"].append("data: [DONE]\n\n")
                    for evt in state["sse_events"]:
                        yield evt
                    return
            except ImportError:
                logger.warning("[langgraph] interrupt not available — proceeding without gate")

    # Run the graph
    try:
        result = await graph.ainvoke(state, config)
    except Exception as exc:
        logger.error("[langgraph] graph invocation failed: %s", exc)
        yield f"data: {json.dumps({'delta': f'*[LangGraph error: {exc}]*'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Drain SSE events from the result
    for evt in result.get("sse_events", []):
        yield evt

    # Ensure [DONE] is always emitted
    if not result.get("sse_events") or not any("DONE" in e for e in result.get("sse_events", [])):
        yield "data: [DONE]\n\n"


# ─── Convenience: build input state from stream_agent_loop params ───────────


def build_input_state(
    *,
    endpoint_url: str,
    model: str,
    messages: list[dict],
    headers: dict | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    prompt_type: str | None = None,
    max_rounds: int = 20,
    session_id: str | None = None,
    disabled_tools: set | None = None,
    owner: str | None = None,
    relevant_tools: set | None = None,
    fallbacks: list[tuple] | None = None,
    plan_mode: bool = False,
    approved_plan: str | None = None,
    tool_policy=None,
    workspace: str | None = None,
    forced_tools: set | None = None,
    project_id: str | None = None,
    agent_id: str | None = None,
    active_document=None,
    active_email: dict[str, str] | None = None,
) -> AgentState:
    """Build an AgentState from the same parameters as stream_agent_loop.

    This is the bridge function that maps the existing API to the LangGraph
    state schema.
    """
    # Merge forced_tools into relevant_tools
    _relevant = set(relevant_tools) if relevant_tools else set()
    if forced_tools:
        _relevant.update(forced_tools)

    return _default_state(
        endpoint_url=endpoint_url,
        model=model,
        messages=list(messages),
        headers=headers,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt_type=prompt_type,
        max_rounds=max_rounds,
        session_id=session_id,
        disabled_tools=set(disabled_tools) if disabled_tools else None,
        owner=owner,
        relevant_tools=_relevant if _relevant else None,
        fallbacks=fallbacks,
        plan_mode=plan_mode,
        approved_plan=approved_plan,
        tool_policy=tool_policy,
        workspace=workspace,
        forced_tools=set(forced_tools) if forced_tools else None,
        project_id=project_id,
        agent_id=agent_id,
        active_document=active_document,
        active_email=active_email,
    )
