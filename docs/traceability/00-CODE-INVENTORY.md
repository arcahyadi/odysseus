# Inventaire Code — Réalité (auto-généré)

*Généré: 2026-09-25 — branche feat/inventaire-global-v1*

## Routes (API)

| Fichier | #endpoints | exemples |
|---|---|---|
| email_routes.py | 47 | GET /list; POST /{uid}/unflag-spam; GET /contacts |
| gallery_routes.py | 33 | POST /api/gallery/upload; POST /api/gallery/{image_id}/replace; POST /api/gallery/{image_id}/rename |
| auth_routes.py | 29 | POST /setup; POST /signup; POST /login |
| codex_routes.py | 29 | GET /capabilities; GET /plugin.zip; GET /todos |
| document_routes.py | 24 | POST /api/document; POST /api/documents/import-pdf; GET /api/documents/library |
| skills_routes.py | 20 | GET /index; GET /slash-catalog; GET /builtin |
| task_routes.py | 20 | GET /onboarding; POST /onboarding; GET /notifications |
| calendar_routes.py | 19 | GET /config; POST /config; GET /config/accounts |
| model_routes.py | 19 | GET /models; GET /model-endpoints/probe-local; GET /ping |
| session_routes.py | 19 | GET /sessions; POST /session; PATCH /session/{sid} |
| cookbook_routes.py | 16 | GET /api/cookbook/ssh-key; POST /api/cookbook/ssh-key; POST /api/model/download |
| research_routes.py | 15 | GET /api/research/active; GET /api/research/status/{session_id}; POST /api/research/cancel/{session_id} |
| memory_routes.py | 14 | POST /debug; POST /add; POST /search |
| history_routes.py | 11 | GET /api/history/{session_id}; POST /api/session/{session_id}/truncate; POST /api/session/{session_id}/message |
| mcp_routes.py | 11 | GET /servers; POST /servers; POST /servers/{server_id}/reconnect |
| contacts_routes.py | 10 | GET /list; GET /search; POST /add |
| knowledge_routes.py | 10 | GET /code/search; GET /code/trace; GET /code/snippet |
| chat_routes.py | 8 | POST /api/chat; POST /api/chat_stream; GET /api/chat/resume/{session_id} |
| note_routes.py | 8 | GET /{note_id}; PUT /{note_id}; DELETE /{note_id} |
| preset_routes.py | 8 | GET /api/presets; POST /api/presets/custom; GET /api/presets/templates |
| embedding_routes.py | 7 | GET /models; POST /models/{model_name:path}/download; GET /models/{model_name:path}/status |
| assistant_routes.py | 6 | GET /session; GET /settings; PATCH /settings |
| diagnostics_routes.py | 6 | GET /api/diagnostics/services; GET /api/diagnostics/logs; GET /api/db/stats |
| governance_routes.py | 6 | GET /budgets; GET /budgets/{agent_id}; POST /heartbeat/{agent_id} |
| shell_routes.py | 6 | POST /api/shell/exec; POST /api/shell/stream; GET /api/cookbook/packages |
| vault_routes.py | 6 | GET /config; POST /config; POST /login |
| webhook_routes.py | 6 | GET /webhooks; POST /webhooks; POST /webhooks/{webhook_id}/test |
| api_token_routes.py | 5 | GET /tokens; GET /tokens/profiles; POST /tokens |
| compare_routes.py | 5 | POST /start; POST /{comp_id}/vote; POST /record |
| editor_draft_routes.py | 5 | GET /api/editor-drafts; GET /api/editor-drafts/{draft_id}; POST /api/editor-drafts |
| personal_routes.py | 5 | POST /reload; POST /add_directory; DELETE /remove_directory |
| search_routes.py | 5 | GET /api/search/config; POST /api/search; GET /api/search/providers |
| upload_routes.py | 5 | POST /cleanup; GET /stats; GET /{file_id} |
| autoeval_routes.py | 4 | POST /evaluate; POST /run-eval-only; GET /summary |
| backup_routes.py | 4 | GET /api/export; POST /api/import; POST /api/backup/export |
| hwfit_routes.py | 4 | GET /system; GET /models; GET /profiles |
| tts_routes.py | 4 | GET /stats; POST /synthesize; POST /clear-cache |
| channel_routes.py | 3 | POST /send; POST /broadcast; GET /status |
| device_flow.py | 3 | POST /device/start; POST /device/poll; POST /device/cancel |
| phase_routes.py | 3 | POST /set; GET /current/{session_id}; GET /config |
| signature_routes.py | 3 | GET /api/signatures; POST /api/signatures; DELETE /api/signatures/{sig_id} |
| workspace_routes.py | 3 | GET /browse; GET /vet; GET /read |
| mcp_tools_routes.py | 2 | POST /diagram; GET /available |
| n8n_routes.py | 2 | POST /trigger/{workflow_id}; GET /health |
| prefs_routes.py | 2 | GET /{key}; PUT /{key} |
| stt_routes.py | 2 | GET /stats; POST /transcribe |
| admin_wipe_routes.py | 1 | DELETE /wipe/{kind} |
| cleanup_routes.py | 1 | GET /preview |
| emoji_routes.py | 1 | GET /{code}.svg |
| font_routes.py | 1 | GET /custom |
| observer_routes.py | 1 | GET /drift |
| _validators.py | 0 |  |
| chat_helpers.py | 0 |  |
| chatgpt_subscription_routes.py | 0 |  |
| cookbook_helpers.py | 0 |  |
| cookbook_output.py | 0 |  |
| copilot_routes.py | 0 |  |
| document_helpers.py | 0 |  |
| email_helpers.py | 0 |  |
| email_pollers.py | 0 |  |
| gallery_helpers.py | 0 |  |
| killswitch_routes.py | 0 |  |

**Total endpoints: 487**

## Modules src/

| Module | Description |
|---|---|
| action_intents.py | Lightweight routing hints for chat requests that need tools. |
| agent_loop.py | Compatibility wrapper — re-exports from archive/legacy/agent_loop.py. |
| agent_runs.py | Detached agent-run manager. |
| agentseal_runner.py |  |
| ai_interaction.py |  |
| api_key_manager.py |  |
| app_helpers.py |  |
| app_initializer.py | Initialize all application components and dependencies. |
| assistant_log.py |  |
| auth_helpers.py | Shared auth helpers used by all route files. |
| autoeval_loop.py |  |
| bg_jobs.py | Background job execution for the agent's `bash` tool. |
| bg_monitor.py | Always-on monitor that auto-continues the agent when a background job |
| budget_enforcer.py |  |
| builtin_actions.py |  |
| builtin_mcp.py |  |
| caldav_sync.py | CalDAV → local SQLite sync. |
| caldav_writeback.py | CalDAV write-back: push local create/update/delete out to the remote (#800). |
| cbm_client.py |  |
| channel_bootstrap.py | channel_bootstrap.py — wake the dormant Discord/Telegram adapters (M3.5). |
| channel_gateway.py |  |
| chat_handler.py | Handler for chat endpoint operations. |
| chat_helpers.py | URL extraction, message/upload validation, request parsing. |
| chat_processor.py |  |
| chatgpt_subscription.py | ChatGPT subscription / Codex backend OAuth helpers. |
| chroma_client.py |  |
| cleanup_service.py |  |
| command_validator.py |  |
| config.py |  |
| constants.py | Application-wide constants and configuration values. |
| content_security.py | SFD §5.20 + §5.13 — Sécurité contenus + Découverte outils. |
| context_budget.py | Adaptive input-token budget for the agent loop (#1170). |
| context_compactor.py |  |
| cookbook_serve_lifecycle.py | Cookbook serve lifecycle: kills scheduler-owned serves whose end-of- |
| copilot.py | GitHub Copilot provider support. |
| data_classification.py | SFD §5.19 — Classification et rétention des données. |
| database.py |  |
| decision_engine.py |  |
| deep_research.py |  |
| docling_runtime.py | Helpers for the optional Docling document-processing dependency. |
| document_actions.py |  |
| document_processor.py | Document processing: PDF/OCR extraction, text file handling, image VL analysis, user content buildin |
| durable_execution.py | SFD §5.5 — Exécution durable. |
| email_thread_parser.py |  |
| embedding_lanes.py |  |
| embeddings.py |  |
| endpoint_resolver.py | Unified endpoint resolution for all backend services. |
| event_bus.py |  |
| exceptions.py | Backward-compatible shim — the single source of truth is core/exceptions.py. |
| generated_images.py |  |
| goal_based_extractor.py |  |
| governance.py |  |
| hash_edit_validator.py |  |
| integrations.py |  |
| intent_gate.py |  |
| killswitch_registry.py | Read-only registry of odysseus kill-switches. |
| llm_core.py | Compatibility wrapper — re-exports from archive/legacy/llm_core.py. |
| markitdown_runtime.py | Helpers for the optional markitdown document-extraction dependency. |
| mcp_manager.py |  |
| mcp_oauth.py | mcp_oauth.py — generic OAuth for remote (Streamable HTTP) MCP servers. |
| memory.py |  |
| memory_impact.py | SFD §5.27 — P19: Memory Impact Verification. |
| memory_provider.py | Memory provider interfaces for native and external memory systems. |
| memory_vector.py |  |
| memory_writer.py |  |
| model_context.py |  |
| model_discovery.py |  |
| observer.py |  |
| office_doc.py | Auto-create a Document row from an Office attachment. |
| opencode_bridge.py | Odysseus <-> AgentOS Engine Bridge. |
| opencode_client.py |  |
| opencode_engine.py |  |
| optional_deps.py | Compatibility helpers for optional third-party dependencies. |
| output_router.py | SFD §5.18 — Modalités de sortie et visualisation. |
| pdf_form_doc.py | Bridge between extracted PDF form fields and the document editor. |
| pdf_forms.py | PDF AcroForm field detection and extraction. |
| pdf_runtime.py | Small helpers for optional PDF runtime dependencies. |
| perf_profiler.py | Performance Profiler — hooks into SSE metrics for live performance tracking. |
| personal_docs.py |  |
| planning_engine.py | SFD §5.3 — Planification intelligente avec décomposition arborescente. |
| preferences.py | SFD §5.15 — Système de préférences utilisateur structurées. |
| preset_manager.py |  |
| progressive_disclosure.py | SFD §5.26 — P5: Progressive Disclosure. |
| project_manifest.py |  |
| prompt_security.py | Prompt-injection hardening helpers. |
| provenance_memory.py | SFD §5.7 — Mémoire avec provenance. |
| rag_manager.py |  |
| rag_singleton.py |  |
| rag_vector.py |  |
| rate_limiter.py | Generic in-memory rate limiter — sliding window, keyed by IP. |
| readiness.py | Ithaca anchor — local-instance readiness / integrity self-check. |
| reminder_personas.py | Server-side mirror of the built-in characters used for reminder synthesis. |
| request_models.py |  |
| research_handler.py | Handler for research service integration with expandable UI support. |
| research_utils.py | Shared utilities for the deep research system. |
| risk_classifier.py |  |
| runtime_paths.py | Helpers for resolving runtime paths in source and frozen builds. |
| secret_storage.py |  |
| serena_client.py |  |
| service_health.py | Consolidated service health / degraded-state reporting. |
| session_actions.py |  |
| session_search.py | Shared session transcript search for UI and agent tools. |
| settings.py | Centralized settings and features management. |
| settings_scrub.py | Secret-scrubbing for settings exposed to non-admin / unauthenticated callers. |
| sse_indicators.py | Pure builders for live-indicator SSE events. |
| task_endpoint.py | Shared resolver for background-task AI endpoints. |
| task_scheduler.py | Background scheduler for ScheduledTask execution. |
| teacher_escalation.py | Teacher-escalation loop for self-hosted models in agent mode. |
| text_helpers.py | Text-cleanup helpers shared across LLM-output paths. |
| tls_overrides.py | Extended TLS trust store for private-CA LLM providers. |
| tool_execution.py |  |
| tool_implementations.py |  |
| tool_index.py |  |
| tool_parsing.py |  |
| tool_policy.py | Per-turn tool policy composition for agent execution. |
| tool_registry.py | Central Tool Registry — every tool is a modular brick. |
| tool_schemas.py |  |
| tool_security.py | Server-side tool safety policy. |
| tool_utils.py |  |
| topic_analyzer.py |  |
| trace_writer.py |  |
| upload_handler.py |  |
| upload_limits.py | Small helpers for route-local upload size caps. |
| url_safety.py | Outbound URL safety checks (SSRF hardening). |
| url_security.py | URL validation helpers for server-side outbound requests. |
| user_time.py | Per-request user-local time helpers. |
| visual_report.py |  |
| webhook_manager.py | Outgoing webhook manager — fires HTTP POSTs when events happen. |
| youtube_handler.py | Compatibility wrapper for the canonical services.youtube.youtube_handler module. |
| zen_router.py |  |

**Total modules src/: 130**

## Services (services/)

| Service | .py | README |
|---|---|---|
| acontext | 1 | non |
| code | 2 | non |
| docs | 2 | non |
| documents | 2 | non |
| hwfit | 6 | non |
| memory | 11 | non |
| notifications | 2 | non |
| observability | 3 | non |
| pipelines | 4 | non |
| research | 3 | non |
| search | 10 | non |
| security | 2 | non |
| shell | 2 | non |
| stt | 2 | non |
| tts | 2 | non |
| vector | 2 | non |
| youtube | 2 | non |

## Serveurs MCP

- `email_server.py`
- `graphify_mcp.py`
- `image_gen_server.py`
- `memory_server.py`
- `obsidian_mcp.py`
- `rag_server.py`

## Packages npm (@agentos)

- **sfd-classify** — SFD Classification — intent classification, event routing, content categorization
- **sfd-discovery** — SFD Discovery — service registry, endpoint probing, connector detection
- **sfd-durable** — SFD Durable Execution — idempotent step tracking with saga compensation (vérifié : `async compensate(id)` dans `packages/sfd-durable/src/index.ts`). **Le port Python `src/durable_execution.py` ne l'implémente pas** : crochet câblé, jamais armé, action non exécutée (v11 §1). Ne pas confondre les deux ports.
- **sfd-eventbus** — SFD Central Event Bus — 15 families, 62 events, covers all 4 master reference files
- **sfd-heartbeat** — SFD Heartbeat — health checking, uptime tracking, alerting
- **sfd-memory** — SFD Memory — vector memory store with provenance tracking and consolidation hooks
- **sfd-phase** — SFD Phase Manager — phase lifecycle, transitions, validation, rollback
- **sfd-prefs** — SFD Preferences — user preference management with layered resolution and MVP override
- **sfd-security** — SFD Security — content policy enforcement, injection detection, permission gating
- **sfd-visual** — SFD Visual Output — diagrams, reports, mockups via Kroki/SVG/PNG/HTML

## Agents .opencode (20)

- `auto-evolve` — SFD Auto-Evolution — researches best skills/plugins/services, creates custom solutions when none exist. Runs a
- `build` — >
- `constitution` — >
- `debate-5-personas` — >
- `design-extract` — >
- `edge-case-gen` — >
- `executor` — SFD Executor — écrit le code, exécute les commandes, crée les fichiers
- `explore` — Fast agent for codebase exploration. Use when you need to find files by patterns (eg. "src/components/**/*.tsx
- `gsd-debugger` — Performs systematic debugging using scientific method — isolation, hypothesis testing, root cause analysis.
- `gsd-executor` — Executes phase plans step by step with atomic commits and checkpoint protocol on failure.
- `gsd-planner` — Creates phase plans from goals, breaks work into atomic tasks using goal-backward analysis.
- `gsd-researcher` — Researches implementation approach before planning, producing a RESEARCH.md consumed by gsd-planner.
- `gsd-roadmapper` — Maintains ROADMAP.md with phase breakdown, coverage validation, and consistency checks against STATE.md.
- `gsd-verifier` — Verifies phase goal achievement using goal-backward analysis, not just task completion checklist.
- `open-design` — >
- `plan` — >
- `planner` — SFD Planner — décompose les objectifs en tâches, estime les tokens, assigne les agents
- `reviewer` — SFD Reviewer — audite le code, vérifie la qualité, détecte les vulnérabilités. TDD checklist + comment quality
- `security-audit` — >
- `sfd-orchestrator` — SFD Orchestrator — décompose un projet en phases, spawn les bons agents par phase avec le bon modèle

## Skills

- `.opencode/skills/auto-evolve`
- `.opencode/skills/sfd-decision-tree`
- `.opencode/skills/sfd-pipeline`
- `skills/deploy-vps`
- `skills/durability-testing`
- `skills/e2e-workflow`
- `skills/i18n-scanner`
- `skills/k6-load-testing`
- `skills/monitoring-setup`
- `skills/multi-agent-orchestration`
- `skills/pa11y-accessibility`
- `skills/perf-testing`
- `skills/performance-profiling`
- `skills/visual-output`

## Kill-switches

**Total: 47**

```
ODYSSEUS_AGENTSEAL, ODYSSEUS_AGENT_CATALOG, ODYSSEUS_AGENT_CONSTITUTION, ODYSSEUS_AGENT_DEBATE, ODYSSEUS_AGENT_DEBUGGER, ODYSSEUS_AGENT_DESIGN_EXTRACT, ODYSSEUS_AGENT_EDGECASE, ODYSSEUS_AGENT_EXECUTOR, ODYSSEUS_AGENT_OPEN_DESIGN, ODYSSEUS_AGENT_PLANNER, ODYSSEUS_AGENT_RESEARCHER, ODYSSEUS_AGENT_ROADMAPPER, ODYSSEUS_AGENT_SECURITY, ODYSSEUS_AGENT_VERIFIER, ODYSSEUS_AUTOEVAL, ODYSSEUS_AUTOEVOLVE, ODYSSEUS_BROWSER_HARNESS, ODYSSEUS_CBM, ODYSSEUS_CHANNEL_AGENT_REPLY, ODYSSEUS_CHECKPOINT, ODYSSEUS_CODEBURN, ODYSSEUS_DEEPEVAL, ODYSSEUS_DESTRUCTIVE_GATE, ODYSSEUS_DISABLE_MCP, ODYSSEUS_DOCLING, ODYSSEUS_GOVERNANCE_ANCESTRY, ODYSSEUS_GRAPHIFY, ODYSSEUS_INPROCESS_DISCORD, ODYSSEUS_INPROCESS_TELEGRAM, ODYSSEUS_LANGFUSE, ODYSSEUS_LANGGRAPH, ODYSSEUS_LANGGRAPH_INTERRUPT, ODYSSEUS_LIVE_ORCHESTRATION, ODYSSEUS_MEMORY_IMPACT, ODYSSEUS_MODEL_ROUTER, ODYSSEUS_N8N, ODYSSEUS_OBSIDIAN_MCP, ODYSSEUS_PHASE_TRACKER, ODYSSEUS_PLAYWRIGHT, ODYSSEUS_PROGRESSIVE_DISCLOSURE, ODYSSEUS_RRF_FUSION, ODYSSEUS_SERENA_MCP, ODYSSEUS_SUPABASE, ODYSSEUS_TREESITTER, ODYSSEUS_UNIFIED_TOKENS, ODYSSEUS_VAULTWARDEN, ODYSSEUS_ZEN_FROM_ENDPOINT
```

## Tests

- Fichiers `tests/test_*.py`: 665
- Entrées `tests/`: 682
