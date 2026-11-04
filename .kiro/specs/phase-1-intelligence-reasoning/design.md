# Design Document: Phase 1 — Intelligence & Reasoning

## Overview

This document describes the technical design for the five Phase 1 capabilities added to Odysseus:

1. **Multi-Agent Orchestration** — spawning sub-agents, live DAG graph, pause/resume/cancel
2. **Agent Personas / Roles** — CRUD personas, session binding, three built-ins
3. **Long-Horizon Planning** — goal decomposition, cross-session execution, resumption
4. **Self-Critique Loops** — second-model evaluation pass, transparency UI, fallback
5. **Reasoning Traces** — `<think>` extraction, dedicated storage, collapsible UI, forking

All five features extend the existing FastAPI + SQLite + vanilla JS stack. No changes are made
to `routes/chat_routes.py` or `routes/session_routes.py`. Backward compatibility is maintained
throughout via additive schema changes and opt-in activation.

---

## Architecture

### High-Level Component Map

```
FastAPI app.py
│
├── routes/
│   ├── agent_routes.py        ← new: AgentRun CRUD + SSE stream
│   ├── persona_routes.py      ← new: Persona CRUD + activation
│   ├── plan_routes.py         ← new: Plan CRUD + execution control
│   ├── critique_routes.py     ← new: CritiquePass config + toggle
│   └── reasoning_routes.py   ← new: ReasoningTrace CRUD + fork
│
├── services/
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     ← spawn/delegate/synthesise logic
│   │   ├── run_store.py        ← AgentRun DB helpers
│   │   └── oversight.py        ← pause/resume/cancel mechanics
│   ├── personas/
│   │   ├── __init__.py
│   │   └── persona_manager.py  ← Persona CRUD + built-ins + activation
│   ├── planning/
│   │   ├── __init__.py
│   │   ├── planner.py          ← goal decomposition via LLM
│   │   └── executor.py         ← sequential PlanStep runner
│   ├── critique/
│   │   ├── __init__.py
│   │   └── critique_service.py ← draft → critique model → revised response
│   └── reasoning/
│       ├── __init__.py
│       ├── trace_extractor.py  ← <think> tag parser
│       └── trace_store.py      ← ReasoningTrace/Node DB helpers
│
└── core/
    └── database.py             ← 7 new SQLAlchemy models (additive)
```

### Integration Points

| Existing component | How Phase 1 touches it |
|---|---|
| `SessionManager` | Read-only access; personas inject system prompt at session start; planning creates sessions via `ensure_task_session()` |
| `MemoryManager` | Personas pass a `memory_scope` string; orchestration reads/writes scoped memory per sub-agent |
| `AuthManager` | All new routes call `get_current_user()` / `_verify_session_owner()`; owner column on every new model |
| `chat_routes.py` | **Untouched.** Critique and reasoning hooks are injected at the `stream_agent_loop` call-site in `routes/chat_helpers.py` via thin wrapper |
| `src/agent_loop.py` | Reasoning trace extraction added as a post-processing step wrapping the existing generator; no loop logic changed |


---

## Database Models

### Migration Strategy

**Choice: `core/database.py` additive `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS` at startup.**

Rationale: Odysseus uses a single SQLite file (`data/app.db`) and currently calls `Base.metadata.create_all(engine)` at startup in `src/app_initializer.py`. Phase 1 adds new `Base` subclasses to `core/database.py`; SQLAlchemy's `create_all` will create new tables automatically and is idempotent for existing ones.

For new columns on *existing* tables (only `Session` gets two new columns), a lightweight startup migration function runs raw `ALTER TABLE … ADD COLUMN IF NOT EXISTS` before `create_all`. This avoids introducing Alembic as a dependency while keeping the migration safe on any existing database.

```python
# core/phase1_migrations.py
def run_phase1_migrations(engine):
    """Idempotent column additions on existing tables."""
    with engine.connect() as conn:
        _add_col_if_missing(conn, "sessions", "forked_from_session_id", "TEXT")
        _add_col_if_missing(conn, "sessions", "forked_from_message_id", "TEXT")
        _add_col_if_missing(conn, "sessions", "active_persona_id", "TEXT")

def _add_col_if_missing(conn, table, column, col_type):
    import sqlite3
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    except Exception:
        pass  # column already exists
```

Called from `app.py` lifespan before `create_all`.

---

### New SQLAlchemy Models

All new models follow the existing `TimestampMixin` pattern and use `String` primary keys (UUID strings) to match the rest of the codebase.


#### `AgentRun`

```python
class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id             = Column(String, primary_key=True, index=True)
    owner          = Column(String, nullable=True, index=True)       # username
    parent_run_id  = Column(String, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    persona_id     = Column(String, ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    session_id     = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    root_run_id    = Column(String, nullable=True, index=True)       # denormalised for fast subtree queries
    depth          = Column(Integer, default=0, nullable=False)      # 0 = root orchestrator
    task_description = Column(Text, nullable=False)
    status         = Column(String, default="pending", nullable=False, index=True)
    # status values: pending | running | completed | failed | paused | cancelled
    result         = Column(Text, nullable=True)                     # JSON final output
    error_detail   = Column(Text, nullable=True)
    tool_calls_log = Column(Text, nullable=True)                     # JSON array of tool call records
    input_tokens   = Column(Integer, default=0)
    output_tokens  = Column(Integer, default=0)
    started_at     = Column(DateTime, nullable=True)
    ended_at       = Column(DateTime, nullable=True)
    # checkpoint: last message list serialised for pause/resume
    checkpoint     = Column(Text, nullable=True)                     # JSON

    parent = relationship("AgentRun", remote_side=[id], backref="children")
    persona = relationship("Persona", foreign_keys=[persona_id])
    session = relationship("Session", backref=backref("agent_runs", cascade="save-update, merge"))

    __table_args__ = (
        Index("ix_agent_runs_owner_status", "owner", "status"),
        Index("ix_agent_runs_root", "root_run_id", "depth"),
        Index("ix_agent_runs_retention", "owner", "created_at"),
    )
```

#### `Persona`

```python
class Persona(TimestampMixin, Base):
    __tablename__ = "personas"

    id             = Column(String, primary_key=True, index=True)
    owner          = Column(String, nullable=True, index=True)       # NULL = built-in / global
    name           = Column(String, nullable=False)                  # 1–64 chars, unique per owner
    system_prompt  = Column(Text, nullable=False)
    allowed_tools  = Column(Text, nullable=True)                     # JSON list of tool names; NULL = all
    memory_scope   = Column(String, nullable=True)                   # e.g. "global", "persona:<id>", "session"
    model_ref      = Column(String, nullable=True)                   # model name override
    endpoint_url   = Column(String, nullable=True)                   # endpoint override
    is_builtin     = Column(Boolean, default=False)
    is_active      = Column(Boolean, default=True)                   # soft-delete
    sort_order     = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_personas_owner_name", "owner", "name", unique=True),
        Index("ix_personas_active", "owner", "is_active"),
    )
```


#### `Plan` and `PlanStep`

```python
class Plan(TimestampMixin, Base):
    __tablename__ = "plans"

    id             = Column(String, primary_key=True, index=True)
    owner          = Column(String, nullable=True, index=True)
    title          = Column(String, nullable=False)
    goal           = Column(Text, nullable=False)                    # original user goal text
    status         = Column(String, default="pending", nullable=False, index=True)
    # status: pending | running | paused_on_failure | completed | cancelled
    current_step_index = Column(Integer, default=0)
    model          = Column(String, nullable=True)
    endpoint_url   = Column(String, nullable=True)

    steps = relationship("PlanStep", back_populates="plan",
                         cascade="all, delete-orphan",
                         order_by="PlanStep.order_index")

    __table_args__ = (
        Index("ix_plans_owner_status", "owner", "status"),
    )


class PlanStep(TimestampMixin, Base):
    __tablename__ = "plan_steps"

    id             = Column(String, primary_key=True, index=True)
    plan_id        = Column(String, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index    = Column(Integer, nullable=False)
    title          = Column(String(120), nullable=False)
    description    = Column(Text, nullable=True)
    status         = Column(String, default="pending", nullable=False)
    # status: pending | running | done | failed | skipped
    session_id     = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    output         = Column(Text, nullable=True)                     # result of step execution
    error_detail   = Column(Text, nullable=True)
    retry_count    = Column(Integer, default=0)
    started_at     = Column(DateTime, nullable=True)
    ended_at       = Column(DateTime, nullable=True)

    plan    = relationship("Plan", back_populates="steps")
    session = relationship("Session", backref=backref("plan_steps"))

    __table_args__ = (
        Index("ix_plan_steps_plan_order", "plan_id", "order_index"),
        Index("ix_plan_steps_status", "plan_id", "status"),
    )
```

#### `CritiquePassRecord`

```python
class CritiquePassRecord(TimestampMixin, Base):
    __tablename__ = "critique_pass_records"

    id               = Column(String, primary_key=True, index=True)
    session_id       = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id       = Column(String, nullable=True)                 # DB id of the assistant message
    owner            = Column(String, nullable=True, index=True)
    primary_model    = Column(String, nullable=False)
    critique_model   = Column(String, nullable=False)
    was_revised      = Column(Boolean, default=False)
    original_draft   = Column(Text, nullable=False)
    revised_response = Column(Text, nullable=True)
    original_tokens  = Column(Integer, default=0)
    revised_tokens   = Column(Integer, default=0)
    error_detail     = Column(Text, nullable=True)                   # set on fallback

    __table_args__ = (
        Index("ix_critique_session_msg", "session_id", "message_id"),
    )
```

#### `ReasoningTrace` and `ReasoningNode`

```python
class ReasoningTrace(TimestampMixin, Base):
    __tablename__ = "reasoning_traces"

    id          = Column(String, primary_key=True, index=True)
    session_id  = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id  = Column(String, nullable=False, index=True)          # DB id of the parent assistant message
    owner       = Column(String, nullable=True, index=True)
    model       = Column(String, nullable=True)
    full_text   = Column(Text, nullable=False)                        # raw concatenated think content

    nodes = relationship("ReasoningNode", back_populates="trace",
                         cascade="all, delete-orphan",
                         order_by="ReasoningNode.index")

    __table_args__ = (
        Index("ix_reasoning_session_msg", "session_id", "message_id"),
    )


class ReasoningNode(Base):
    __tablename__ = "reasoning_nodes"

    id         = Column(String, primary_key=True, index=True)
    trace_id   = Column(String, ForeignKey("reasoning_traces.id", ondelete="CASCADE"), nullable=False, index=True)
    index      = Column(Integer, nullable=False)
    content    = Column(Text, nullable=False)

    trace = relationship("ReasoningTrace", back_populates="nodes")

    __table_args__ = (
        Index("ix_reasoning_nodes_trace_idx", "trace_id", "index"),
    )
```


### Existing Table Additions

Two new columns on `sessions` (via `ALTER TABLE ADD COLUMN IF NOT EXISTS`):

| Column | Type | Purpose |
|---|---|---|
| `forked_from_session_id` | TEXT nullable | Source session for fork |
| `forked_from_message_id` | TEXT nullable | Source message for fork |
| `active_persona_id` | TEXT nullable | Currently active persona |

---

### ER Diagram (text form)

```
sessions ─────────────────────────────────────────────────────────────────┐
  │ id PK                                                                   │
  │ active_persona_id → personas.id                                         │
  │ forked_from_session_id → sessions.id (self-ref)                         │
  │ forked_from_message_id                                                  │
  │                                                                         │
  ├──< agent_runs                                                           │
  │      id PK                                                              │
  │      parent_run_id → agent_runs.id (self-ref, tree)                     │
  │      root_run_id (denorm)                                               │
  │      persona_id → personas.id                                           │
  │      session_id → sessions.id                                           │
  │      depth, status, task_description, result, checkpoint                │
  │                                                                         │
  ├──< plan_steps                                                           │
  │      id PK                                                              │
  │      plan_id → plans.id                                                 │
  │      session_id → sessions.id                                           │
  │      order_index, status, title, description, output                    │
  │                                                                         │
  ├──< critique_pass_records                                                │
  │      id PK                                                              │
  │      session_id → sessions.id                                           │
  │      message_id (string ref to chat_messages.id)                        │
  │      primary_model, critique_model, was_revised                         │
  │                                                                         │
  └──< reasoning_traces                                                     │
         id PK                                                              │
         session_id → sessions.id                                           │
         message_id (string ref)                                            │
         └──< reasoning_nodes                                               │
                id PK                                                       │
                trace_id → reasoning_traces.id                             │
                index, content                                              │
                                                                           │
personas ──────────────────────────────────────────────────────────────────┘
  id PK
  owner, name, system_prompt, allowed_tools (JSON), memory_scope
  model_ref, endpoint_url, is_builtin, is_active

plans
  id PK
  owner, title, goal, status, current_step_index
  └──< plan_steps (see above)
```

---


## Service Modules

### `services/orchestration/orchestrator.py`

Core responsibilities: spawn sub-agents, enforce depth limits, synthesise results.

```python
class Orchestrator:
    MAX_DEPTH = int(os.getenv("AGENT_MAX_DEPTH", "3"))

    def __init__(self, session_manager, memory_manager):
        self._sm = session_manager
        self._mm = memory_manager
        # run_id → asyncio.Event for pause signalling
        self._pause_events: dict[str, asyncio.Event] = {}
        # run_id → asyncio.CancelScope (or Task) for cancel
        self._cancel_flags: dict[str, bool] = {}

    async def start_run(
        self,
        task: str,
        owner: str,
        persona_id: str | None,
        parent_run_id: str | None = None,
        depth: int = 0,
    ) -> AgentRun:
        if depth > self.MAX_DEPTH:
            raise DepthLimitError(f"Max agent depth {self.MAX_DEPTH} exceeded")
        run = _create_agent_run_record(task, owner, persona_id, parent_run_id, depth)
        asyncio.create_task(self._execute_run(run))
        return run

    async def _execute_run(self, run: AgentRun):
        try:
            _update_run_status(run.id, "running")
            persona = _load_persona(run.persona_id)
            messages = _build_initial_messages(run.task_description, persona)
            # Wrap existing stream_agent_loop — captures tool calls and sub-agent requests
            async for event in self._agent_loop_with_hooks(run, messages, persona):
                await _emit_sse(run.root_run_id, event)
                await self._check_pause(run.id)
                if self._cancel_flags.get(run.id):
                    _update_run_status(run.id, "cancelled")
                    return
            _update_run_status(run.id, "completed")
        except Exception as e:
            _update_run_status(run.id, "failed", error=str(e))
            _propagate_failure_to_parent(run)

    async def _check_pause(self, run_id: str):
        """Yield to pause event if set; blocks until resumed."""
        event = self._pause_events.get(run_id)
        if event and event.is_set():
            _update_run_status(run_id, "paused")
            await event.wait()   # wait is a no-op once cleared; we wait for clear
            _update_run_status(run_id, "running")
```

Sub-agent spawning is triggered when the LLM emits a special tool call `delegate_to_subagent(task, persona_id)`. The orchestrator intercepts this before returning it to the LLM and recursively calls `start_run` with `depth + 1`.

```python
    async def _agent_loop_with_hooks(self, run, messages, persona):
        async for chunk in stream_agent_loop(messages, ...):
            if _is_delegate_tool_call(chunk):
                sub_run = await self.start_run(
                    task=chunk["task"],
                    owner=run.owner,
                    persona_id=chunk.get("persona_id"),
                    parent_run_id=run.id,
                    depth=run.depth + 1,
                )
                # Inject sub-agent result into messages as a tool response
                result = await _await_run_result(sub_run.id)
                messages.append({"role": "tool", "content": result})
            else:
                yield chunk
```

### `services/orchestration/oversight.py`

Pause, resume, cancel operations. These are called from route handlers.

```python
async def pause_run(root_run_id: str):
    """Signal all running sub-agents in this tree to pause."""
    run_ids = _get_all_running_in_tree(root_run_id)
    for rid in run_ids:
        orchestrator._pause_events[rid] = asyncio.Event()
        orchestrator._pause_events[rid].set()   # causes _check_pause to block

async def resume_run(root_run_id: str):
    for rid, event in orchestrator._pause_events.items():
        if _run_belongs_to_root(rid, root_run_id):
            event.clear()   # unblocks _check_pause

async def cancel_run(root_run_id: str):
    run_ids = _get_all_in_tree(root_run_id)
    for rid in run_ids:
        orchestrator._cancel_flags[rid] = True
    _bulk_update_status(run_ids, "cancelled")
```


### `services/personas/persona_manager.py`

```python
BUILTIN_PERSONAS = [
    {
        "id": "builtin-code-reviewer",
        "name": "Code Reviewer",
        "system_prompt": "You are an expert code reviewer...",
        "allowed_tools": ["read_file", "run_tests"],
        "memory_scope": "session",
        "is_builtin": True,
    },
    {
        "id": "builtin-legal-analyst",
        "name": "Legal Analyst",
        "system_prompt": "You are a legal analyst...",
        "allowed_tools": [],   # text-only
        "memory_scope": "session",
        "is_builtin": True,
    },
    {
        "id": "builtin-personal-trainer",
        "name": "Personal Trainer",
        "system_prompt": "You are a personal fitness coach...",
        "allowed_tools": [],
        "memory_scope": "global",
        "is_builtin": True,
    },
]

class PersonaManager:
    PER_USER_LIMIT = int(os.getenv("PERSONA_PER_USER_LIMIT", "50"))

    def seed_builtins(self):
        """Idempotently insert built-in personas on startup."""
        db = SessionLocal()
        try:
            for p in BUILTIN_PERSONAS:
                if not db.query(Persona).filter_by(id=p["id"]).first():
                    db.add(Persona(**p))
            db.commit()
        finally:
            db.close()

    def create(self, owner: str, name: str, **kwargs) -> Persona:
        db = SessionLocal()
        try:
            count = db.query(Persona).filter_by(owner=owner, is_active=True).count()
            if count >= self.PER_USER_LIMIT:
                raise PersonaLimitError(f"Limit of {self.PER_USER_LIMIT} personas reached")
            if not (1 <= len(name) <= 64):
                raise ValueError("Name must be 1–64 characters")
            if db.query(Persona).filter_by(owner=owner, name=name, is_active=True).first():
                raise ValueError(f"Persona '{name}' already exists")
            p = Persona(id=str(uuid.uuid4()), owner=owner, name=name, **kwargs)
            db.add(p)
            db.commit()
            return p
        finally:
            db.close()

    def activate_for_session(self, session_id: str, persona_id: str):
        """Stamp the session's active_persona_id column and return the persona."""
        db = SessionLocal()
        try:
            persona = db.query(Persona).filter_by(id=persona_id, is_active=True).first()
            if not persona:
                raise KeyError("Persona not found")
            db.query(DbSession).filter_by(id=session_id).update(
                {"active_persona_id": persona_id}
            )
            db.commit()
            return persona
        finally:
            db.close()
```

### `services/planning/planner.py`

Goal decomposition via a structured LLM prompt returning JSON.

```python
DECOMPOSE_PROMPT = """
You are a planning assistant. Break the following goal into an ordered list of
2 to 50 concrete, actionable steps. Return JSON only:
{"steps": [{"title": "...", "description": "..."}]}

Goal: {goal}
"""

async def decompose_goal(goal: str, endpoint_url: str, model: str, headers: dict) -> list[dict]:
    prompt = DECOMPOSE_PROMPT.format(goal=goal)
    raw = await llm_call_async(endpoint_url, model, [{"role": "user", "content": prompt}], headers=headers)
    data = json.loads(raw)
    steps = data.get("steps", [])
    if not (2 <= len(steps) <= 50):
        raise ValueError(f"LLM returned {len(steps)} steps; expected 2–50")
    return steps
```

### `services/planning/executor.py`

```python
class PlanExecutor:
    async def execute(self, plan_id: str, owner: str):
        plan = _load_plan(plan_id)
        for step in plan.steps:
            if step.status == "done":
                continue
            if self._cancelled.get(plan_id):
                break
            await self._execute_step(plan, step, owner)
            if step.status == "failed":
                _update_plan_status(plan_id, "paused_on_failure")
                _notify_user(owner, f"Plan '{plan.title}' paused: step '{step.title}' failed.")
                return
        _update_plan_status(plan_id, "completed")

    async def _execute_step(self, plan, step, owner):
        _update_step_status(step.id, "running")
        session = session_manager.ensure_task_session(
            session_id=f"plan-{plan.id}-step-{step.order_index}",
            name=f"[Plan] {step.title[:60]}",
            endpoint_url=plan.endpoint_url,
            model=plan.model,
            owner=owner,
        )
        _link_step_to_session(step.id, session.id)
        try:
            result = await _run_agent_for_step(session, step.description)
            _save_step_output(step.id, result)
            _update_step_status(step.id, "done")
        except Exception as e:
            step.retry_count += 1
            if step.retry_count >= MAX_RETRIES:
                _update_step_status(step.id, "failed", error=str(e))
            else:
                await self._execute_step(plan, step, owner)  # retry
```


### `services/critique/critique_service.py`

The critique service wraps the primary LLM response. It is invoked from a thin hook in `routes/chat_helpers.py` only when the session has critique enabled.

```python
CRITIQUE_PROMPT = """
You are a quality reviewer. Evaluate the following AI response for:
1. Factual accuracy (internal consistency only — do not introduce external claims)
2. Completeness (does it address the user's question fully?)
3. Tone appropriateness

Original user question:
{user_question}

Draft response:
{draft}

If the response is satisfactory, return it unchanged.
If there are deficiencies, return a revised response that corrects them.
Return the response text ONLY — no commentary, no explanation, no preamble.
"""

class CritiqueService:
    def is_enabled_for_session(self, session_id: str) -> bool:
        db = SessionLocal()
        try:
            row = db.query(SessionCritiqueConfig).filter_by(session_id=session_id).first()
            if row:
                return row.enabled
            # Fall back to global config
            return _global_critique_enabled()
        finally:
            db.close()

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
        critique_model, critique_endpoint = self._resolve_critique_model(session_id, primary_model, endpoint_url)
        record = _create_record(session_id, message_id, owner, primary_model, critique_model, draft)
        try:
            prompt = CRITIQUE_PROMPT.format(user_question=user_question, draft=draft)
            revised = await asyncio.wait_for(
                llm_call_async(critique_endpoint, critique_model,
                               [{"role": "user", "content": prompt}], headers=headers),
                timeout=30.0,
            )
            was_revised = (revised.strip() != draft.strip())
            _update_record(record.id, revised=revised, was_revised=was_revised)
            return revised
        except Exception as e:
            _update_record(record.id, error=str(e))
            logger.warning("CritiquePass failed, returning draft: %s", e)
            return draft   # Req 7.9 fallback
```

The hook in `routes/chat_helpers.py`:

```python
# After save_assistant_response(), before streaming to client:
async def maybe_apply_critique(session_id, message_id, user_q, draft, sess, owner) -> str:
    if not critique_service.is_enabled_for_session(session_id):
        return draft
    return await critique_service.critique(
        session_id, message_id, user_q, draft,
        sess.model, sess.endpoint_url, sess.headers, owner
    )
```

### `services/reasoning/trace_extractor.py`

```python
import re

# Matches <think>...</think> blocks (non-greedy, handles multi-block)
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

def extract_thinking(text: str) -> tuple[str, list[str]]:
    """Returns (text_without_think_blocks, list_of_think_segments)."""
    segments = _THINK_RE.findall(text)
    clean = _THINK_RE.sub("", text).strip()
    return clean, [s.strip() for s in segments if s.strip()]

def extract_thinking_streaming(accumulated: str) -> tuple[str, list[str], bool]:
    """For use during SSE streaming — detects a complete </think> tag.
    Returns (clean_so_far, segments_found, has_open_think).
    """
    segments = _THINK_RE.findall(accumulated)
    clean = _THINK_RE.sub("", accumulated)
    has_open = "<think>" in accumulated and "</think>" not in accumulated
    return clean, segments, has_open
```

### `services/reasoning/trace_store.py`

```python
class TraceStore:
    def persist(self, session_id: str, message_id: str, owner: str,
                model: str, segments: list[str]) -> ReasoningTrace | None:
        if not segments:
            return None
        db = SessionLocal()
        try:
            trace_id = str(uuid.uuid4())
            trace = ReasoningTrace(
                id=trace_id,
                session_id=session_id,
                message_id=message_id,
                owner=owner,
                model=model,
                full_text="\n\n".join(segments),
            )
            db.add(trace)
            for idx, seg in enumerate(segments):
                db.add(ReasoningNode(
                    id=str(uuid.uuid4()),
                    trace_id=trace_id,
                    index=idx,
                    content=seg,
                ))
            db.commit()
            return trace
        finally:
            db.close()

    def get_for_message(self, message_id: str) -> ReasoningTrace | None:
        db = SessionLocal()
        try:
            return db.query(ReasoningTrace).filter_by(message_id=message_id)\
                     .options(joinedload(ReasoningTrace.nodes)).first()
        finally:
            db.close()
```


---

## API Endpoints

### Agent Routes (`routes/agent_routes.py`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/agents/runs` | Start a new root AgentRun |
| `GET` | `/api/agents/runs` | List runs for current user (filterable: `?status=&root_run_id=&from=&to=`) |
| `GET` | `/api/agents/runs/{run_id}` | Full detail of a single AgentRun |
| `GET` | `/api/agents/runs/{run_id}/stream` | SSE stream for run state transitions and sub-agent events |
| `POST` | `/api/agents/runs/{run_id}/pause` | Pause a root run |
| `POST` | `/api/agents/runs/{run_id}/resume` | Resume a paused run |
| `POST` | `/api/agents/runs/{run_id}/cancel` | Cancel a run |
| `DELETE` | `/api/agents/runs/{run_id}` | Delete a run (owner only) |

**POST /api/agents/runs — Request body:**
```json
{
  "session_id": "string",
  "task_description": "Research the top 5 Python ORMs and compare them",
  "persona_id": "string | null"
}
```

**GET /api/agents/runs/{run_id}/stream — SSE event schema:**
```
event: agent_run_event
data: {
  "run_id": "string",
  "root_run_id": "string",
  "parent_run_id": "string | null",
  "status": "created|running|completed|failed|paused|cancelled",
  "depth": 0,
  "task_description": "string",
  "result": "string | null",
  "error_detail": "string | null",
  "started_at": "ISO8601 | null",
  "ended_at": "ISO8601 | null"
}

event: agent_graph_snapshot
data: {
  "root_run_id": "string",
  "nodes": [
    {"run_id": "string", "parent_run_id": "string|null", "status": "string",
     "depth": 0, "task_description": "string", "elapsed_ms": 0}
  ]
}
```

### Persona Routes (`routes/persona_routes.py`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/personas` | List active personas for current user + built-ins |
| `POST` | `/api/personas` | Create new persona |
| `GET` | `/api/personas/{persona_id}` | Get single persona |
| `PUT` | `/api/personas/{persona_id}` | Update persona (user-owned only) |
| `DELETE` | `/api/personas/{persona_id}` | Soft-delete (user-owned only) |
| `POST` | `/api/sessions/{session_id}/persona` | Activate persona for a session |
| `DELETE` | `/api/sessions/{session_id}/persona` | Deactivate persona for a session |

**POST /api/personas — Request:**
```json
{
  "name": "Python Expert",
  "system_prompt": "You are a senior Python engineer...",
  "allowed_tools": ["run_code", "read_file"],
  "memory_scope": "persona:python-expert",
  "model_ref": "gpt-4o",
  "endpoint_url": "http://localhost:8080/v1"
}
```

**GET /api/personas — Response:**
```json
{
  "personas": [
    {
      "id": "string", "name": "string", "is_builtin": false,
      "system_prompt": "string", "allowed_tools": ["string"],
      "memory_scope": "string", "model_ref": "string|null",
      "endpoint_url": "string|null"
    }
  ]
}
```


### Plan Routes (`routes/plan_routes.py`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/plans` | Create plan from goal (LLM decomposition) |
| `GET` | `/api/plans` | List plans for current user |
| `GET` | `/api/plans/{plan_id}` | Full plan with steps |
| `PUT` | `/api/plans/{plan_id}` | Update plan metadata |
| `DELETE` | `/api/plans/{plan_id}` | Delete plan |
| `POST` | `/api/plans/{plan_id}/execute` | Start/resume sequential execution |
| `POST` | `/api/plans/{plan_id}/pause` | Pause plan execution |
| `POST` | `/api/plans/{plan_id}/cancel` | Cancel plan execution |
| `GET` | `/api/plans/{plan_id}/steps` | List all steps |
| `PUT` | `/api/plans/{plan_id}/steps/{step_id}` | Update step (title, description, status override) |
| `POST` | `/api/plans/{plan_id}/steps` | Add a new step |
| `DELETE` | `/api/plans/{plan_id}/steps/{step_id}` | Delete a step |

**POST /api/plans — Request:**
```json
{
  "goal": "Build a full FastAPI CRUD app with auth and tests",
  "model": "llama3",
  "endpoint_url": "http://localhost:11434/v1"
}
```

**POST /api/plans — Response:**
```json
{
  "plan_id": "string",
  "title": "string",
  "status": "pending",
  "steps": [
    {"id": "string", "order_index": 0, "title": "string",
     "description": "string", "status": "pending"}
  ]
}
```

### Critique Routes (`routes/critique_routes.py`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/critique/config` | Global critique config |
| `PUT` | `/api/critique/config` | Update global config |
| `GET` | `/api/sessions/{session_id}/critique` | Per-session critique config |
| `PUT` | `/api/sessions/{session_id}/critique` | Enable/disable + set critique model |
| `GET` | `/api/sessions/{session_id}/critique/history` | List CritiquePassRecords for session |
| `GET` | `/api/critique/records/{record_id}` | Full record including original draft |

**PUT /api/sessions/{session_id}/critique — Request:**
```json
{
  "enabled": true,
  "critique_model": "phi3",
  "critique_endpoint_url": "http://localhost:11434/v1"
}
```

**GET /api/critique/records/{record_id} — Response:**
```json
{
  "id": "string",
  "session_id": "string",
  "message_id": "string",
  "primary_model": "string",
  "critique_model": "string",
  "was_revised": true,
  "original_draft": "string",
  "revised_response": "string",
  "original_tokens": 120,
  "revised_tokens": 145,
  "created_at": "ISO8601"
}
```

### Reasoning Routes (`routes/reasoning_routes.py`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/sessions/{session_id}/reasoning` | List all traces for a session |
| `GET` | `/api/reasoning/traces/{trace_id}` | Full trace with nodes |
| `GET` | `/api/reasoning/by-message/{message_id}` | Trace for a specific message |
| `POST` | `/api/sessions/{session_id}/fork` | Fork session from a message or node |
| `GET` | `/api/sessions/{session_id}/fork-info` | Fork banner data (source session name, link) |

**POST /api/sessions/{session_id}/fork — Request:**
```json
{
  "source_message_id": "string",
  "source_node_id": "string | null"
}
```

**POST /api/sessions/{session_id}/fork — Response:**
```json
{
  "new_session_id": "string",
  "new_session_name": "[Fork] First 50 chars...",
  "source_session_id": "string",
  "source_message_id": "string"
}
```


---

## Frontend Architecture

All new UI code lives under `static/js/` as vanilla ES modules. No external JS libraries are introduced.

### New Files

```
static/js/
├── agent-graph.js         ← agent run DAG visualisation (SVG)
├── persona-switcher.js    ← dropdown in chat header
├── plan-tracker.js        ← plan progress sidebar widget
├── critique-toggle.js     ← per-session toggle + comparison panel
├── reasoning-trace.js     ← collapsible <think> content in chat
├── fork-controls.js       ← "Fork from here" buttons + banner
└── phase1-init.js         ← wires all modules, called from app.js
```

`static/app.js` gets one new import at the bottom:
```js
import { initPhase1 } from './js/phase1-init.js';
initPhase1();
```

### Agent Graph Visualisation — SVG choice

**SVG** is chosen over Canvas for the following reasons:
- Each node and edge is a DOM element — hover, click, and tooltip events are handled natively without manual hit-testing.
- Accessibility: SVG elements can carry `aria-label` attributes; Canvas cannot.
- No external library needed. D3 or Cytoscape are not present in the codebase; implementing a DAG layout in raw Canvas would require reimplementing all interaction primitives.
- The expected graph size is small (≤20 nodes in a typical run); SVG rendering is fast at this scale.

```js
// static/js/agent-graph.js
export class AgentGraph {
  constructor(container) {
    this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.svg.setAttribute("class", "agent-graph");
    container.appendChild(this.svg);
    this.nodes = new Map();   // run_id → {x, y, el}
    this.edges = new Map();   // `${parent}-${child}` → el
    this._evtSource = null;
  }

  connect(rootRunId) {
    this._evtSource = new EventSource(`/api/agents/runs/${rootRunId}/stream`);
    this._evtSource.addEventListener("agent_run_event", e => {
      this._handleRunEvent(JSON.parse(e.data));
    });
    this._evtSource.addEventListener("agent_graph_snapshot", e => {
      this._renderSnapshot(JSON.parse(e.data));
    });
  }

  _renderSnapshot({ nodes }) {
    this.svg.innerHTML = "";
    // Simple layered layout: group by depth, space horizontally
    const layers = {};
    for (const n of nodes) {
      (layers[n.depth] = layers[n.depth] || []).push(n);
    }
    const W = 160, H = 80, GAP_X = 40, GAP_Y = 60;
    for (const [depth, layerNodes] of Object.entries(layers)) {
      layerNodes.forEach((n, i) => {
        const x = i * (W + GAP_X) + 20;
        const y = depth * (H + GAP_Y) + 20;
        this._drawNode(n, x, y, W, H);
        if (n.parent_run_id) this._drawEdge(n.parent_run_id, n.run_id);
      });
    }
  }

  _drawNode(n, x, y, w, h) {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", `agent-node status-${n.status}`);
    g.setAttribute("aria-label", n.task_description);
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", x); rect.setAttribute("y", y);
    rect.setAttribute("width", w); rect.setAttribute("height", h);
    // Title text (truncated)
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", x + w / 2); text.setAttribute("y", y + h / 2);
    text.setAttribute("text-anchor", "middle");
    text.textContent = n.task_description.slice(0, 30) + (n.task_description.length > 30 ? "…" : "");
    g.appendChild(rect); g.appendChild(text);
    g.addEventListener("click", () => this._onNodeClick(n));
    this.svg.appendChild(g);
    this.nodes.set(n.run_id, { x, y, w, h });
  }
}
```


### Persona Switcher (chat header)

```js
// static/js/persona-switcher.js
export class PersonaSwitcher {
  constructor(sessionId, headerEl) {
    this.sessionId = sessionId;
    this.headerEl = headerEl;
    this._render();
  }

  async _render() {
    const { personas } = await fetch("/api/personas").then(r => r.json());
    const sel = document.createElement("select");
    sel.className = "persona-select";
    sel.innerHTML = `<option value="">— No Persona —</option>` +
      personas.map(p => `<option value="${p.id}">${p.name}${p.is_builtin ? " 🔒" : ""}</option>`).join("");
    sel.addEventListener("change", () => this._activate(sel.value));
    this.headerEl.querySelector(".persona-slot").replaceChildren(sel);
  }

  async _activate(personaId) {
    if (!personaId) {
      await fetch(`/api/sessions/${this.sessionId}/persona`, { method: "DELETE" });
    } else {
      await fetch(`/api/sessions/${this.sessionId}/persona`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona_id: personaId }),
      });
    }
  }
}
```

### Collapsible Reasoning Trace Component

The `reasoning-trace.js` module patches the existing message rendering. After a message is rendered, it checks for a trace:

```js
// static/js/reasoning-trace.js
export async function attachReasoningTrace(messageEl, messageDbId) {
  const res = await fetch(`/api/reasoning/by-message/${messageDbId}`);
  if (!res.ok) return;
  const trace = await res.json();
  if (!trace || !trace.nodes?.length) return;

  const details = document.createElement("details");
  details.className = "reasoning-trace";
  const summary = document.createElement("summary");
  summary.textContent = `🤔 Thinking (${trace.nodes.length} steps)`;
  details.appendChild(summary);

  trace.nodes.forEach((node, i) => {
    const div = document.createElement("div");
    div.className = "reasoning-node";
    div.dataset.index = node.index;
    div.dataset.chars = node.content.length;
    div.title = `Step ${node.index + 1} · ${node.content.length} chars`;
    div.textContent = node.content;
    details.appendChild(div);
  });

  // Insert before message text
  messageEl.insertBefore(details, messageEl.firstChild);
}

// Called during SSE streaming — appends nodes as they arrive
export function appendStreamingNode(traceContainer, nodeContent, index) {
  const div = document.createElement("div");
  div.className = "reasoning-node streaming";
  div.dataset.index = index;
  div.textContent = nodeContent;
  traceContainer.appendChild(div);
}
```

**Streaming approach**: During an active SSE response, the backend emits special events of type `thinking_node` before the `content` tokens arrive:

```
event: thinking_node
data: {"index": 0, "content": "Let me think about..."}

event: thinking_node
data: {"index": 1, "content": "Breaking it down..."}

event: content
data: {"token": "The answer is..."}
```

The existing `chat_routes.py` SSE generator is NOT modified. Instead, the trace extractor runs as a post-processing wrapper that buffers the stream, detects `<think>` blocks, and re-emits them as `thinking_node` events ahead of the cleaned content stream.

### Plan Progress Tracker

```js
// static/js/plan-tracker.js
export class PlanTracker {
  constructor(planId, containerEl) {
    this.planId = planId;
    this.containerEl = containerEl;
  }

  async refresh() {
    const plan = await fetch(`/api/plans/${this.planId}`).then(r => r.json());
    const done = plan.steps.filter(s => s.status === "done").length;
    const total = plan.steps.length;
    const current = plan.steps.find(s => s.status === "running");
    this.containerEl.innerHTML = `
      <div class="plan-progress">
        <span class="plan-title">${plan.title}</span>
        <progress value="${done}" max="${total}"></progress>
        <span>${done}/${total} steps</span>
        ${current ? `<span class="plan-current">▶ ${current.title}</span>` : ""}
      </div>
    `;
  }
}
```

### Critique Toggle + Comparison Panel

```js
// static/js/critique-toggle.js
export class CritiqueToggle {
  constructor(sessionId, headerEl) {
    this.sessionId = sessionId;
    this.toggle = headerEl.querySelector(".critique-toggle");
    this.toggle.addEventListener("change", () => this._onChange());
    this._syncState();
  }

  async _onChange() {
    const enabled = this.toggle.checked;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    try {
      await fetch(`/api/sessions/${this.sessionId}/critique`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
        signal: controller.signal,
      });
    } catch {
      // Req 8.4: revert toggle and show error
      this.toggle.checked = !enabled;
      showToast("Failed to update critique setting", "error");
    } finally {
      clearTimeout(timeout);
    }
  }
}

export function attachCritiqueComparison(messageEl, recordId) {
  // Fetches original_draft vs revised_response and renders side-by-side
  const badge = document.createElement("span");
  badge.className = "critiqued-badge";
  badge.textContent = "✓ Critiqued";
  badge.addEventListener("click", () => _showComparison(messageEl, recordId));
  messageEl.querySelector(".message-meta").appendChild(badge);
}
```


---

## Key Algorithms

### Sub-Agent Spawning and Depth Enforcement

The LLM signals sub-agent delegation via a dedicated tool call:

```json
{
  "tool_name": "delegate_to_subagent",
  "arguments": {
    "task": "Extract all Python function signatures from the uploaded code",
    "persona_id": null
  }
}
```

The orchestrator intercepts this tool name in `_agent_loop_with_hooks` **before** appending it to the message list. Depth is enforced at spawn time:

```python
def _check_depth(parent_run: AgentRun):
    if parent_run.depth + 1 > Orchestrator.MAX_DEPTH:
        # Return a synthetic error tool response instead of spawning
        return {"role": "tool", "content": f"[ERROR] Max agent depth {Orchestrator.MAX_DEPTH} reached. Cannot spawn sub-agent."}
    return None  # OK to proceed
```

`root_run_id` is denormalised on every `AgentRun` at creation time (copied from parent's `root_run_id`, or set to `self.id` for root runs). This makes subtree queries `O(1)` index scans without recursive CTEs.

### Graceful Pause / Cancel

**Pause**: Uses `asyncio.Event` per run. The main execution loop calls `await _check_pause(run_id)` after every tool response or LLM chunk. When pause is requested, the event is `.set()`; `_check_pause` detects it and blocks on `event.wait()` with the event cleared again. Resume clears the event, unblocking all waiting coroutines.

**Cancel**: A simple `dict[run_id, bool]` flag. The cancel check is a non-blocking `if self._cancel_flags.get(run_id)` after every iteration — fire-and-forget, no await needed. Cancel propagates immediately to all tree members because each has its own flag set by `cancel_run`.

**Why not asyncio.CancelledError?** Task cancellation in asyncio can leave DB state inconsistent if the task is cancelled mid-write. Using explicit flags ensures DB cleanup (status update to `cancelled`) always runs in the normal code path.

### `<think>` Tag Extraction from SSE Stream

The tag extractor wraps the existing streaming generator in `src/agent_loop.py`. The wrapper accumulates tokens until a complete `</think>` is seen, then flushes the thinking content as `thinking_node` events, then forwards the cleaned tokens as `content` events:

```python
async def reasoning_aware_stream(base_generator):
    buf = ""
    think_buf = ""
    in_think = False
    node_index = 0

    async for chunk in base_generator:
        if chunk.get("type") != "content":
            yield chunk
            continue
        token = chunk.get("token", "")
        buf += token

        while True:
            if not in_think:
                open_pos = buf.find("<think>")
                if open_pos == -1:
                    # No open tag yet — emit everything up to last 7 chars (could be partial tag)
                    safe = buf[:-7] if len(buf) > 7 else ""
                    if safe:
                        yield {"type": "content", "token": safe}
                        buf = buf[len(safe):]
                    break
                else:
                    # Emit before the <think> tag
                    if open_pos > 0:
                        yield {"type": "content", "token": buf[:open_pos]}
                    buf = buf[open_pos + 7:]   # skip <think>
                    in_think = True
            else:
                close_pos = buf.find("</think>")
                if close_pos == -1:
                    # Accumulate in think buffer
                    if len(buf) > 8:
                        think_buf += buf[:-8]
                        buf = buf[-8:]
                    break
                else:
                    think_buf += buf[:close_pos]
                    yield {"type": "thinking_node", "index": node_index, "content": think_buf.strip()}
                    node_index += 1
                    buf = buf[close_pos + 8:]   # skip </think>
                    think_buf = ""
                    in_think = False

    # Flush remaining clean text
    if buf and not in_think:
        yield {"type": "content", "token": buf}
```

### Self-Critique Pipeline

```
User question
     │
     ▼
Primary LLM call  ──────────► draft response
                                    │
                          is_enabled_for_session?
                            No ─────► return draft to user
                            Yes
                             │
                             ▼
                      Critique model call (30s timeout)
                             │
                     ┌───────┴────────┐
                  Success           Error/Timeout
                     │                    │
              was_revised?          return draft (fallback)
               Yes  │  No                 log error
                    │   │
              return    return
             revised    draft
```

The critique record is written in both success and failure paths. The `error_detail` column distinguishes the fallback case.

### Plan Step Sequencing and Resumption

```
Plan status: pending → running → [paused_on_failure | completed | cancelled]

Step execution loop:
  for step in plan.steps (ordered by order_index):
    if step.status == "done" or "skipped":
        continue   ← resumption: skip completed steps
    if step.status == "failed" and retry_count < MAX_RETRIES:
        step.retry_count += 1
        run step again
    elif step.status == "failed":
        plan.status = "paused_on_failure"
        notify user
        return   ← halt; user must resolve or skip
    else (step.status == "pending" or "running"):
        execute step
```

Resumption is handled by the same loop — `resume` simply re-calls `execute()`. The loop skips any step with `status == "done"` or `"skipped"`, so it naturally restarts from the correct position.

Persistence of checkpoint state: after every step status update, the `PlanStep.status` and `Plan.current_step_index` are committed to the DB. If the server restarts mid-step, the step will be in `running` state; on resume, the executor treats `running` the same as `pending` (idempotent retry).


---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Agent Tree Depth Invariant

*For any* sequence of sub-agent spawn operations rooted at a single `AgentRun`, the `depth` field of every node in the resulting tree must be strictly less than or equal to `MAX_DEPTH`. Equivalently, no `AgentRun` in the database should ever have `depth > MAX_DEPTH`.

**Validates: Requirements 1.7, 1.8**

### Property 2: Agent Run Parent Linkage Invariant

*For any* child `AgentRun` record (i.e., one with a non-null `parent_run_id`), the `parent_run_id` must reference an existing `AgentRun` record, and the child's `depth` must equal the parent's `depth + 1`.

**Validates: Requirements 1.2**

### Property 3: Persona Name Uniqueness and Length Invariant

*For any* user, no two active `Persona` records owned by that user should have the same `name`. Additionally, for any `Persona` that was successfully persisted, its `name` must have length between 1 and 64 characters (inclusive).

**Validates: Requirements 3.5**

### Property 4: Persona Update Non-Interference

*For any* `Persona` that is updated while one or more `Session` records reference it via `active_persona_id`, the `active_persona_id` reference on existing sessions is preserved unchanged — i.e., updating a persona does not alter any session's `active_persona_id` column.

**Validates: Requirements 3.3**

### Property 5: Plan Step Count Bounds

*For any* successfully created `Plan`, the number of associated `PlanStep` records must satisfy `2 ≤ count ≤ 50`.

**Validates: Requirements 5.3**

### Property 6: Plan Step Ordering Invariant

*For any* `Plan`, the `order_index` values across all its `PlanStep` records must form a strictly monotonically increasing sequence starting at 0 with no gaps or duplicates.

**Validates: Requirements 5.2**

### Property 7: Plan Resumption Skips Completed Steps

*For any* `Plan` that has been partially executed (some steps `done`, some `pending`), invoking `execute()` must not re-execute any step that already has `status == "done"` — the executor must advance to the first non-done step.

**Validates: Requirements 6.4**

### Property 8: Critique Fallback Preserves Draft

*For any* draft response string `d` and any simulated failure of the critique model, the value returned by `CritiqueService.critique()` must equal `d` unchanged.

**Validates: Requirements 7.9**

### Property 9: Think Tag Extraction Round-Trip

*For any* text containing one or more `<think>...</think>` blocks, `extract_thinking(text)` must return the clean text (with think blocks removed) and a list of segments whose concatenation equals the concatenated think block contents. Equivalently: `clean + "".join(segments) == text` modulo whitespace from tag removal.

**Validates: Requirements 9.1**

### Property 10: Reasoning Node Uniqueness and Sequential Indexing

*For any* `ReasoningTrace`, all `ReasoningNode` records belonging to that trace must have unique `id` values and their `index` values must form a sequence `0, 1, 2, …, n-1` with no duplicates or gaps.

**Validates: Requirements 9.2**

### Property 11: Fork History Prefix

*For any* fork operation on session S at message M (where M is the k-th message in S's history), the resulting forked session F must have a `history` list that is exactly the first k messages of S's history — a prefix with no additions, deletions, or reorderings.

**Validates: Requirements 11.1, 11.2**

### Property 12: Fork Session Name Truncation

*For any* source content string of arbitrary length, the name of the forked session must equal `"[Fork] " + content[:50]`. For strings shorter than 50 characters, the full string is used with no trailing space or truncation marker.

**Validates: Requirements 11.3**


---

## Error Handling and Fallbacks

### CritiquePass Failure

Three failure modes are handled:

| Failure | Behaviour |
|---|---|
| Critique model unavailable (connection error) | Return original draft; log error; write `CritiquePassRecord.error_detail` |
| Critique model returns malformed response | Return original draft; log with response snippet |
| `asyncio.TimeoutError` after 30s | Return original draft; log timeout; write `CritiquePassRecord.error_detail = "timeout"` |

The UI will not display the "Critiqued" badge when `was_revised == False`. A separate `error_detail` field distinguishes "model agreed with draft" from "critique failed".

### Sub-Agent Failure Propagation

When a sub-agent marks itself `failed`:

1. `_propagate_failure_to_parent(run)` is called — it sets `parent_run.error_detail` to include the child's `error_detail`.
2. The parent's tool response for the `delegate_to_subagent` call is set to `"[SUBAGENT FAILED] <error>"`.
3. The parent LLM loop continues — it can decide to retry (by issuing another `delegate_to_subagent`), skip, or abort. This keeps the decision in the LLM's hands.
4. If the parent also fails, propagation continues up the tree.
5. An `agent_run_event` SSE event with `status: "failed"` is emitted for each failed node, so the UI graph turns the node red.

### Plan Step Retry Logic

```
MAX_RETRIES = int(os.getenv("PLAN_STEP_MAX_RETRIES", "2"))

on step failure:
  step.retry_count += 1
  if step.retry_count < MAX_RETRIES:
      log warning, reset status to "pending", retry immediately
  else:
      step.status = "failed"
      plan.status = "paused_on_failure"
      emit notification to owner
      halt execution loop
```

The user can then manually fix the step's description, reset its status to `pending`, and call `POST /api/plans/{plan_id}/execute` again.

### AgentRun Record Retention

A background scheduled task (registered with the existing `TaskScheduler`) runs daily:

```python
async def prune_agent_runs():
    retention_days = int(os.getenv("AGENT_RUN_RETENTION_DAYS", "90"))
    cutoff = utcnow_naive() - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        # Find root runs past retention; cascading delete removes children
        expired = db.query(AgentRun)\
                    .filter(AgentRun.parent_run_id == None)\
                    .filter(AgentRun.created_at < cutoff)\
                    .all()
        for run in expired:
            db.delete(run)
        db.commit()
    finally:
        db.close()
```

---

## Backward Compatibility

### Schema Changes

All changes are purely additive:
- 7 new tables (`CREATE TABLE IF NOT EXISTS` — no-op on fresh databases, no-op on re-runs).
- 3 new nullable columns on `sessions` (`ALTER TABLE ADD COLUMN IF NOT EXISTS` — idempotent; nullable with no default means all existing rows are unaffected).
- No existing columns are dropped, renamed, or type-changed.

### Existing Routes

`routes/chat_routes.py` and `routes/session_routes.py` are not modified. Phase 1 hooks into the chat flow via:
1. A wrapper around `stream_agent_loop` in `routes/chat_helpers.py` (the reasoning trace extractor and the critique call are both in this wrapper).
2. The wrapper is activated only when the session has `active_persona_id` set or critique is enabled — otherwise it is a zero-cost passthrough.

### Existing Sessions

Sessions created before Phase 1 have `active_persona_id = NULL`. The persona activation path checks for NULL and skips injection entirely, preserving existing behaviour.

### Startup Latency

All five service managers (`PersonaManager`, `Orchestrator`, `PlanExecutor`, `CritiqueService`, `TraceStore`) are instantiated lazily via module-level singletons with no I/O at import time. The only startup I/O is:
- `PersonaManager.seed_builtins()` — 3 `SELECT` + up to 3 `INSERT` on an indexed table. Expected < 10ms.
- `run_phase1_migrations()` — 3 `ALTER TABLE` statements (no-ops after first run). Expected < 5ms.

Both are called in the existing lifespan handler after `create_all`.

### Tool Policy Interaction

When a Persona is active, `allowed_tools` is applied as an **additional filter** on top of the existing MCP tool policy:

```python
def effective_tools_for_session(session_id: str, base_policy: ToolPolicy) -> ToolPolicy:
    persona = _get_active_persona(session_id)
    if persona is None or persona.allowed_tools is None:
        return base_policy
    allowed = set(json.loads(persona.allowed_tools))
    # Persona can only RESTRICT, never EXPAND, what the base policy allows
    return base_policy.intersect(allowed)
```

This ensures Personas cannot bypass existing MCP security controls (Req 13.6).


---

## Testing Strategy

### Dual Testing Approach

Unit tests cover specific examples and edge cases. Property-based tests (using [Hypothesis](https://hypothesis.readthedocs.io/)) validate universal correctness properties across many generated inputs. Both are complementary: unit tests catch concrete regressions; property tests find edge cases that specific examples miss.

**Framework:** Python `pytest` + `hypothesis` for property tests. Tests live in `tests/phase1/`.

### Property-Based Test Configuration

Each property test is configured to run a minimum of 100 examples (Hypothesis default). Tests are tagged with a comment referencing the design document property:

```python
# Feature: phase-1-intelligence-reasoning, Property 9: Think tag extraction round-trip
@given(st.lists(st.text(), min_size=1, max_size=5))
@settings(max_examples=200)
def test_think_tag_extraction_round_trip(segments):
    # Construct a text with <think> blocks
    text = " ".join(f"<think>{s}</think>" for s in segments)
    clean, found = extract_thinking(text)
    assert "".join(found) == "".join(s for s in segments if s.strip())
```

### Property Tests

**Property 1 & 2 — Agent Tree Invariants**
```python
# Feature: phase-1-intelligence-reasoning, Property 1 & 2: Agent tree depth and parent linkage
@given(st.integers(min_value=0, max_value=5))
def test_spawn_depth_never_exceeds_max(depth_attempts):
    runs = simulate_spawn_chain(depth_attempts)
    assert all(r.depth <= MAX_DEPTH for r in runs)
    for r in runs:
        if r.parent_run_id:
            parent = next(p for p in runs if p.id == r.parent_run_id)
            assert r.depth == parent.depth + 1
```

**Property 3 — Persona Name Uniqueness and Length**
```python
# Feature: phase-1-intelligence-reasoning, Property 3: Persona name uniqueness and length
@given(st.text(min_size=0, max_size=100))
def test_persona_name_validation(name):
    pm = PersonaManager()
    if 1 <= len(name) <= 64:
        p = pm.create("testuser", name, system_prompt="x", memory_scope="session")
        assert p.name == name
        with pytest.raises(ValueError):
            pm.create("testuser", name, system_prompt="y", memory_scope="session")
    else:
        with pytest.raises(ValueError):
            pm.create("testuser", name, system_prompt="x", memory_scope="session")
```

**Property 5 & 6 — Plan Step Count and Ordering**
```python
# Feature: phase-1-intelligence-reasoning, Property 5 & 6: Plan step count bounds and ordering
@given(st.lists(plan_step_strategy(), min_size=1, max_size=60))
def test_plan_step_invariants(steps_input):
    # Mock LLM returns steps_input
    plan = create_plan_with_steps(steps_input)
    assert 2 <= len(plan.steps) <= 50
    indices = [s.order_index for s in plan.steps]
    assert indices == list(range(len(indices)))
```

**Property 8 — Critique Fallback**
```python
# Feature: phase-1-intelligence-reasoning, Property 8: Critique fallback preserves draft
@given(st.text(min_size=1))
@settings(max_examples=100)
async def test_critique_fallback_returns_draft(draft):
    service = CritiqueService(critique_llm=failing_mock_llm)
    result = await service.critique("sess1", "msg1", "question", draft, "m1", "ep", {}, "user")
    assert result == draft
```

**Property 9 — Think Tag Extraction Round-Trip**
```python
# Feature: phase-1-intelligence-reasoning, Property 9: Think tag extraction round-trip
@given(st.lists(st.text(min_size=0), min_size=1, max_size=10))
@settings(max_examples=500)
def test_think_extraction_round_trip(segments):
    text = "".join(f"<think>{s}</think>" for s in segments)
    clean, found = extract_thinking(text)
    assert clean.strip() == ""  # only think content, no other text
    assert [f.strip() for f in found] == [s.strip() for s in segments]
```

**Properties 10, 11, 12 — Node indexing, fork prefix, fork name**
```python
# Feature: phase-1-intelligence-reasoning, Property 10: Reasoning node sequential indexing
@given(st.lists(st.text(min_size=1), min_size=1, max_size=20))
def test_reasoning_node_indices_are_sequential(segments):
    trace = trace_store.persist("s1", "m1", "user", "model", segments)
    indices = sorted(n.index for n in trace.nodes)
    assert indices == list(range(len(segments)))

# Feature: phase-1-intelligence-reasoning, Property 11: Fork history is a prefix
@given(session_with_messages_strategy(), st.integers(min_value=1))
def test_fork_history_is_prefix(session, fork_at):
    fork_at = min(fork_at, len(session.history))
    forked = fork_session(session.id, session.history[fork_at - 1].id)
    assert len(forked.history) == fork_at
    assert forked.history == session.history[:fork_at]

# Feature: phase-1-intelligence-reasoning, Property 12: Fork session name truncation
@given(st.text(min_size=0, max_size=200))
def test_fork_session_name(content):
    name = build_fork_session_name(content)
    assert name == "[Fork] " + content[:50]
```

### Unit Tests

- **`test_orchestrator.py`**: Spawn chains, pause/cancel state transitions, error propagation
- **`test_persona_manager.py`**: CRUD, built-in seeding, per-user limits, update non-interference
- **`test_plan_executor.py`**: Sequential execution, resumption from mid-plan, retry exhaustion
- **`test_critique_service.py`**: Full pipeline, timeout fallback, no-revision passthrough
- **`test_trace_extractor.py`**: Multi-block extraction, streaming partial tags, empty input

### Integration Tests

- Migration idempotency: apply `run_phase1_migrations()` twice, verify no errors
- Session backward compatibility: create sessions without Phase 1 features active, verify chat behaves identically
- Auth boundary: verify 403/404 on cross-user AgentRun/Plan/Persona access

