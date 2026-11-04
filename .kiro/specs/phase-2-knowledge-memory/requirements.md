# Requirements Document

## Introduction

Phase 2 extends Odysseus's existing memory system (vector store via ChromaDB/fastembed and flat-file
`MemoryManager`) with five interconnected capabilities: temporal awareness for memory entries, an
entity/relationship graph built from conversations, per-persona memory isolation, nightly auto-digest
generation, and inline source citation tracking for research and RAG answers.

These capabilities build directly on the `services/memory/` and `routes/memory/` infrastructure
introduced in the base project and the persona system (`CrewMember` model) introduced in Phase 1.
They are designed to be additive — existing memory APIs remain backward compatible.

---

## Glossary

- **Memory_Manager**: The existing `MemoryManager` service (`services/memory/memory.py` /
  `src/memory.py`) responsible for reading and writing flat-file memory entries.
- **Vector_Store**: The existing `MemoryVectorStore` backed by ChromaDB and fastembed
  (`services/memory/memory_vector.py`).
- **Temporal_Memory_Store**: The new subsystem that augments memory entries with expiry dates,
  activation conditions, and time-scoped retrieval.
- **Graph_Memory_Store**: The new subsystem that maintains an entity/relationship graph extracted
  from chat messages.
- **Entity**: A named concept extracted from conversation: a person, project, tool, organisation,
  or domain concept.
- **Relationship**: A directed edge between two Entities with a type label (e.g. `works-on`,
  `related-to`, `mentioned-with`).
- **Namespace**: The memory isolation scope for a persona. Each `CrewMember` has its own namespace
  string; the default namespace is `global`.
- **Persona**: A `CrewMember` row from the database, representing an AI persona with its own
  personality and memory silo.
- **Auto_Digest_Service**: The background job that summarises a day's activity into a structured
  journal entry.
- **Digest**: A structured document produced by Auto_Digest_Service containing highlights, action
  items, open questions, and a tone/mood summary for a given calendar day.
- **Citation**: A structured record that links a specific claim in a response back to the exact
  source document, URL, or chunk it was drawn from, together with a confidence score.
- **Citation_Renderer**: The frontend component that renders inline citation markers and expands
  them to show source details.
- **RAG_Answer**: Any assistant reply that incorporates retrieved document chunks from the
  Vector_Store or personal-docs index.
- **Research_Report**: A document produced by the deep-research pipeline.
- **Confidence_Score**: A float in [0, 1] representing how strongly a chunk supports the claim it
  is cited for.
- **Chunk**: A bounded substring of a source document, the granular unit indexed by the
  Vector_Store.
- **Archived_Entry**: A memory entry that has passed its expiry date and been moved out of the
  active store but retained for audit/recall purposes.
- **Scheduler**: The existing `ScheduledTask` / task-scheduler infrastructure used for timed
  background jobs.
- **Owner**: The authenticated username associated with a resource; matches the `owner` column in
  existing database tables.

---

## Requirements

### Requirement 1: Temporal Memory — Expiry and Archival

**User Story:** As a user, I want my memory entries to have optional expiry dates so that
time-sensitive facts are automatically retired rather than polluting future context.

#### Acceptance Criteria

1. WHEN a user creates or updates a memory entry, THE Memory_Manager SHALL accept an optional
   `expires_at` field (ISO-8601 UTC datetime string) and persist it alongside the entry.

2. WHEN a user creates or updates a memory entry, THE Memory_Manager SHALL accept an optional
   `active_from` field (ISO-8601 UTC datetime string) and persist it alongside the entry.

3. WHILE the current UTC time is before an entry's `active_from` value, THE Memory_Manager SHALL
   exclude that entry from all context-retrieval queries.

4. WHEN a scheduled expiry check runs and the current UTC time is at or after an entry's
   `expires_at` value, THE Temporal_Memory_Store SHALL move the entry to an archived collection
   rather than deleting it.

5. WHEN an entry is archived, THE Temporal_Memory_Store SHALL record the archival timestamp on
   the entry and mark it with status `archived`.

6. WHILE an entry has status `archived`, THE Memory_Manager SHALL exclude it from all
   standard context-retrieval queries. Entries whose `expires_at` has passed but have not yet
   been processed by a scheduled expiry check SHALL remain accessible until that check runs.

7. THE Scheduler SHALL execute the expiry check at intervals of no more than 60 minutes under
   normal operating conditions while the application is running; scheduling delays caused by
   system load MAY cause individual runs to exceed the 60-minute target without being treated
   as failures.

8. WHEN the expiry check runs, THE Temporal_Memory_Store SHALL process all entries across all
   owners in a single pass.

9. IF the `expires_at` or `active_from` field of an entry contains a value that is not a valid
   ISO-8601 UTC datetime string, THEN THE Memory_Manager SHALL reject the write with a 422
   validation error and a descriptive message identifying the invalid field.


### Requirement 2: Temporal Memory — Time-Scoped Retrieval

**User Story:** As a user, I want to query my memory by time range so that I can ask the agent
"what did I know or discuss around a specific date" without manually browsing history.

#### Acceptance Criteria

1. THE Memory_Manager SHALL expose a time-range retrieval method that accepts `from_dt` and
   `to_dt` parameters (both ISO-8601 UTC datetime strings) and returns all non-archived entries
   whose `created_at` timestamp falls within the inclusive range `[from_dt, to_dt]`.

2. WHEN a time-range query is issued and `from_dt` is after `to_dt`, THE Memory_Manager SHALL
   return an empty result set rather than raising an error.

3. WHEN a time-range query is issued with only `from_dt` supplied, THE Memory_Manager SHALL
   return all non-archived entries created at or after `from_dt`.

4. WHEN a time-range query is issued with only `to_dt` supplied, THE Memory_Manager SHALL return
   all non-archived entries created at or before `to_dt`.

5. THE API layer SHALL expose a `GET /api/memory/time-range` endpoint that accepts `from_dt`,
   `to_dt`, and `owner` query parameters, enforces owner-scoping identical to existing memory
   endpoints, and returns results in ascending `created_at` order.

6. WHERE the archived entries retrieval option is explicitly enabled in the request, THE
   Memory_Manager SHALL include archived entries in the time-range result set.


### Requirement 3: Graph Memory — Extraction

**User Story:** As a user, I want the system to automatically extract entities and relationships
from my conversations so that I can track connections between people, projects, and concepts
without manual tagging.

#### Acceptance Criteria

1. WHEN a chat message is persisted to a session, THE Graph_Memory_Store SHALL schedule an
   asynchronous extraction pass on that message using an LLM-based extractor.

2. WHEN the extractor runs, THE Graph_Memory_Store SHALL identify zero or more Entities in the
   message, each with a `name` (string), `type` (`person` | `project` | `concept` | `tool` |
   `organisation`), and `owner` equal to the session owner.

3. WHEN the extractor identifies Entities that already exist in the graph for that owner (matched
   by normalised name and type), THE Graph_Memory_Store SHALL update the existing entity's
   `last_seen_at` timestamp and increment its `mention_count` rather than creating a duplicate.

4. WHEN the extractor identifies a new Entity that does not exist in the graph, THE
   Graph_Memory_Store SHALL create a new entity row with `mention_count` initialised to 1 and
   `first_seen_at` set to the current UTC time.

5. WHEN the extractor runs, THE Graph_Memory_Store SHALL identify zero or more Relationships
   between extracted Entities, each with a `type` label drawn from the set
   (`works-on`, `related-to`, `mentioned-with`, `reports-to`, `uses`, `owns`, `part-of`).

6. WHEN a Relationship between two Entities already exists in the graph for that owner, THE
   Graph_Memory_Store SHALL increment the relationship's `strength` counter rather than creating
   a duplicate edge.

7. IF the LLM extractor call fails or times out, THEN THE Graph_Memory_Store SHALL log the
   failure and skip extraction for that message without interrupting message delivery to the user.

8. THE Graph_Memory_Store SHALL store entities and relationships in the existing SQLite database
   (`data/app.db`) using new tables (`graph_entities`, `graph_relationships`) with owner-scoped
   rows.


### Requirement 4: Graph Memory — Retrieval and Context Enrichment

**User Story:** As a user, I want the agent to automatically pull relevant graph context when
answering my questions, and I want to be able to browse and search the entity graph myself.

#### Acceptance Criteria

1. WHEN the agent builds context for a query, THE Graph_Memory_Store SHALL retrieve the
   subgraph of Entities and Relationships within 2 hops of any Entity whose name appears in the
   query, and include a compact text summary in the context payload.

2. THE Graph_Memory_Store SHALL provide a search method that accepts a name fragment and returns
   all Entities whose normalised name contains that fragment, for the requesting owner.

3. THE API layer SHALL expose a `GET /api/memory/graph/entities` endpoint that returns all
   entities for the authenticated owner, supporting an optional `q` query parameter for
   name-fragment search.

4. THE API layer SHALL expose a `GET /api/memory/graph/entity/{entity_id}` endpoint that returns
   a single entity with its full neighbour list (direct edges only), 404 if not found or not
   owned by the caller.

5. THE API layer SHALL expose a `GET /api/memory/graph/export` endpoint that returns the full
   owner-scoped graph as a JSON object suitable for rendering in a force-directed layout library.

6. WHEN a graph export or entity-list response is built, THE Graph_Memory_Store SHALL include
   for each entity: `id`, `name`, `type`, `mention_count`, `first_seen_at`, `last_seen_at`.

7. WHEN a graph export response is built, THE Graph_Memory_Store SHALL include for each
   relationship: `source_id`, `target_id`, `type`, `strength`.

8. IF an entity_id in a `GET /api/memory/graph/entity/{entity_id}` request does not exist or
   belongs to a different owner, THEN THE API layer SHALL return HTTP 404.


### Requirement 5: Per-Persona Memory Isolation

**User Story:** As a user, I want each AI persona to have its own private memory silo so that
facts I share with one persona do not leak into another persona's responses.

#### Acceptance Criteria

1. WHEN a memory write occurs within a session linked to a `CrewMember` (i.e. the session row
   has a non-null `crew_member_id`), THE Memory_Manager SHALL tag the memory entry with a
   `namespace` equal to the `CrewMember.id`.

2. WHEN a memory write occurs outside any crew-member session (global chat), THE Memory_Manager
   SHALL tag the memory entry with `namespace` equal to `"global"`.

3. WHEN a context-retrieval query is issued within a persona-scoped session, THE Memory_Manager
   SHALL return only entries matching the session's namespace and SHALL NOT return entries from
   any other namespace, including `"global"`, unless explicit cross-namespace access is requested.

4. THE API layer SHALL expose a `POST /api/memory/promote` endpoint that accepts a memory
   `entry_id` and moves it from its current persona namespace to `"global"` scope, restricted to
   the authenticated owner.

5. IF a promote request targets an entry that does not belong to the authenticated owner, THEN
   THE API layer SHALL return HTTP 404.

6. IF a promote request targets an entry already in the `"global"` namespace, THEN THE API layer
   SHALL return HTTP 409 with a message indicating the entry is already global.

7. WHEN a memory entry's namespace is `"global"`, THE Memory_Manager SHALL include it in
   context-retrieval queries from any namespace belonging to the same owner.

8. THE API layer SHALL enforce namespace isolation at the retrieval endpoint level so that no
   SQL or vector query can return rows outside the caller's resolved namespace without explicit
   promote action.


### Requirement 6: Auto-Digest Generation

**User Story:** As a user, I want a nightly summary of my day's activity — chats, emails, and
notes — compiled into a structured personal journal entry so that I can review what happened and
what needs follow-up without reading every thread.

#### Acceptance Criteria

1. THE Scheduler SHALL trigger the Auto_Digest_Service once per day at a user-configurable time
   (default 02:00 local time) to generate the previous calendar day's digest.

2. WHEN triggered, THE Auto_Digest_Service SHALL collect: all chat messages from the previous
   calendar day for the owner, all email summaries received or sent that day (where an email
   integration is configured), and all note and task updates made that day.

3. WHEN the Auto_Digest_Service generates a digest, THE Auto_Digest_Service SHALL produce a
   structured output containing: `highlights` (list of key events or decisions), `action_items`
   (list of follow-up tasks extracted from the day's content), `open_questions` (unresolved
   questions or blockers identified), and `tone_summary` (a 1–3 sentence mood/productivity
   characterisation of the day).

4. WHEN a digest is generated, THE Auto_Digest_Service SHALL persist it as a Digest record in
   the database with: `owner`, `date` (the calendar day covered), `content` (full structured
   JSON), `created_at`, and a plain-text `summary` field containing the `tone_summary` for
   quick display. A Digest record MAY be created before generation completes, using a `status`
   field of `"pending"` that transitions to `"complete"` or `"failed"` once the LLM call
   finishes.

5. THE Auto_Digest_Service SHALL be triggerable on demand via a
   `POST /api/digest/generate` endpoint, accepting an optional `date` parameter (ISO-8601 date
   string, defaulting to yesterday) so users can regenerate or back-fill digests.

6. THE API layer SHALL expose a `GET /api/digest` endpoint that returns digests for the
   authenticated owner in descending date order, supporting `limit` (default 30) and `offset`
   query parameters.

7. THE API layer SHALL expose a `GET /api/digest/{date}` endpoint that returns the digest for a
   specific calendar day (ISO-8601 date string) for the authenticated owner, returning HTTP 404
   if no digest exists for that date.

8. WHEN the agent receives a query that references the recent past (e.g. "what did I do
   yesterday", "remind me of last week's actions"), THE Memory_Manager SHALL include relevant
   Digest summaries in the context payload alongside regular memory entries.

9. IF the Auto_Digest_Service encounters an LLM call failure during generation, THEN THE
   Auto_Digest_Service SHALL store a partial digest record with `status` set to `"failed"` and
   an `error` field describing the failure, rather than silently dropping the job.

10. WHERE the user has disabled automatic digest generation via user preferences, THE Scheduler
    SHALL skip the nightly trigger for that owner but SHALL still allow on-demand generation via
    the `POST /api/digest/generate` endpoint.


### Requirement 7: Auto-Digest Searchability

**User Story:** As a user, I want to search across my past digests so that I can find a specific
day's highlights without scrolling through an entire journal history.

#### Acceptance Criteria

1. THE API layer SHALL expose a `GET /api/digest/search` endpoint that accepts a `q` query
   parameter and returns all Digest records for the authenticated owner whose `content` or
   `summary` contains the search term, in descending date order.

2. WHEN a digest search query is issued with an empty or whitespace-only `q` parameter, THE API
   layer SHALL return HTTP 400 with a descriptive validation error.

3. WHEN the agent is given a digest-search tool, THE Memory_Manager SHALL invoke the digest
   search index to retrieve relevant digests as context when answering questions about past
   activity.


### Requirement 8: Source Citation Tracking — Generation

**User Story:** As a user, I want every claim in a RAG answer or research report to link back
to its exact source so that I can verify information and understand where it came from.

#### Acceptance Criteria

1. WHEN the agent produces a RAG_Answer that draws on one or more Chunks from the Vector_Store
   or personal-docs index, THE Citation system SHALL attach a `citations` list to the response
   message metadata, each element containing: `chunk_id`, `source_url` (or file path),
   `source_title`, `snippet` (the exact text passage of up to 300 characters), and
   `confidence_score` (float in [0.0, 1.0]).

2. WHEN the deep-research pipeline produces a Research_Report, THE Citation system SHALL
   attach a `citations` list at the report level, each element containing: `claim_text` (the
   sentence or clause being cited), `source_url`, `source_title`, `snippet`, and
   `confidence_score`.

3. WHEN a `confidence_score` is computed, THE Citation system SHALL derive it from the cosine
   similarity score returned by the Vector_Store retrieval, normalised to [0.0, 1.0].

4. WHEN citations are generated, THE Citation system SHALL deduplicate: if the same `chunk_id`
   or `source_url` would appear more than once in a single response's citation list, THE Citation
   system SHALL retain only the entry with the highest `confidence_score`.

5. WHEN a chat message with citations is persisted, THE Citation system SHALL store the
   `citations` list as part of the message's `metadata` JSON column so that citations survive
   page reloads and session restore.

6. IF a retrieval step returns a Chunk with no resolvable `source_url` or file path, THEN THE
   Citation system SHALL still emit the citation with `source_url` set to `null` rather than
   omitting the citation.


### Requirement 9: Source Citation Tracking — Frontend Rendering

**User Story:** As a user, I want to see inline citation markers in assistant responses that I
can expand to read the source excerpt and visit the original URL.

#### Acceptance Criteria

1. WHEN the frontend receives a message whose metadata contains a non-empty `citations` list,
   THE Citation_Renderer SHALL insert numbered superscript markers (e.g. `[1]`, `[2]`) inline
   in the rendered message text at positions corresponding to each cited claim.

2. WHEN a user clicks a citation marker, THE Citation_Renderer SHALL expand a panel showing:
   the source title, the snippet text, the source URL (as a clickable link where non-null), and
   the confidence score rendered as a percentage.

3. WHEN the same source is cited more than once in a message, THE Citation_Renderer SHALL use
   the same marker number for both occurrences.

4. WHEN the page is reloaded and a session is restored, THE Citation_Renderer SHALL re-render
   all citation markers for historical messages that have a `citations` metadata field.

5. WHEN a citation's `source_url` is null, THE Citation_Renderer SHALL display the snippet and
   title without a hyperlink, and SHALL NOT render a broken or empty anchor element.

6. WHEN a citation's `confidence_score` is below 0.5, THE Citation_Renderer SHALL visually
   distinguish the citation marker (e.g. with a different colour or icon) to indicate lower
   confidence.


### Requirement 10: Source Citation Tracking — Research Report Citations

**User Story:** As a user, I want research reports to include a references section with full
citations so that I can independently follow up on the sources the agent used.

#### Acceptance Criteria

1. WHEN a Research_Report is saved, THE Citation system SHALL append a `## References` section
   to the report content, listing each unique cited source with: an index number, the source
   title, the URL, and the snippet.

2. WHEN a research report is rendered in the Documents view, THE Citation_Renderer SHALL render
   inline `[N]` markers in the report body that link to the corresponding entry in the
   `## References` section.

3. WHEN a research report's citations are stored, THE Citation system SHALL persist them in the
   same `metadata` JSON structure used for chat-message citations, ensuring the documents API
   returns them alongside the report content.

4. IF a Research_Report is generated and no sources were retrieved (e.g. web search returned no
   results), THEN THE Citation system SHALL omit the `## References` section rather than
   rendering an empty section.
