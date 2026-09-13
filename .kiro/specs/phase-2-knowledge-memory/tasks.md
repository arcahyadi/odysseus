# Implementation Plan: Phase 2 — Knowledge & Memory

## Overview

This plan extends Odysseus's memory system with five additive feature areas: temporal
memory (expiry/archival), graph memory (entity/relationship extraction), per-persona
namespace isolation, auto-digest generation, and source citation tracking. Each task
area follows a strict dependency order: DB models → services → routes → integration
hooks → frontend components. All changes are additive; existing APIs remain backward
compatible.

## Tasks

- [x] 1. Add SQLAlchemy models and run startup migrations
  - [x] 1.1 Add `GraphEntity`, `GraphRelationship`, and `Digest` ORM models to `core/database.py`
    - Define `GraphEntity` with columns: `id`, `owner`, `name`, `name_norm`, `type`, `mention_count`, `first_seen_at`, `last_seen_at`; add `UniqueConstraint("owner","name_norm","type")` and indexes
    - Define `GraphRelationship` with columns: `id`, `owner`, `source_id` (FK→graph_entities, CASCADE), `target_id` (FK→graph_entities, CASCADE), `type`, `strength`, `created_at`; add unique constraint and indexes
    - Define `Digest` with columns: `id`, `owner`, `date`, `status`, `content`, `summary`, `error`, `created_at`, `updated_at`; add `UniqueConstraint("owner","date")` and descending index `ix_digests_owner_date`
    - Import `UniqueConstraint` from sqlalchemy if not already present
    - _Requirements: 3.8, 6.4_
  - [x] 1.2 Add `_run_phase2_migrations` function in `core/database.py` and call it at startup
    - Create an idempotent function that calls `Base.metadata.create_all(engine)` (already done) and then executes `CREATE INDEX IF NOT EXISTS ix_digests_owner_date ON digests(owner, date DESC)`
    - Call this function at the bottom of `core/database.py` after the engine is created
    - _Requirements: 3.8, 6.4_

- [x] 2. Implement Temporal Memory Store and Namespace Resolver services
  - [x] 2.1 Create `services/memory/temporal.py` with `TemporalMemoryStore`
    - Implement `_parse_iso(value)` helper that raises `ValueError` on malformed input
    - Implement `validate_temporal_fields(expires_at, active_from)` — raise `ValueError` with descriptive message if either field fails `_parse_iso`
    - Implement `set_temporal(entry, expires_at, active_from)` — attach fields to entry dict, default `status` to `"active"`
    - Implement `is_active(entry)` — returns `False` if `status=="archived"` or `active_from` is a future datetime
    - Implement `filter_active(entries)` — list comprehension over `is_active`
    - Implement `time_range_query(entries, from_dt, to_dt, include_archived)` — parse bounds, return `[]` when `from_dt > to_dt`, sort ascending by `timestamp`
    - Implement `run_expiry_pass()` — scan all entries via `memory_manager.load_all()`, set `status="archived"` and `archived_at` on expired entries, call `memory_vector.remove(id)` for each archived entry, persist, return count
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.1, 2.2, 2.3, 2.4_
  - [x]* 2.2 Write property tests for `TemporalMemoryStore` in `tests/phase2/test_temporal.py`
    - **Property 1: Temporal fields round-trip** — `set_temporal` → `save` → `load_all` preserves `expires_at` and `active_from`
    - **Property 2: Active-from exclusion** — any entry with `active_from` in the future is excluded by `filter_active`
    - **Property 3: Expiry archival completeness** — after `run_expiry_pass`, every entry with a past `expires_at` has `status=="archived"` and `archived_at` set
    - **Property 4: Archived entries excluded** — `filter_active` never returns an entry with `status=="archived"`
    - **Property 5: Time-range filter correctness** — result contains exactly those active entries whose `timestamp` is within `[from_dt, to_dt]`
    - Use `hypothesis` with `@settings(max_examples=100)`; tag each test: `# Feature: phase-2-knowledge-memory, Property N: <title>`
    - Also add unit tests: invalid ISO-8601 string raises `ValueError`; malformed stored `expires_at` is skipped during expiry pass
    - _Requirements: 1.1–1.9, 2.1–2.4_
  - [x] 2.3 Create `services/memory/namespace.py` with `NamespaceResolver`
    - Implement `resolve_namespace(crew_member_id)` — returns `crew_member_id` if non-None, else `"global"`
    - Implement `write_entry(entry, crew_member_id)` — tags entry dict with resolved namespace
    - Implement `filter_for_session(entries, owner, crew_member_id)` — persona sessions see `namespace==crew_member_id OR namespace=="global"`; global sessions see only `namespace=="global"`; legacy entries with no namespace field default to `"global"` via `.get("namespace","global")`
    - Implement `promote_to_global(entry_id, owner)` — load all entries, find by id+owner (raise `KeyError` if not found), raise `ValueError` if already global, set `namespace="global"`, save, return updated entry
    - Create `services/memory/__init__.py` exports if needed
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  - [x]* 2.4 Write property and unit tests for `NamespaceResolver` in `tests/phase2/test_namespace.py`
    - **Property 6: Namespace isolation** — `filter_for_session` for any `crew_member_id` never returns entries whose namespace is neither that ID nor `"global"`
    - Unit tests: promote succeeds and returns updated entry; promote already-global raises `ValueError`; promote cross-owner raises `KeyError`; global session receives only `"global"` entries
    - _Requirements: 5.1–5.8_

- [x] 3. Implement Graph Memory Store service
  - [x] 3.1 Create `services/memory/graph.py` with `GraphMemoryStore` — extraction internals
    - Define module-level constants: `VALID_ENTITY_TYPES`, `VALID_REL_TYPES`, `_EXTRACTION_SYSTEM` prompt
    - Implement `_parse_extraction(raw)` — strip markdown fences, `json.loads`, validate entity types against `VALID_ENTITY_TYPES`, validate relationship types against `VALID_REL_TYPES`, return sanitised dict or `{"entities":[],"relationships":[]}` on any error
    - Implement `_upsert_entities(db, owner, entities)` — for each entity, look up by `(owner, name_norm, type)`; if found increment `mention_count` and update `last_seen_at`; if new insert with `mention_count=1`; return `name→id` map
    - Implement `_upsert_relationships(db, owner, entity_map, relationships)` — look up by `(owner, source_id, target_id, type)`; if found increment `strength`; if new insert; skip self-loops and unmapped names
    - Implement `_extract_and_store(message, owner, endpoint_url, model, headers)` async — call LLM with 30s timeout, parse result, run upserts in a DB session, commit; on any exception log warning and return (never re-raise)
    - Implement `schedule_extraction(message, owner, endpoint_url, model, headers)` — wraps `_extract_and_store` in `asyncio.create_task`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_
  - [x] 3.2 Add retrieval methods to `GraphMemoryStore` in `services/memory/graph.py`
    - Implement `_build_context_text(db, owner, seed_ids, max_hops=2)` — BFS up to 2 hops via `graph_relationships` (both `source_id` and `target_id` directions), collect visited entity IDs, return compact `[Knowledge Graph Context]` string listing name/type/mention_count
    - Implement `get_2hop_context(owner, query)` — find seed entities whose `name_norm` appears in `query.lower()`, delegate to `_build_context_text`; return `""` if no seeds
    - Implement `search_entities(owner, fragment)` — query `GraphEntity` filtered by owner; if fragment given, add `name_norm.contains(fragment.lower())` filter; return list of dicts via `_entity_to_dict`
    - Implement `get_entity_with_neighbours(owner, entity_id)` — fetch entity by `id+owner`; return `None` if not found; include direct edges as `relationships` list in result dict
    - Implement `export_graph(owner)` — return `{"nodes":[...], "edges":[...]}` with all owner entities and relationships
    - Implement `_entity_to_dict(entity)` static method — return `{id, name, type, mention_count, first_seen_at, last_seen_at}`
    - _Requirements: 4.1, 4.2, 4.6, 4.7_
  - [x]* 3.3 Write tests for `GraphMemoryStore` in `tests/phase2/test_graph.py`
    - **Property 10: Entity type validation** — `_parse_extraction` on arbitrary raw entity JSON always returns entities whose `type` is in `VALID_ENTITY_TYPES`
    - Unit tests: LLM timeout is caught and extraction skips silently; malformed JSON returns empty entities/relationships; duplicate entity (same owner/name_norm/type) increments `mention_count` not inserts new row; duplicate relationship increments `strength`; 2-hop context includes nodes 2 edges away from seed
    - _Requirements: 3.1–3.8, 4.1, 4.2_

- [x] 4. Implement Auto-Digest Service
  - [x] 4.1 Create `services/digest/__init__.py` (empty or re-export `DigestService`)
    - _Requirements: 6.1_
  - [x] 4.2 Create `services/digest/digest_service.py` with `DigestService` — collection and generation
    - Define `_DIGEST_SYSTEM` prompt string
    - Implement `_collect_day(db, owner, target_date)` — query `ChatMessage` joined to `Session`, filter by owner, midnight-to-midnight window for `target_date`, roles `"user"` and `"assistant"`, order by `timestamp`; format as `[ROLE] content[:500]` lines; return `"(no activity)"` if empty
    - Implement `generate(owner, target_date, endpoint_url, model, headers)` async — default `target_date` to yesterday UTC; upsert a `Digest` row with `status="pending"`; collect day's activity; call LLM with 30s-tolerant timeout; parse JSON response normalising keys `highlights`, `action_items`, `open_questions`, `tone_summary`; on LLM failure update row to `status="failed"` with `error` field and return failure dict; on success update row to `status="complete"` with `content` (JSON dump) and `summary` (tone_summary)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.9_
  - [x] 4.3 Add retrieval methods to `DigestService`
    - Implement `list_digests(owner, limit, offset)` — query `Digest` ordered by `date DESC`, paginated
    - Implement `get_by_date(owner, date_str)` — return single digest dict or `None`
    - Implement `search(owner, q)` — load all owner digests, filter rows where `q.lower()` appears in `content` or `summary` (case-insensitive), return in descending date order
    - Implement `_digest_to_dict(row)` static method — deserialise `content` JSON, return `{id, date, status, summary, content, error, created_at}`
    - _Requirements: 6.6, 6.7, 6.8, 6.10, 7.1, 7.2_
  - [x]* 4.4 Write tests for `DigestService` in `tests/phase2/test_digest_service.py`
    - Unit tests: LLM failure stores `status="failed"` record with error text; re-triggering same owner+date reuses existing row (no duplicate insert); `list_digests` returns results in descending date order; `search` with empty/whitespace `q` returns empty list (400 enforcement is at the route layer); missing date returns `None` from `get_by_date`
    - _Requirements: 6.1–6.10, 7.1–7.3_

- [x] 5. Implement Citation Service
  - [x] 5.1 Create `services/citations/__init__.py` (empty or re-export `CitationService`)
    - _Requirements: 8.1_
  - [x] 5.2 Create `services/citations/citation_service.py` with `CitationService`
    - Implement `_normalise_score(score)` module-level helper — clamp `float(score)` to `[0.0, 1.0]` via `max(0.0, min(1.0, ...))`
    - Implement `_dedup_citations(citations)` module-level helper — key on `chunk_id or source_url`, keep entry with highest `confidence_score` per key
    - Implement `build_rag_citations(retrieval_results)` — for each hit extract `chunk_id`, `source_url` (try `metadata.source_url`, `metadata.url`, default `None`), `source_title`, `snippet[:300]`, `confidence_score = _normalise_score(1.0 - distance)`; call `_dedup_citations`
    - Implement `build_research_citations(sources)` — for each source extract url/title/snippet[:300], assign `confidence = _normalise_score(source.get("confidence", 1.0))`; call `_dedup_citations`
    - Implement `attach_to_message_metadata(existing_metadata, citations)` — parse existing JSON string (or start with `{}`), set `meta["citations"] = citations`, return `json.dumps(meta)`
    - Implement `inject_references_section(report_content, citations)` — return `report_content` unchanged if `citations` is empty; otherwise append `\n\n## References\n` with numbered entries: `[N] [title](url)` (or plain `[N] title` if url is null) followed by indented snippet
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 10.1, 10.4_
  - [x]* 5.3 Write property and unit tests for `CitationService` in `tests/phase2/test_citation_service.py`
    - **Property 7: Citation deduplication keeps maximum confidence** — `_dedup_citations` on any list with duplicate `chunk_id`s produces exactly one entry per key with the maximum `confidence_score`
    - **Property 8: Confidence normalisation always in [0.0, 1.0]** — `_normalise_score` on any finite float returns a value in `[0.0, 1.0]`
    - **Property 9: References section present iff citations non-empty** — `inject_references_section` with non-empty citations always contains `## References`; with empty list returns unchanged content
    - Unit tests: null `source_url` is preserved as `None` in output dict (not omitted); `attach_to_message_metadata` preserves existing metadata keys; `inject_references_section` with empty citations list returns content unchanged
    - _Requirements: 8.1–8.6, 10.1, 10.4_

- [x] 6. Add API routes
  - [x] 6.1 Extend `routes/memory/memory_routes.py` with `GET /api/memory/time-range`
    - Add `TemporalMemoryStore` and `PromoteRequest` Pydantic model imports at top of file
    - Instantiate `TemporalMemoryStore(memory_manager, memory_vector)` at module level (or inject via dependency)
    - Add `GET /time-range` route: extract `owner` via `require_user`, call `memory_manager.load(owner=owner)`, pass to `temporal_store.time_range_query(entries, from_dt, to_dt, include_archived)`, return `{"entries": results, "count": len(results)}`
    - _Requirements: 2.5, 2.6_
  - [x] 6.2 Extend `routes/memory/memory_routes.py` with `POST /api/memory/promote`
    - Add `NamespaceResolver` import; instantiate `NamespaceResolver(memory_manager)` at module level
    - Add `POST /promote` route: extract owner, call `ns_resolver.promote_to_global(body.entry_id, owner)`, map `KeyError` → HTTP 404, `ValueError` → HTTP 409
    - _Requirements: 5.4, 5.5, 5.6_
  - [x] 6.3 Create `routes/memory/graph_routes.py` with graph API endpoints
    - Create an `APIRouter` with prefix `/api/memory/graph`
    - Instantiate `GraphMemoryStore()` at module level
    - `GET /entities` — call `graph_store.search_entities(owner, q)`, return `{"entities": [...]}`
    - `GET /entity/{entity_id}` — call `graph_store.get_entity_with_neighbours(owner, entity_id)`, raise HTTP 404 if `None`
    - `GET /export` — call `graph_store.export_graph(owner)`, return `{"nodes": [...], "edges": [...]}`
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_
  - [x] 6.4 Create `routes/digest/__init__.py` and `routes/digest/digest_routes.py`
    - Create `routes/digest/` directory with `__init__.py`
    - Create `APIRouter` with prefix `/api/digest`; instantiate `DigestService()` at module level
    - `POST /generate` — parse optional `date` param, call `asyncio.create_task(digest_service.generate(...))`, return 202 `{"ok": True, "digest_id": ..., "status": "pending"}`
    - `GET /` — accept `limit` (default 30) and `offset` query params, return `{"digests": [...], "total": len(...)}`
    - `GET /search` — require non-blank `q` (return HTTP 400 with descriptive error on empty/whitespace), call `digest_service.search(owner, q)`, return `{"digests": [...], "count": len(...)}`
    - `GET /{date}` — call `digest_service.get_by_date(owner, date)`, raise HTTP 404 if `None`
    - Note: route order matters — register `/search` before `/{date}` to prevent path ambiguity
    - _Requirements: 6.5, 6.6, 6.7, 7.1, 7.2_
  - [x] 6.5 Register new routers in `app.py`
    - Import and include `graph_routes.router` and `digest_routes.router` with appropriate prefixes
    - Ensure memory router is already included (it should be); verify the memory router file includes the new time-range and promote routes
    - _Requirements: 2.5, 4.3–4.5, 5.4, 6.5–6.7, 7.1_

- [x] 7. Wire integration hooks into existing pipelines
  - [x] 7.1 Add namespace tagging to memory write path in `routes/memory/memory_routes.py`
    - On any memory write (add/update), resolve the session's `crew_member_id` from the request context (passed as query param or body field), call `ns_resolver.write_entry(entry, crew_member_id)` to tag `namespace` before persisting
    - Validate `expires_at` / `active_from` fields on write via `temporal_store.validate_temporal_fields`; raise HTTP 422 on invalid ISO-8601
    - Call `temporal_store.set_temporal(entry, expires_at, active_from)` to attach temporal fields
    - Existing entries without a `namespace` field read as `"global"` in all filter operations (no backfill required)
    - _Requirements: 1.1, 1.2, 1.9, 5.1, 5.2_
  - [x] 7.2 Hook graph extraction into chat pipeline in `routes/chat_routes.py`
    - After `ChatMessage` is persisted, add `asyncio.create_task(graph_store.schedule_extraction(message_content, owner, endpoint_url, model, headers))` — fire-and-forget
    - Import `GraphMemoryStore` and instantiate it (or retrieve from `app.state`) at the top of the file
    - Ensure any exception from the task is caught within `_extract_and_store` and logged, never propagated to the SSE stream
    - _Requirements: 3.1, 3.7_
  - [x] 7.3 Hook citation service into the RAG answer path
    - In the RAG pipeline (where `MemoryVectorStore.search` results are assembled into context), call `CitationService().build_rag_citations(retrieval_results)` after retrieval
    - Call `citation_service.attach_to_message_metadata(existing_metadata, citations)` before `session_manager._persist_message` is called
    - _Requirements: 8.1, 8.5_
  - [x] 7.4 Hook citation service into the research pipeline in `routes/research_routes.py`
    - After the research handler returns sources, call `CitationService().build_research_citations(sources)` to build a citation list
    - Call `citation_service.inject_references_section(report_content, citations)` before the research result is persisted to a `Document`
    - Store citations in the document's metadata JSON via `attach_to_message_metadata` so the documents API returns them
    - _Requirements: 8.2, 8.5, 10.1, 10.2, 10.3, 10.4_
  - [x] 7.5 Register expiry-check and nightly-digest tasks in the scheduler
    - In the scheduler startup code (wherever `ScheduledTask` recurring jobs are registered — check `src/app_initializer.py` or `app.py` lifespan), register the expiry check job: interval ≤ 60 minutes, calls `temporal_store.run_expiry_pass()`
    - Register the nightly digest job: daily at 02:00 local time (configurable), calls `digest_service.generate(owner, ...)` for each owner; honour per-user opt-out via user preferences before triggering
    - _Requirements: 1.7, 6.1, 6.10_
  - [x] 7.6 Include 2-hop graph context and digest summaries in agent context builder
    - In the agent context assembly path (wherever memory entries are collected to build the system-prompt context), call `graph_store.get_2hop_context(owner, query)` and prepend the returned string (if non-empty) under a `[Knowledge Graph Context]` header
    - Also query recent digests via `digest_service.list_digests(owner, limit=7)` and include `summary` fields for any digests whose date is relevant to the query (e.g. "yesterday", "last week")
    - _Requirements: 4.1, 6.8_

- [x] 8. Checkpoint — ensure backend is functional before adding frontend
  - Ensure all tests pass, ask the user if questions arise.
  - Verify the app starts without errors with the new routes registered.
  - Run `tests/phase2/` suite to confirm property and unit tests pass.

- [x] 9. Implement frontend ES modules
  - [x] 9.1 Create `static/js/citations.js` with `CitationRenderer` class
    - Export `CitationRenderer` class with `render(messageEl, citations)` method
    - `render`: build the citations box and append it once per message (short-circuits when the target already holds a `.citations-box`, so a re-render is a no-op)
    - Renders a collapsible `<details class="citations-box">` whose `<summary>` reads `Citations (N)`; the body holds a numbered list of `.citation-item` rows, each with `.citation-num`, the source title (an `<a class="citation-link" target="_blank" rel="noopener noreferrer">` only when `source_url` matches `^https?://`, else a plain `<span>`), a `.citation-confidence` percentage, and a `.citation-snippet` truncated to 300 chars
    - Expand/collapse is handled natively by `<details>`; no inline `<sup>` markers are spliced into the answer text
    - Export `restoreFromMetadata(messageEl, metadataJson)` method for session restore — parse JSON, call `render` if `citations` array is present and non-empty
    - Use the shared `esc` helper from `ui.js` for all user-facing strings to prevent XSS
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

    > **Implementation note (2026-09-13).** The plan above originally specified inline
    > `<sup class="citation-marker">` markers spliced into the answer via a
    > `TreeWalker`, plus a separate `<ol class="citation-refs">` reference list (and
    > `_insertSupscripts` / `_appendRefList` / `citation-low-confidence`). The shipped
    > code takes a different approach: one collapsible citations box per message. The
    > user-visible outcome is equivalent (citations are present, numbered and
    > clickable for a RAG answer) and was verified in a real browser at 3 text-scale
    > settings, so this entry has been amended to describe the code as built rather
    > than the code as originally planned.
  - [x] 9.2 Create `static/js/memory-graph.js` with `MemoryGraphView` class
    - Export `MemoryGraphView` class; constructor accepts an `<svg>` element
    - `load(owner)` — `fetch("/api/memory/graph/export")`, parse JSON, call `_render(nodes, edges)`
    - `_render(nodes, edges)` — implement a simple SVG force-directed layout using `requestAnimationFrame` (mirror the pattern from the existing `agent_graph.js` if present); colour nodes by type (person=blue, project=green, concept=orange, tool=purple, organisation=teal); weight edge line stroke-width by `strength`; show hover tooltip with `mention_count` and `first_seen_at`
    - _Requirements: 4.3, 4.5, 4.6, 4.7_
  - [x] 9.3 Create `static/js/digest-panel.js` with `DigestPanel` class
    - Export `DigestPanel` class; constructor accepts a container element
    - `load()` — `fetch("/api/digest?limit=30")`, render list of digest cards showing `date` and `summary` text
    - `loadDate(dateStr)` — `fetch("/api/digest/${dateStr}")`, render detail modal/panel showing `highlights`, `action_items`, `open_questions`, `tone_summary` from parsed `content`
    - `search(q)` — `fetch("/api/digest/search?q=...")`, render results list
    - Handle 404 gracefully (show "No digest for this date" message); handle 400 on blank search (show validation hint)
    - _Requirements: 6.6, 6.7, 7.1, 7.2_

- [x] 10. Final checkpoint — end-to-end verification
  - Ensure all tests pass, ask the user if questions arise.
  - Verify temporal fields survive a write/read cycle via the API.
  - Verify graph entities appear after a chat message is sent.
  - Verify a digest can be generated on demand via `POST /api/digest/generate`.
  - Verify citation markers render in the UI for a RAG answer with retrieved chunks.

  > **Verified 2026-09-12 → 2026-09-13. All four steps pass.** The first pass
  > FAILED and surfaced two blocking defects, both now fixed:
  > 1. `GET /api/memory/time-range` was unreachable — the Phase 2 routes were
  >    registered *after* the `GET /{memory_id}` wildcard in
  >    `routes/memory/memory_routes.py`, so the wildcard matched the literal id
  >    `"time-range"` first and always 404'd. Routes reordered; regression test
  >    added at `tests/test_memory_routes_ordering.py`.
  > 2. `POST /api/digest/generate` forwarded an empty endpoint from the UI's `{}`
  >    body (`DigestService.generate` uses `endpoint_url` verbatim and resolves no
  >    default), so every digest was persisted `status="failed"` and the "Generate
  >    now" button could never succeed. The route now resolves via
  >    `resolve_task_endpoint`, raises 503 when nothing is configured instead of
  >    writing a failed row, and returns a `digest_id` that matches the persisted
  >    row.
  >
  > Evidence: temporal write/read 12/12; graph extraction 14/14 (real HTTP call to
  > a local `/v1/chat/completions` stub, entities persisted and retrievable,
  > idempotent, failures isolated); digest route 17/17 and service 23/23; citation
  > service 20/20 plus a DOM run of the real `citations.js` 20/20. `tests/phase2`
  > passes. Spec entry 9.1 was amended to describe the shipped citations box.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP iteration.
- Each task references specific requirements numbers for traceability.
- Strict ordering: tasks 1 → 2/3/4/5 (parallel) → 6 → 7 → 8 (checkpoint) → 9 → 10.
- All existing memory endpoints and data remain backward compatible — no migration scripts needed for flat-file JSON.
- Property tests use `hypothesis` (`pip install hypothesis`); each test should run with `@settings(max_examples=100)` minimum.
- Integration hooks in tasks 7.2–7.4 are additive: all existing chat/research/RAG flows continue to work if the new services raise an exception (errors are caught and logged).

## Task Dependency Graph

```json
{
  "tasks": {
    "1": {
      "title": "Add SQLAlchemy models and startup migrations",
      "subtasks": ["1.1", "1.2"],
      "depends_on": []
    },
    "2": {
      "title": "Implement TemporalMemoryStore and NamespaceResolver",
      "subtasks": ["2.1", "2.2", "2.3", "2.4"],
      "depends_on": ["1"]
    },
    "3": {
      "title": "Implement GraphMemoryStore",
      "subtasks": ["3.1", "3.2", "3.3"],
      "depends_on": ["1"]
    },
    "4": {
      "title": "Implement DigestService",
      "subtasks": ["4.1", "4.2", "4.3", "4.4"],
      "depends_on": ["1"]
    },
    "5": {
      "title": "Implement CitationService",
      "subtasks": ["5.1", "5.2", "5.3"],
      "depends_on": []
    },
    "6": {
      "title": "Add API routes",
      "subtasks": ["6.1", "6.2", "6.3", "6.4", "6.5"],
      "depends_on": ["2", "3", "4", "5"]
    },
    "7": {
      "title": "Wire integration hooks into existing pipelines",
      "subtasks": ["7.1", "7.2", "7.3", "7.4", "7.5", "7.6"],
      "depends_on": ["2", "3", "4", "5", "6"]
    },
    "8": {
      "title": "Checkpoint — backend functional verification",
      "subtasks": [],
      "depends_on": ["7"]
    },
    "9": {
      "title": "Implement frontend ES modules",
      "subtasks": ["9.1", "9.2", "9.3"],
      "depends_on": ["6"]
    },
    "10": {
      "title": "Final checkpoint — end-to-end verification",
      "subtasks": [],
      "depends_on": ["8", "9"]
    }
  },
  "waves": [
    ["1"],
    ["2", "3", "4", "5"],
    ["6"],
    ["7"],
    ["8"],
    ["9"],
    ["10"]
  ],
  "critical_path": ["1", "2", "6", "7", "8", "9", "10"]
}
```
