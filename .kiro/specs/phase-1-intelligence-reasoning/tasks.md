# Implementation Plan: Phase 1 — Intelligence & Reasoning

## Overview

This plan implements the five Phase 1 capabilities for Odysseus in dependency order:
database schema and migrations first, then backend services, then API routes, then
frontend modules, with tests co-located under each feature area.

All code targets Python 3.11+ (backend) and vanilla ES modules with no build step (frontend).
Property-based tests use `pytest` + `hypothesis`. New files go in the locations defined by the design document; no existing route handlers in `chat_routes.py` or `session_routes.py` are modified.

---

## Tasks

- [x] 1. Database schema — new models and startup migrations
  - [x] 1.1 Add Phase 1 SQLAlchemy models to `core/database.py`
    - Add `AgentRun`, `Persona`, `Plan`, `PlanStep`, `CritiquePassRecord`, `ReasoningTrace`, `ReasoningNode` classes following the `TimestampMixin` pattern
    - Add `forked_from_session_id`, `forked_from_message_id`, `active_persona_id` columns to the existing `Session` model
    - Use `String` PKs (UUID strings), `ForeignKey` with appropriate `ondelete` actions, and composite indexes as specified in the design
    - _Requirements: 1.2, 3.1, 5.1, 5.2, 6.3, 7.6, 8.6, 9.3, 9.5, 11.4, 12.1_

  - [x] 1.2 Create `core/phase1_migrations.py`
    - Implement `run_phase1_migrations(engine)` with idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` calls for the three new `sessions` columns
    - Implement `_add_col_if_missing(conn, table, column, col_type)` helper that swallows the "column already exists" exception
    - _Requirements: 13.1, 13.4_

  - [x] 1.3 Wire migrations and model creation into `app.py` lifespan
    - Import and call `run_phase1_migrations(engine)` in the lifespan handler, before the existing `Base.metadata.create_all(engine)` call
    - _Requirements: 13.1, 13.4_

  - [x]* 1.4 Write integration test for migration idempotency
    - In `tests/phase1/test_migrations.py`, call `run_phase1_migrations()` twice on an in-memory SQLite DB and assert no exception is raised and all columns exist after both calls
    - _Requirements: 13.1_

- [x] 2. Feature area 1 — Multi-Agent Orchestration
  - [x] 2.1 Create `services/orchestration/__init__.py` and `services/orchestration/run_store.py`
    - `run_store.py`: DB helper functions — `create_agent_run`, `update_run_status`, `get_run`, `list_runs_for_owner`, `get_subtree`, `bulk_update_status`, `prune_expired_runs`
    - All helpers use `SessionLocal` directly; no ORM session is passed in from outside
    - _Requirements: 1.2, 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 2.2 Create `services/orchestration/orchestrator.py`
    - Implement `Orchestrator` class with `MAX_DEPTH` env config (default 3)
    - `start_run(task, owner, persona_id, parent_run_id, depth)` — creates `AgentRun` record, spawns `asyncio.Task` for `_execute_run`
    - `_execute_run` — calls `stream_agent_loop` via `_agent_loop_with_hooks`, emits SSE events, checks pause/cancel flags after each chunk
    - `_agent_loop_with_hooks` — intercepts `delegate_to_subagent` tool calls, enforces depth limit, awaits sub-run result and injects as tool response
    - `_check_pause(run_id)` — blocks while pause event is set; no-op otherwise
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [x] 2.3 Create `services/orchestration/oversight.py`
    - `pause_run(root_run_id)`, `resume_run(root_run_id)`, `cancel_run(root_run_id)`
    - Pause/resume use per-run `asyncio.Event` stored on the orchestrator singleton; cancel uses a `dict[run_id, bool]` flag
    - `cancel_run` sets flags and bulk-updates all tree records to `cancelled` synchronously
    - _Requirements: 2.3, 2.4, 2.5_

  - [x]* 2.4 Write property test for agent tree depth invariant
    - In `tests/phase1/test_orchestrator.py`
    - **Property 1: Agent Tree Depth Invariant**
    - **Property 2: Agent Run Parent Linkage Invariant**
    - **Validates: Requirements 1.7, 1.8, 1.2**

  - [x]* 2.5 Write unit tests for orchestrator pause/cancel/error propagation
    - Test pause → resume state cycle; test cancel sets all tree nodes to `cancelled`; test sub-agent failure propagates `error_detail` to parent
    - _Requirements: 1.6, 2.3, 2.4, 2.5_


- [x] 3. Feature area 2 — Agent Personas / Roles
  - [x] 3.1 Create `services/personas/__init__.py` and `services/personas/persona_manager.py`
    - Define `BUILTIN_PERSONAS` list with "Code Reviewer", "Legal Analyst", "Personal Trainer" entries (matching design)
    - `PersonaManager.seed_builtins()` — idempotent upsert of built-ins at startup
    - `create(owner, name, **kwargs)` — enforces per-user limit (default 50), name length 1–64, uniqueness; raises `PersonaLimitError` or `ValueError` on violation
    - `update(persona_id, owner, **kwargs)` — updates mutable fields; does not touch any `Session.active_persona_id` reference
    - `delete(persona_id, owner)` — soft-delete (`is_active = False`); preserves `AgentRun` references
    - `list_for_user(owner)` — returns active personas owned by user plus all built-ins, sorted alphabetically
    - `activate_for_session(session_id, persona_id)` — stamps `Session.active_persona_id`; deactivate sets it to NULL
    - `effective_tools_for_session(session_id, base_policy)` — returns `base_policy.intersect(allowed_tools)` when persona is active
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 13.6_

  - [x]* 3.2 Write property tests for persona name validation
    - In `tests/phase1/test_persona_manager.py`
    - **Property 3: Persona Name Uniqueness and Length Invariant**
    - **Property 4: Persona Update Non-Interference**
    - **Validates: Requirements 3.5, 3.3**

  - [x]* 3.3 Write unit tests for persona CRUD and activation
    - Test built-in seeding idempotency; test per-user limit enforcement; test activation stamps session column; test deactivation clears it; test built-in cannot be modified or deleted by user
    - _Requirements: 3.2, 3.4, 3.6, 3.7, 3.8, 4.1, 4.6_

- [x] 4. Feature area 3 — Long-Horizon Planning
  - [x] 4.1 Create `services/planning/__init__.py` and `services/planning/planner.py`
    - `decompose_goal(goal, endpoint_url, model, headers)` — calls `llm_call_async` with the structured JSON decomposition prompt; parses response; validates `2 ≤ len(steps) ≤ 50`; raises `ValueError` on out-of-range counts
    - `create_plan(owner, goal, endpoint_url, model)` — calls `decompose_goal`, persists `Plan` + `PlanStep` records in a single transaction; assigns `order_index` starting at 0; returns the new `Plan`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.2 Create `services/planning/executor.py`
    - `PlanExecutor.execute(plan_id, owner)` — sequential step loop; skips `done`/`skipped` steps; retries failed steps up to `PLAN_STEP_MAX_RETRIES` (default 2) before setting plan to `paused_on_failure`
    - `_execute_step(plan, step, owner)` — creates or reuses a session via `session_manager.ensure_task_session`; runs agent loop; persists step output; updates step status
    - `pause(plan_id)`, `cancel(plan_id)` — set in-memory flags checked at loop head
    - On all-steps-done: sets plan status to `completed`; emits user notification
    - Persist `Plan.current_step_index` and `PlanStep.status` after every step transition for crash-safe resumption
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x]* 4.3 Write property tests for plan step invariants
    - In `tests/phase1/test_plan_executor.py`
    - **Property 5: Plan Step Count Bounds**
    - **Property 6: Plan Step Ordering Invariant**
    - **Property 7: Plan Resumption Skips Completed Steps**
    - **Validates: Requirements 5.3, 5.2, 6.4**

  - [x]* 4.4 Write unit tests for plan execution edge cases
    - Test resumption from mid-plan (some steps `done`); test retry exhaustion transitions plan to `paused_on_failure`; test manual `done`/`skipped` override; test cancel halts loop
    - _Requirements: 6.3, 6.4, 6.5, 6.7_


- [x] 5. Feature area 4 — Self-Critique Loops
  - [x] 5.1 Create `services/critique/__init__.py` and `services/critique/critique_service.py`
    - `CritiqueService.is_enabled_for_session(session_id)` — queries a lightweight `SessionCritiqueConfig` in-memory dict (or a small table); falls back to global setting
    - `CritiqueService.set_enabled(session_id, enabled, critique_model, critique_endpoint_url)` — persists per-session config; returns within 1 second
    - `CritiqueService.critique(session_id, message_id, user_question, draft, primary_model, endpoint_url, headers, owner)` — calls critique model with 30-second `asyncio.wait_for` timeout; writes `CritiquePassRecord`; falls back to returning `draft` unchanged on any exception or timeout
    - `_resolve_critique_model(session_id, primary_model, endpoint_url)` — returns per-session override if set, else falls back to primary model/endpoint
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.6_

  - [x] 5.2 Add critique hook to `routes/chat_helpers.py`
    - Add `maybe_apply_critique(session_id, message_id, user_q, draft, sess, owner) -> str` function
    - Call it after `save_assistant_response()` only when `critique_service.is_enabled_for_session(session_id)` is true; return revised or original draft
    - This is the ONLY modification to `chat_helpers.py`; `chat_routes.py` is not touched
    - _Requirements: 7.2, 13.2, 13.5_

  - [x]* 5.3 Write property test for critique fallback
    - In `tests/phase1/test_critique_service.py`
    - **Property 8: Critique Fallback Preserves Draft**
    - **Validates: Requirements 7.9**

  - [x]* 5.4 Write unit tests for critique pipeline
    - Test full pipeline (was_revised=True); test no-revision passthrough (was_revised=False); test 30-second timeout falls back to draft; test `CritiquePassRecord` metadata fields are persisted in all paths
    - _Requirements: 7.3, 7.4, 7.8, 7.9, 8.6_

- [x] 6. Feature area 5 — Reasoning Traces
  - [x] 6.1 Create `services/reasoning/__init__.py` and `services/reasoning/trace_extractor.py`
    - `extract_thinking(text)` — regex-based extraction of all `<think>…</think>` blocks; returns `(clean_text, list_of_segments)`
    - `extract_thinking_streaming(accumulated)` — variant for SSE streaming that detects complete close tags; returns `(clean_so_far, segments_found, has_open_think)`
    - `reasoning_aware_stream(base_generator)` — async generator wrapper that buffers tokens, emits `thinking_node` SSE events before forwarding cleaned `content` events
    - _Requirements: 9.1, 10.5_

  - [x] 6.2 Create `services/reasoning/trace_store.py`
    - `TraceStore.persist(session_id, message_id, owner, model, segments)` — writes `ReasoningTrace` + N `ReasoningNode` records in one transaction; returns `None` if `segments` is empty
    - `TraceStore.get_for_message(message_id)` — returns `ReasoningTrace` with eagerly loaded `nodes`, or `None`
    - `TraceStore.list_for_session(session_id)` — returns all traces for a session without node content (list view)
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x]* 6.3 Write property tests for trace extraction and node indexing
    - In `tests/phase1/test_trace_extractor.py`
    - **Property 9: Think Tag Extraction Round-Trip**
    - **Property 10: Reasoning Node Uniqueness and Sequential Indexing**
    - **Validates: Requirements 9.1, 9.2**

  - [x]* 6.4 Write unit tests for trace edge cases
    - Test multi-block extraction; test streaming partial `<think>` tag (no close tag yet); test empty input returns empty segments; test session delete cascades to traces and nodes
    - _Requirements: 9.1, 9.2, 9.6_


- [x] 7. Checkpoint — Backend services complete
  - Ensure all tests in `tests/phase1/` pass, ask the user if questions arise.

- [x] 8. API Routes
  - [x] 8.1 Create `routes/agent_routes.py`
    - `POST /api/agents/runs` — validate request body, call `orchestrator.start_run()`, return the new `AgentRun` as JSON
    - `GET /api/agents/runs` — query `run_store.list_runs_for_owner()` with optional `status`, `root_run_id`, `from`, `to` filters; enforce owner via `get_current_user()`
    - `GET /api/agents/runs/{run_id}` — return full record including child run IDs; 403 if not owner, 404 if not found
    - `GET /api/agents/runs/{run_id}/stream` — `StreamingResponse` with `text/event-stream`; emits `agent_run_event` and `agent_graph_snapshot` events; subscribes to the orchestrator's per-run event queue
    - `POST /api/agents/runs/{run_id}/pause`, `/resume`, `/cancel` — call corresponding `oversight` functions; ownership checked before dispatch
    - `DELETE /api/agents/runs/{run_id}` — owner-only hard delete; cascades to children via FK
    - Register router in `app.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 12.1, 12.2, 12.3, 12.4, 12.6_

  - [x] 8.2 Create `routes/persona_routes.py`
    - `GET /api/personas` — returns active user personas + built-ins sorted alphabetically
    - `POST /api/personas` — calls `persona_manager.create()`; returns new persona with assigned ID within 2 seconds
    - `GET /api/personas/{persona_id}` — ownership check; 404 for built-ins owned by others is not applicable (built-ins are readable by all)
    - `PUT /api/personas/{persona_id}` — user-owned only; built-ins return 403
    - `DELETE /api/personas/{persona_id}` — user-owned only; soft-delete
    - `POST /api/sessions/{session_id}/persona` — activate; verifies session ownership via `_verify_session_owner`
    - `DELETE /api/sessions/{session_id}/persona` — deactivate
    - Register router in `app.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.5, 4.6, 4.7_

  - [x] 8.3 Create `routes/plan_routes.py`
    - `POST /api/plans` — calls `planner.create_plan()`; returns plan + steps; associates plan with requesting user
    - `GET /api/plans` — list user's plans with title, step counts, current status; owner filtering enforced
    - `GET /api/plans/{plan_id}` — full plan with all steps; 404/403 guards
    - `PUT /api/plans/{plan_id}` — update plan metadata
    - `DELETE /api/plans/{plan_id}` — owner only
    - `POST /api/plans/{plan_id}/execute` — calls `plan_executor.execute()` in a background task; returns 202
    - `POST /api/plans/{plan_id}/pause`, `/cancel`
    - `GET /api/plans/{plan_id}/steps`, `POST`, step `PUT`/`DELETE` — step CRUD with running-step guard on delete
    - Register router in `app.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.4, 6.6, 6.7_

  - [x] 8.4 Create `routes/critique_routes.py`
    - `GET /api/critique/config`, `PUT /api/critique/config` — global enabled flag + default critique model
    - `GET /api/sessions/{session_id}/critique`, `PUT /api/sessions/{session_id}/critique` — per-session config; PUT must acknowledge within 1 second; session ownership check
    - `GET /api/sessions/{session_id}/critique/history` — list `CritiquePassRecord`s for session (no `original_draft` in list view)
    - `GET /api/critique/records/{record_id}` — full record including `original_draft` and `revised_response`; owner check
    - Register router in `app.py`
    - _Requirements: 7.1, 7.6, 8.1, 8.3, 8.4, 8.6_

  - [x] 8.5 Create `routes/reasoning_routes.py`
    - `GET /api/sessions/{session_id}/reasoning` — list traces for session (no node content); session ownership check
    - `GET /api/reasoning/traces/{trace_id}` — full trace with nodes; owner check
    - `GET /api/reasoning/by-message/{message_id}` — trace for a specific message; owner inferred from session
    - `POST /api/sessions/{session_id}/fork` — validates `source_message_id`; creates new session with history prefix; sets `forked_from_session_id` and `forked_from_message_id`; sets session name to `"[Fork] " + content[:50]`; applies same ownership as requesting user
    - `GET /api/sessions/{session_id}/fork-info` — returns source session name and ID for the fork banner; returns `null` if session is not a fork
    - Register router in `app.py`
    - _Requirements: 9.4, 10.1, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [x]* 8.6 Write unit tests for route auth boundaries
    - In `tests/phase1/` — verify 403 is returned when a user requests another user's AgentRun, Plan, and Persona; verify 404 when resource doesn't exist; verify 401 when unauthenticated
    - _Requirements: 5.5, 12.6_


- [x] 9. Checkpoint — Routes complete
  - Ensure all tests pass and `app.py` starts without import errors, ask the user if questions arise.

- [x] 10. Frontend — Phase 1 JS modules
  - [x] 10.1 Create `static/js/reasoning-trace.js`
    - `attachReasoningTrace(messageEl, messageDbId)` — fetches `/api/reasoning/by-message/{id}`; if trace exists, inserts a `<details class="reasoning-trace">` element with a `<summary>` showing node count, before the message text
    - Each `ReasoningNode` rendered as a `<div class="reasoning-node">` with `title` tooltip showing step index and character count
    - `appendStreamingNode(traceContainer, nodeContent, index)` — appends a node div during active SSE streaming
    - _Requirements: 10.1, 10.2, 10.3, 10.6, 10.7_

  - [x] 10.2 Create `static/js/persona-switcher.js`
    - `PersonaSwitcher(sessionId, headerEl)` — fetches `/api/personas` and renders a `<select>` in `.persona-slot`; first option is "— No Persona —"
    - Built-in personas rendered with a 🔒 suffix
    - On change: calls `POST /api/sessions/{id}/persona` or `DELETE /api/sessions/{id}/persona`
    - Exports `getCurrentPersonaName()` for the chat header display
    - _Requirements: 4.7_

  - [x] 10.3 Create `static/js/agent-graph.js`
    - `AgentGraph(container)` — creates an SVG element and appends it to `container`
    - `connect(rootRunId)` — opens `EventSource` on `/api/agents/runs/{id}/stream`; handles `agent_run_event` and `agent_graph_snapshot` events
    - `_renderSnapshot({nodes})` — layered layout grouped by `depth`; each node is an SVG `<g>` with `<rect>` + `<text>` + `class="status-{status}"`; edges drawn as `<line>` elements
    - Node click emits a custom DOM event with full run data for an external detail panel
    - `disconnect()` — closes `EventSource`
    - _Requirements: 2.2, 2.6, 2.7, 2.8_

  - [x] 10.4 Create `static/js/plan-tracker.js`
    - `PlanTracker(planId, containerEl)` — renders a `<div class="plan-progress">` with a `<progress>` element, step counts, and currently-running step title
    - `refresh()` — re-fetches `/api/plans/{id}` and re-renders; called on a timer or SSE event
    - _Requirements: 6.8_

  - [x] 10.5 Create `static/js/critique-toggle.js`
    - `CritiqueToggle(sessionId, headerEl)` — binds to `.critique-toggle` checkbox; on change, calls `PUT /api/sessions/{id}/critique` with 2-second `AbortController` timeout; on timeout/error, reverts checkbox and calls `showToast()`
    - `_syncState()` — fetches current config and sets checkbox state on init
    - `attachCritiqueComparison(messageEl, recordId)` — appends a "✓ Critiqued" badge to `.message-meta`; badge click fetches record and renders a side-by-side comparison panel; close button hides panel
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 10.6 Create `static/js/fork-controls.js`
    - `attachForkButtons(messageEl, messageDbId, sessionId)` — appends a "Fork from here" button to each message; click calls `POST /api/sessions/{sessionId}/fork` with `source_message_id`
    - `attachNodeForkButton(nodeEl, nodeId, messageDbId, sessionId)` — same but passes `source_node_id`
    - `renderForkBanner(sessionEl, sessionId)` — fetches `/api/sessions/{id}/fork-info`; if non-null, inserts a dismissible banner with a link back to the source session
    - _Requirements: 11.1, 11.2, 11.5, 11.7_

  - [x] 10.7 Create `static/js/phase1-init.js`
    - `initPhase1()` — imports and wires all Phase 1 modules: registers `PersonaSwitcher` for the active chat session, attaches `CritiqueToggle`, calls `renderForkBanner`, wires `attachReasoningTrace` into the existing message-render pipeline
    - Add `import { initPhase1 } from './js/phase1-init.js'; initPhase1();` to the bottom of `static/app.js`
    - _Requirements: 13.2_


- [x] 11. Reasoning trace integration with streaming chat
  - [x] 11.1 Add `reasoning_aware_stream` wrapper to the streaming path in `routes/chat_helpers.py`
    - Import `reasoning_aware_stream` from `services/reasoning/trace_extractor`
    - In the SSE streaming code path, wrap the `stream_agent_loop` call with `reasoning_aware_stream` when `active_persona_id` is set or reasoning traces are enabled for the session
    - After the stream completes, call `trace_store.persist()` with collected segments if any were found
    - This is an additive change only — the existing non-wrapped path remains the default for sessions with no Phase 1 features active
    - _Requirements: 9.1, 9.2, 9.4, 9.5, 10.5, 13.2, 13.5_

  - [x] 11.2 Add AgentRun retention pruning to the existing task scheduler
    - In `services/orchestration/run_store.py`, implement `prune_expired_runs(retention_days)` using the cascade-delete approach from the design
    - Register a daily scheduled call in the app lifespan (use the existing `TaskScheduler` pattern from `app.py`)
    - _Requirements: 12.4, 12.5_

  - [x] 11.3 Seed built-in personas on startup
    - In `app.py` lifespan (after migrations and `create_all`), instantiate `PersonaManager` and call `persona_manager.seed_builtins()`
    - _Requirements: 3.7, 13.4_

- [x] 12. Property-based tests for fork operations
  - [x]* 12.1 Write property tests for fork history and session naming
    - In `tests/phase1/test_trace_extractor.py` or a new `tests/phase1/test_fork.py`
    - **Property 11: Fork History Prefix** — for any session with N messages, forking at message k produces a session with exactly the first k messages
    - **Property 12: Fork Session Name Truncation** — for any source content string, the fork name equals `"[Fork] " + content[:50]`
    - **Validates: Requirements 11.1, 11.2, 11.3**

- [x] 13. Final checkpoint — All tests and startup validation
  - Ensure all tests in `tests/phase1/` pass with `pytest tests/phase1/ --tb=short`
  - Verify `app.py` imports all new routers without startup errors
  - Verify an existing chat session works identically to pre-Phase-1 behaviour (no persona active, critique disabled, no reasoning traces)
  - Ask the user if questions arise.

---

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2", "3", "4", "5", "6"] },
    { "wave": 3, "tasks": ["7"] },
    { "wave": 4, "tasks": ["8"] },
    { "wave": 5, "tasks": ["9"] },
    { "wave": 6, "tasks": ["10"] },
    { "wave": 7, "tasks": ["11", "12"] },
    { "wave": 8, "tasks": ["13"] }
  ]
}
```

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP pass
- Each task references specific requirements for traceability; sub-requirement numbers (e.g., `1.2`) match the acceptance criteria numbering in `requirements.md`
- Property tests reference design document properties by number (Properties 1–12 in `design.md`)
- All backend code must use the existing `SessionLocal` / `get_current_user` / `_verify_session_owner` patterns — no new auth mechanisms
- `chat_routes.py` and `session_routes.py` must not be modified; all hooks enter via `chat_helpers.py`
- Frontend modules are vanilla ES modules; no npm, no bundler, no external JS libraries
