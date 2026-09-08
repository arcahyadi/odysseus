# Requirements Document

## Introduction

Phase 1 of the Odysseus enhancement plan introduces five intelligence and reasoning capabilities to the existing self-hosted AI workspace. These capabilities elevate Odysseus from a single-agent chat tool into a structured multi-agent environment with persistent planning, self-correcting output, and transparent reasoning. The five capabilities are:

1. **Multi-Agent Orchestration** — agents that spawn sub-agents, delegate tasks, and synthesise results, with a visual execution graph and user oversight controls.
2. **Agent Personas / Roles** — preconfigured agents with distinct system prompts, tool sets, and memory scopes that users can create, edit, and switch.
3. **Long-Horizon Planning** — a planning agent that breaks goals into ordered steps, persists progress across sessions, and can resume execution automatically.
4. **Self-Critique Loops** — a configurable second-model evaluation pass that checks accuracy, completeness, and tone before displaying a response to the user.
5. **Reasoning Traces (Chain-of-Thought UI)** — inline display of thinking steps in the chat UI, with the ability to fork a conversation from any reasoning node.

All capabilities are built on top of the existing FastAPI (Python) backend and vanilla JS frontend, extending `core/`, `services/`, `routes/`, and `src/` as needed while preserving backward compatibility with the current session, memory, and authentication systems.

---

## Glossary

- **Orchestrator**: The top-level agent instance that coordinates a multi-agent run. Corresponds to a root `AgentRun` record.
- **Sub-Agent**: A child agent spawned by an Orchestrator or another Sub-Agent to handle a delegated sub-task.
- **AgentRun**: A database record representing a single agent execution, including its inputs, outputs, status, parent reference, and graph position.
- **Persona**: A named configuration bundle consisting of a system prompt, an allowed tool set, a memory scope, and an associated model/endpoint reference.
- **Plan**: A persisted, ordered list of `PlanStep` records representing the decomposition of a user goal.
- **PlanStep**: A single atomic step within a Plan, with a title, description, status (pending/running/done/failed/skipped), and optional session link.
- **CritiquePass**: A second-model evaluation pass applied to a draft assistant response before it is shown to the user.
- **ReasoningTrace**: The chain-of-thought content emitted by a model during a response, stored separately from the final answer.
- **ReasoningNode**: A single discrete step within a ReasoningTrace.
- **Fork**: A new chat session branched from a specific ReasoningNode or message in an existing session.
- **Oversight**: The user-controlled ability to pause, inspect, and cancel an active multi-agent run.
- **Memory_Scope**: The memory namespace a Persona or AgentRun can read from and write to (e.g., global, persona-specific, or session-scoped).
- **Session**: An existing Odysseus chat session as managed by `SessionManager`.
- **Orchestration_Service**: The backend service responsible for spawning, scheduling, and monitoring Sub-Agents.
- **Critique_Service**: The backend service responsible for executing a CritiquePass against a draft response.
- **Planning_Service**: The backend service responsible for goal decomposition, PlanStep execution, and progress persistence.
- **Trace_Store**: The storage layer (SQLite-backed) that persists ReasoningTraces and their ReasoningNodes.
- **SSE**: Server-Sent Events, the existing streaming mechanism used by Odysseus for real-time UI updates.
- **MCP**: Model Context Protocol, the existing tool-integration layer already present in Odysseus.

---

## Requirements

---

### Requirement 1: Multi-Agent Spawning and Delegation

**User Story:** As a power user, I want the orchestrator agent to autonomously spawn sub-agents and delegate sub-tasks to them, so that complex, multi-step work can be parallelised or specialised without requiring me to manage each step manually.

#### Acceptance Criteria

1. WHEN a user initiates a chat in agent mode, THE Orchestrator SHALL accept a high-level task description and decompose it into one or more delegated sub-tasks.
2. WHEN the Orchestrator spawns a Sub-Agent, THE Orchestration_Service SHALL create a child AgentRun record linked to the parent AgentRun via a `parent_run_id` foreign key.
3. WHEN a Sub-Agent completes its assigned sub-task, THE Orchestration_Service SHALL collect the sub-task result and make it available to the parent AgentRun for synthesis.
4. WHEN the Orchestrator synthesises all Sub-Agent results, THE Orchestration_Service SHALL produce a unified final response and associate it with the root AgentRun record.
5. WHILE a Sub-Agent is active, THE Orchestration_Service SHALL continuously enforce the parent AgentRun's tool policy so that the Sub-Agent cannot access tools the parent is not permitted to use at any point during execution.
6. WHEN a Sub-Agent encounters an unrecoverable error, THE Orchestration_Service SHALL mark that AgentRun as `failed`, propagate the error context to the parent AgentRun, and allow the Orchestrator to decide whether to retry, skip, or abort.
7. THE Orchestration_Service SHALL limit Sub-Agent spawn depth to a configurable maximum (default: 3 levels) to prevent unbounded recursion.
8. WHEN the Sub-Agent spawn depth limit is reached, THE Orchestration_Service SHALL refuse further spawning and return an error to the calling agent.

---

### Requirement 2: Multi-Agent Execution Graph and Oversight UI

**User Story:** As a user, I want to see a live visual graph of what agents are running, with controls to pause or cancel the run, so that I maintain oversight of automated work without being locked out.

#### Acceptance Criteria

1. WHEN a multi-agent run is active, THE Orchestration_Service SHALL emit SSE events describing AgentRun state transitions (created, running, completed, failed, paused, cancelled) in real time.
2. WHEN the frontend receives an AgentRun state event, THE Frontend SHALL render a directed acyclic graph showing each AgentRun node, its status, its assigned sub-task description, and its relationship to parent and child nodes.
3. WHEN the user clicks "Pause" on the oversight graph, THE Orchestration_Service SHALL attempt to gracefully suspend all running Sub-Agents within that root AgentRun (targeting completion within 5 seconds) and transition their status to `paused`; if the graceful pause exceeds 5 seconds, THE Orchestration_Service SHALL continue attempting to pause until complete rather than force-terminating agents.
4. WHEN the user clicks "Resume" on a paused run, THE Orchestration_Service SHALL resume execution of paused Sub-Agents from their last saved checkpoint.
5. WHEN the user clicks "Cancel" on an active or paused run, THE Orchestration_Service SHALL immediately terminate all Sub-Agents in that tree without waiting for a pause timeout, set each AgentRun status to `cancelled`, and surface a summary of completed and incomplete sub-tasks to the user.
6. WHEN an AgentRun node is clicked in the graph, THE Frontend SHALL display the node's input, partial or final output, tool calls made, and elapsed time.
7. THE Frontend SHALL update the graph without requiring a page reload by consuming the SSE stream for the root AgentRun.
8. WHEN a multi-agent run completes, THE Frontend SHALL persist the final graph state so the user can inspect it after the session ends.

---

### Requirement 3: Persona Definition and Storage

**User Story:** As a user, I want to create and manage agent personas with distinct system prompts, tool sets, and memory scopes, so that I can quickly switch between specialised agents without reconfiguring settings each time.

#### Acceptance Criteria

1. THE Persona_Manager SHALL store each Persona as a named record containing: a unique identifier, a display name, a system prompt, an ordered list of allowed tool names, a Memory_Scope identifier, and an optional model/endpoint reference.
2. WHEN a user creates a Persona via the UI, THE Persona_Manager SHALL persist the Persona to the database and return its assigned identifier within 2 seconds.
3. WHEN a user updates an existing Persona, THE Persona_Manager SHALL apply the changes to the stored record and SHALL NOT alter any Session that was started under the previous Persona definition.
4. WHEN a user deletes a Persona, THE Persona_Manager SHALL mark the Persona as inactive in the database and SHALL retain all historical AgentRun records that reference it.
5. THE Persona_Manager SHALL enforce that Persona display names are unique per authenticated user and between 1 and 64 characters in length.
6. WHEN a user requests the list of their Personas, THE Persona_Manager SHALL return all active Personas belonging to that user, sorted alphabetically by display name.
7. THE System SHALL provide at least three built-in read-only Personas ("Code Reviewer", "Legal Analyst", "Personal Trainer") that any user can activate but not modify or delete.
8. IF a user attempts to create more Personas than the configured per-user limit (default: 50), THEN THE Persona_Manager SHALL reject the request and return a descriptive error message.

---

### Requirement 4: Persona Activation and Session Binding

**User Story:** As a user, I want to activate a persona for a chat session so that the agent automatically uses the right system prompt, tools, and memory scope for the task at hand.

#### Acceptance Criteria

1. WHEN a user activates a Persona for a Session, THE Orchestration_Service SHALL inject the Persona's system prompt as the leading system message for that Session, replacing any previously active Persona system prompt.
2. WHEN a Persona is active for a Session, THE Orchestration_Service SHALL restrict the agent's available tool calls to the Persona's allowed tool list for every turn in that Session.
3. WHEN a Persona specifies a Memory_Scope, THE Orchestration_Service SHALL immediately scope all memory reads and writes for that Session to the designated Memory_Scope upon activation, isolating them from other scopes.
4. WHILE a Persona is active for a Session, THE Orchestration_Service SHALL continuously enforce the Persona's model/endpoint reference so that every turn in the Session uses that model, overriding the Session's default model at all times.
5. WHEN the user switches the active Persona within an ongoing Session, THE Orchestration_Service SHALL apply the new Persona's system prompt and tool restrictions starting from the next user turn, without modifying the existing message history.
6. WHEN no Persona is explicitly activated, THE Orchestration_Service SHALL use the Session's existing system prompt and tool policy without modification.
7. THE Frontend SHALL display the name of the currently active Persona in the chat header while a Persona is active for the Session.

---

### Requirement 5: Long-Horizon Plan Creation

**User Story:** As a user, I want to describe a high-level goal and have a planning agent break it into ordered, trackable steps, so that long multi-session work has a clear structure I can follow.

#### Acceptance Criteria

1. WHEN a user submits a goal to the Planning_Service, THE Planning_Service SHALL decompose the goal into an ordered list of PlanSteps and persist the resulting Plan to the database before returning a response.
2. WHEN creating a Plan, THE Planning_Service SHALL assign each PlanStep a unique identifier, a sequential order index, a title of no more than 120 characters, an optional detailed description, and an initial status of `pending`.
3. WHEN a Plan is created, THE Planning_Service SHALL estimate the number of PlanSteps required and SHALL NOT create Plans with fewer than 2 or more than 50 PlanSteps.
4. WHEN a Plan is persisted, THE Planning_Service SHALL associate the Plan with the requesting user's identifier so that the Plan is only retrievable by that user.
5. WHEN a user views the Plan list, THE Planning_Service SHALL return only Plans owned by the requesting user, including each Plan's title, total step count, completed step count, and current status, enforcing ownership filtering so no user can view another user's Plans.
6. THE Planning_Service SHALL allow users to manually add, reorder, edit, or delete individual PlanSteps at any time without disrupting Steps that are currently `running`.

---

### Requirement 6: Long-Horizon Plan Execution and Resumption

**User Story:** As a user, I want the planning agent to execute my plan's steps automatically across sessions and resume where it left off, so that I don't have to manually restart work after a break.

#### Acceptance Criteria

1. WHEN the user triggers execution of a Plan, THE Planning_Service SHALL execute PlanSteps sequentially in order-index order, advancing to the next step only after the current step reaches status `done`.
2. WHEN executing a PlanStep, THE Planning_Service SHALL create or reuse a dedicated Session for that step, execute the step's task via the agent loop, and persist the step's output to the PlanStep record before marking it `done`.
3. WHEN plan execution is interrupted (server restart, session timeout, or user pause), THE Planning_Service SHALL persist the current step index and status so that execution can resume from the last incomplete PlanStep.
4. WHEN the user resumes a Plan, THE Planning_Service SHALL restart execution from the first PlanStep that has status `pending` or `failed`, skipping all steps with status `done`.
5. WHEN a PlanStep fails after the configured maximum retry count (default: 2), THE Planning_Service SHALL mark the step as `failed`, set the parent Plan status to `paused_on_failure`, halt automatic execution, and notify the user with the error detail.
6. WHEN all PlanSteps reach status `done`, THE Planning_Service SHALL mark the parent Plan as `completed` and emit a UI notification.
7. THE Planning_Service SHALL allow the user to manually mark any PlanStep as `done` or `skipped` to override automatic execution.
8. WHEN plan execution is active, THE Frontend SHALL display a progress indicator showing the count of completed steps, the currently running step title, and the total step count.

---

### Requirement 7: Self-Critique Loop Configuration

**User Story:** As a user, I want to enable a second model pass that evaluates the assistant's response for accuracy, completeness, and tone before I see it, so that I receive higher-quality answers automatically.

#### Acceptance Criteria

1. THE Critique_Service SHALL support per-session and global configuration of the self-critique loop, with the session-level setting taking precedence over the global setting.
2. WHEN a user enables the self-critique loop for a Session, THE Critique_Service SHALL apply a CritiquePass to every subsequent assistant response in that Session until the loop is disabled.
3. WHEN a CritiquePass is applied, THE Critique_Service SHALL evaluate the draft response against three dimensions: factual accuracy (internal consistency check), completeness (does it address the user's question), and tone appropriateness.
4. WHEN the CritiquePass identifies deficiencies in the draft response, THE Critique_Service SHALL return a revised response incorporating the corrections, not a critique commentary; IF the CritiquePass cannot generate a proper revision, THEN THE Critique_Service SHALL return the original draft response unchanged.
5. WHEN the user disables the self-critique loop for a Session, THE Critique_Service SHALL immediately stop applying CritiquePasses for that Session starting from the next turn.
6. THE Critique_Service SHALL allow the user to configure which model is used for the CritiquePass independently of the primary chat model, using any model endpoint registered in the system.
7. WHEN no critique model is explicitly configured, THE Critique_Service SHALL use the same model as the primary chat Session for the CritiquePass.
8. THE Critique_Service SHALL complete the CritiquePass and return the final response to the user within 30 seconds of the primary model completing its draft.
9. WHEN the CritiquePass model is unavailable or returns an error, THE Critique_Service SHALL fall back to returning the original draft response and SHALL log the critique failure with the error detail.

---

### Requirement 8: Self-Critique Transparency and Control

**User Story:** As a user, I want to understand when and how my response was critiqued, and to toggle critique on or off easily, so that I can trust the output and adjust the behaviour when needed.

#### Acceptance Criteria

1. WHEN a CritiquePass modifies the draft response, THE Frontend SHALL display a visual indicator (e.g., a "Critiqued" badge) alongside the final message to inform the user that the response was revised and SHALL automatically show a side-by-side comparison of the original draft and the revised response.
2. WHEN the user closes the comparison view, THE Frontend SHALL hide the comparison panel and show only the revised response in the chat layout.
3. THE Frontend SHALL display a per-session critique toggle that reflects the current enabled/disabled state and allows the user to change it without leaving the chat view.
4. WHEN the user changes the critique toggle state, THE Critique_Service SHALL acknowledge the change within 1 second and apply it starting from the next assistant response; IF THE Critique_Service does not acknowledge within 2 seconds, THEN THE Frontend SHALL display an error message and revert the toggle to its previous state.
5. WHEN a CritiquePass is in progress, THE Frontend SHALL display a status indicator (e.g., "Reviewing response…") so the user knows the delay is expected.
6. THE Critique_Service SHALL record metadata for each CritiquePass including: timestamp, primary model used, critique model used, whether a revision was made, and the original and revised token counts.

---

### Requirement 9: Reasoning Trace Capture and Storage

**User Story:** As a user, I want the system to capture and store the model's chain-of-thought steps, so that I can review how a conclusion was reached.

#### Acceptance Criteria

1. WHEN a model response includes chain-of-thought content (delimited by `<think>` tags or equivalent model-specific markers), THE Trace_Store SHALL extract and persist the thinking content as a ReasoningTrace linked to the parent assistant message.
2. WHEN persisting a ReasoningTrace, THE Trace_Store SHALL parse the trace into individual ReasoningNodes, each with a unique identifier, a sequential index, and its text content.
3. THE Trace_Store SHALL store the full ReasoningTrace content in a dedicated table separate from the chat message content so that trace data does not inflate the primary message store.
4. WHEN the user has reasoning traces disabled globally, THE Trace_Store SHALL still persist the ReasoningTrace data so that the user may enable display later, but THE Frontend SHALL NOT render reasoning content for that user while the global setting is disabled.
5. THE Trace_Store SHALL associate each ReasoningTrace with the session identifier, message identifier, model name, and timestamp of the parent assistant message.
6. WHEN a Session is deleted, THE Trace_Store SHALL cascade-delete all ReasoningTraces and ReasoningNodes associated with that Session's messages.

---

### Requirement 10: Reasoning Trace Display in Chat UI

**User Story:** As a user, I want to show or hide the model's thinking steps inline in chat, so that I can understand the reasoning behind answers without the steps cluttering my view.

#### Acceptance Criteria

1. WHEN a chat message has an associated ReasoningTrace, THE Frontend SHALL render a collapsible "Thinking" disclosure element above the final response text for that message.
2. WHEN the user expands the "Thinking" disclosure, THE Frontend SHALL display the ReasoningNodes in sequential order, each visually distinguished from the final answer content.
3. WHEN the user collapses the "Thinking" disclosure, THE Frontend SHALL hide the reasoning content and restore the compact message layout without a page reload.
4. THE Frontend SHALL provide a global toggle in Settings that shows or hides all reasoning traces across all sessions by default, which individual session controls can override.
5. WHEN reasoning traces are being streamed for an active response, THE Frontend SHALL render each ReasoningNode incrementally as it arrives via SSE, clearly separated from the streaming final answer.
6. IF a message has no associated ReasoningTrace, THEN THE Frontend SHALL NOT render a "Thinking" disclosure element for that message.
7. WHEN the user hovers over a ReasoningNode, THE Frontend SHALL display a tooltip indicating the node's sequential index and character length.

---

### Requirement 11: Conversation Forking from Reasoning Nodes

**User Story:** As a user, I want to fork a conversation from any reasoning node or message, so that I can explore alternative directions without losing the original thread.

#### Acceptance Criteria

1. WHEN the user selects "Fork from here" on a ReasoningNode, THE System SHALL create a new Session containing the message history up to and including the message whose ReasoningTrace contains that node, and SHALL include the selected node's content as an injected context message.
2. WHEN the user selects "Fork from here" on a regular chat message, THE System SHALL create a new Session containing the message history up to and including that message.
3. WHEN a forked Session is created, THE System SHALL set the new Session's name to "[Fork] " followed by the first 50 characters of the source message or node content.
4. WHEN a forked Session is created, THE System SHALL link it to the source Session via a `forked_from_session_id` field and a `forked_from_message_id` field on the new Session record.
5. WHEN the user navigates to a forked Session, THE Frontend SHALL display a banner indicating the Session was forked from a specific source Session, with a link back to the source.
6. THE System SHALL apply the same ownership and access controls to forked Sessions as to any user-created Session.
7. WHEN the user forks from a message in a shared or multi-user context, THE System SHALL create the forked Session under the requesting user's ownership only.

---

### Requirement 12: Agent Run Persistence and Audit

**User Story:** As a user, I want all agent runs — including sub-agent activity — to be persisted and retrievable, so that I can audit what happened and replay or reference earlier runs.

#### Acceptance Criteria

1. THE Orchestration_Service SHALL persist every AgentRun record to the database, including: run identifier, parent run identifier (nullable), persona identifier (nullable), session identifier, assigned task description, status, start time, end time (nullable), token usage, and tool calls made.
2. WHEN a user queries agent run history, THE Orchestration_Service SHALL return all AgentRun records owned by that user, filterable by status, date range, and root run identifier.
3. WHEN a user requests the detail of a specific AgentRun, THE Orchestration_Service SHALL return the full record including the agent's input messages, output, tool call log, and all child AgentRun identifiers.
4. THE Orchestration_Service SHALL retain AgentRun records for a configurable retention period (default: 90 days) before automatic deletion.
5. WHEN an AgentRun record is deleted due to retention expiry, THE Orchestration_Service SHALL also delete all child AgentRun records in the same tree.
6. IF an authenticated user is not the owner of an AgentRun, THEN THE Orchestration_Service SHALL return a 403 Forbidden response for any request targeting that AgentRun; IF the requested AgentRun identifier does not exist at all, THEN THE Orchestration_Service SHALL return a 404 Not Found response.

---

### Requirement 13: Backward Compatibility and Integration

**User Story:** As an existing Odysseus user, I want Phase 1 features to integrate cleanly with the existing system so that my current sessions, memory, tools, and authentication continue to work without reconfiguration.

#### Acceptance Criteria

1. THE System SHALL preserve all existing Session, ChatMessage, and memory records without migration data loss when Phase 1 database schema changes are applied.
2. WHEN Phase 1 features are not explicitly activated by the user, THE System SHALL operate identically to the pre-Phase-1 behaviour for all existing routes and chat flows.
3. THE System SHALL continue to honour all existing authentication, API token, and authorization mechanisms without modification.
4. WHEN Phase 1 services (Orchestration_Service, Critique_Service, Planning_Service, Trace_Store) are initialised, THE System SHALL not introduce startup latency exceeding 2 seconds compared to the pre-Phase-1 baseline.
5. THE System SHALL expose all Phase 1 capabilities via new FastAPI route modules that do not modify the existing route handlers in `routes/chat_routes.py` or `routes/session_routes.py`.
6. WHEN the MCP tool integration is invoked from within a Persona-bound Session, THE System SHALL apply the Persona's allowed tool list as an additional filter on top of the existing MCP tool policy without bypassing existing tool security controls.
