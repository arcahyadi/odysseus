# Traçabilité SFD v3.1 ↔ Code — vérifiable

*Table de kill-switchs **générée** par `tools/gen_killswitch_tables.py` — rejouer `python tools/gen_killswitch_tables.py` après toute modification du registre.*

## 1. Modules SFD (§5.1→§5.20) → implémentation (existence vérifiée)

| Module SFD | Fichiers présents | Kill-switch (défaut) | Tests~ |
|---|---|---|---|
| §5.1 Décision multi-agent & orchestration | 4/4 · ✅ | `ODYSSEUS_LIVE_ORCHESTRATION`=off, `ODYSSEUS_PHASE_TRACKER`=on 🔒P0, `ODYSSEUS_AGENT_CATALOG`=off | 14 |
| §5.2 Ingénierie du contexte | 3/3 · ✅ | — | 8 |
| §5.3 Planification intelligente | 2/2 · ✅ | `ODYSSEUS_PLANNING_ENGINE`=off | 0 |
| §5.4 Exécution contrôlée/sécurisée | 3/3 · ✅ | `ODYSSEUS_DESTRUCTIVE_GATE`=on | 0 |
| §5.5 Exécution durable | 2/2 · ✅ | `ODYSSEUS_DURABLE_EXECUTION`=on 🔒P0, `ODYSSEUS_CHECKPOINT`=on 🔒P0 | 0 |
| §5.6 Routage modèles | 3/3 · ✅ | `ODYSSEUS_MODEL_ROUTER`=on 🔒P0, `ODYSSEUS_ZEN_FROM_ENDPOINT`=off | 0 |
| §5.7 Mémoire boucle fermée | 5/5 · ✅ | `ODYSSEUS_PROVENANCE_MEMORY`=on 🔒P0, `ODYSSEUS_OBSIDIAN_MCP`=off, `ODYSSEUS_MEMORY_IMPACT`=on 🔒P0 | 0 |
| §5.8 Communication multi-canal | 2/2 · ✅ | `ODYSSEUS_INPROCESS_DISCORD`=off ⚠️non câblé, `ODYSSEUS_INPROCESS_TELEGRAM`=off ⚠️non câblé, `ODYSSEUS_CHANNEL_AGENT_REPLY`=off ⚠️non câblé | 0 |
| §5.9 Gouvernance & budgets | 3/3 · ✅ | `ODYSSEUS_GOVERNANCE_ANCESTRY`=off | 5 |
| §5.10 Auto-évaluation & qualité | 1/1 · ✅ | `ODYSSEUS_AUTOEVAL`=on 🔒P0, `ODYSSEUS_AUTOEVOLVE`=on 🔒P0, `ODYSSEUS_DEEPEVAL`=off ⚠️non câblé | 0 |
| §5.11 Observabilité | 3/3 · ✅ | `ODYSSEUS_LANGFUSE`=off, `ODYSSEUS_CODEBURN`=off, `ODYSSEUS_UNIFIED_TOKENS`=on 🔒P0 | 0 |
| §5.12 Workspaces & worktrees | natif OpenCode | — | 0 |
| §5.13 Extensibilité & MCP | 4/4 · ✅ | `ODYSSEUS_DISABLE_MCP`=off, `ODYSSEUS_CBM`=off, `ODYSSEUS_GRAPHIFY`=off, `ODYSSEUS_SERENA_MCP`=off | 13 |
| §5.14 Config intégrale versionnée | 2/2 · ✅ | — | 0 |
| §5.15 Préférences utilisateur | 2/2 · ✅ | `ODYSSEUS_PREFERENCES`=on 🔒P0 | 0 |
| §5.16 Recherche conversations | 1/1 · ✅ | — | 0 |
| §5.17 Système de skills | 3/3 · ✅ | — | 16 |
| §5.18 Sortie visuelle | 3/3 · ✅ | `ODYSSEUS_OUTPUT_ROUTER`=on 🔒P0 | 0 |
| §5.19 Classification & rétention | 2/2 · ✅ | `ODYSSEUS_DATA_CLASSIFICATION`=on 🔒P0 | 4 |
| §5.20 Sécurité des contenus | 4/4 · ✅ | `ODYSSEUS_CONTENT_SECURITY`=on 🔒P0, `ODYSSEUS_PROGRESSIVE_DISCLOSURE`=on 🔒P0 | 0 |

## 2. Kill-switches (registre vérifiable)

<!-- gen:killswitchs:begin -->
| Catégorie | Env var | Défaut code | Effectif | Câblé | Lecteur |
|---|---|---|---|---|---|
| Agents | `ODYSSEUS_AGENT_CATALOG` | `off` | `off` | oui | `core/startup.py:278` |
| Agents | `ODYSSEUS_AGENT_CONSTITUTION` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_DEBATE` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_DESIGN_EXTRACT` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_EDGECASE` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_DEBUGGER` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_EXECUTOR` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_PLANNER` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_RESEARCHER` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_ROADMAPPER` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_VERIFIER` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_OPEN_DESIGN` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Agents | `ODYSSEUS_AGENT_SECURITY` | `off` | `off` | oui | `src/orchestrator/agent_dispatcher.py` |
| Channels | `ODYSSEUS_CHANNEL_AGENT_REPLY` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| Channels | `ODYSSEUS_INPROCESS_DISCORD` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| Channels | `ODYSSEUS_INPROCESS_TELEGRAM` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| Channels | `ODYSSEUS_APPRISE` | `off` | `off` | oui | `src/channel_gateway.py:78` |
| Code Parsing | `ODYSSEUS_TREESITTER` | `off` | `off` | oui | `src/agent_tools/filesystem_tools.py:16` |
| Document Processing | `ODYSSEUS_DOCLING` | `off` | `off` | oui | `src/docling_runtime.py:30` |
| Governance/Memory | `ODYSSEUS_AUTOEVAL` | `on` | `on` | oui | `src/orchestrator/autoeval.py:45` |
| Governance/Memory | `ODYSSEUS_AUTOEVAL_ALLOW_RESET` | `off` | `off` | oui | `src/orchestrator/autoeval.py:62` |
| Governance/Memory | `ODYSSEUS_AUTOEVOLVE` | `on` | `on` | oui | `src/orchestrator/autoevolve.py:18` |
| Governance/Memory | `ODYSSEUS_CHECKPOINT` | `on` | `on` | oui | `src/orchestrator/checkpoint_tracker.py:39` |
| Governance/Memory | `ODYSSEUS_CODEBURN` | `off` | `off` | oui | `src/orchestrator/codeburn_runner.py:26` |
| Governance/Memory | `ODYSSEUS_CONTENT_SECURITY` | `on` | `on` | oui | `src/content_security.py:24` |
| Governance/Memory | `ODYSSEUS_DATA_CLASSIFICATION` | `on` | `on` | oui | `src/data_classification.py:28` |
| Governance/Memory | `ODYSSEUS_DURABLE_EXECUTION` | `on` | `on` | oui | `src/durable_execution.py:32` |
| Governance/Memory | `ODYSSEUS_GOVERNANCE_ANCESTRY` | `off` | `off` | oui | `src/orchestrator/ancestry_tracker.py:26` |
| Governance/Memory | `ODYSSEUS_LANGFUSE` | `off` | `off` | oui | `services/observability/langfuse_tracer.py:38` |
| Governance/Memory | `ODYSSEUS_LETTA` | `off` | `off` | oui | `services/memory/letta_provider.py:54` |
| Governance/Memory | `ODYSSEUS_MEM0` | `off` | `off` | oui | `services/memory/mem0_provider.py:54` |
| Governance/Memory | `ODYSSEUS_MEMORY_IMPACT` | `on` | `on` | oui | `src/memory_impact.py:28` |
| Governance/Memory | `ODYSSEUS_OUTPUT_ROUTER` | `on` | `on` | oui | `src/output_router.py:30` |
| Governance/Memory | `ODYSSEUS_PREFERENCES` | `on` | `on` | oui | `src/preferences.py:41` |
| Governance/Memory | `ODYSSEUS_PROGRESSIVE_DISCLOSURE` | `on` | `on` | oui | `src/progressive_disclosure.py:27` |
| Governance/Memory | `ODYSSEUS_PROVENANCE_MEMORY` | `on` | `on` | oui | `src/provenance_memory.py:40` |
| Governance/Memory | `ODYSSEUS_UNIFIED_TOKENS` | `on` | `on` | oui | `src/trace_writer.py:146` |
| MCP/Services | `ODYSSEUS_AGENTSEAL` | `off` | `off` | oui | `src/agentseal_runner.py:82` |
| MCP/Services | `ODYSSEUS_BROWSER_HARNESS` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| MCP/Services | `ODYSSEUS_CBM` | `off` | `off` | oui | `src/cbm_client.py:24` |
| MCP/Services | `ODYSSEUS_TOOL_DISCOVERY` | `off` | `off` | oui | `src/content_security.py:112` |
| MCP/Services | `ODYSSEUS_DISABLE_MCP` | `off` | `off` | oui | `src/builtin_mcp.py:90` |
| MCP/Services | `ODYSSEUS_REMOTE_SSH` | `off` | `off` | oui | `src/builtin_actions.py:381` |
| MCP/Services | `ODYSSEUS_SCRIPT_HOST` | `off` | `off` | oui | `src/builtin_actions.py:394` |
| MCP/Services | `ODYSSEUS_GRAPHIFY` | `off` | `off` | oui | `src/builtin_mcp.py:108` |
| MCP/Services | `ODYSSEUS_OBSIDIAN_MCP` | `off` | `off` | oui | `src/builtin_mcp.py:99` |
| MCP/Services | `ODYSSEUS_PREFECT` | `off` | `off` | oui | `services/pipelines/maintenance_pipeline.py:19` |
| MCP/Services | `ODYSSEUS_PLAYWRIGHT` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| MCP/Services | `ODYSSEUS_OPA` | `off` | `off` | oui | `services/security/opa_client.py:23` |
| MCP/Services | `ODYSSEUS_SERENA_MCP` | `off` | `off` | oui | `src/serena_client.py:25` |
| MCP/Services | `ODYSSEUS_SUPABASE` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| MCP/Services | `ODYSSEUS_VAULTWARDEN` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| MCP/Services | `ODYSSEUS_ZEN_FROM_ENDPOINT` | `off` | `off` | oui | `src/zen_router.py:130` |
| MCP/Services | `ODYSSEUS_N8N` | `off` | `off` | oui | `routes/n8n_routes.py:27` |
| Orchestration | `ODYSSEUS_DESTRUCTIVE_GATE` | `on` | `on` | oui | `src/orchestrator/gate.py:26` |
| Orchestration | `ODYSSEUS_MULTI_AGENT` | `off` | `off` | oui | `archive/legacy/agent_loop.py:3025` |
| Orchestration | `ODYSSEUS_LANGGRAPH_INTERRUPT` | `on` | `on` | oui | `src/orchestrator/langgraph_loop.py:805` |
| Orchestration | `ODYSSEUS_LANGGRAPH` | `off` | `off` | oui | `src/orchestrator/langgraph_loop.py:42` |
| Orchestration | `ODYSSEUS_LIVE_ORCHESTRATION` | `off` | `off` | oui | `archive/legacy/agent_loop.py:2933` |
| Orchestration | `ODYSSEUS_MODEL_ROUTER` | `on` | `on` | oui | `src/orchestrator/router_advice.py:42` |
| Orchestration | `ODYSSEUS_PLANNING_ENGINE` | `off` | `off` | oui | `src/planning_engine.py:27` |
| Orchestration | `ODYSSEUS_PHASE_TRACKER` | `on` | `on` | oui | `src/orchestrator/phase_tracker.py:23` |
| Quality | `ODYSSEUS_DEEPEVAL` | `off` | `off` | **NON** | `(aucun lecteur dans le code)` |
| Quality | `ODYSSEUS_OTEL` | `on` | `on` | oui | `services/observability/otel_setup.py:39` |
| RAG | `ODYSSEUS_QDRANT` | `off` | `off` | oui | `src/memory_vector.py:29` |
| RAG | `ODYSSEUS_RRF_FUSION` | `off` | `off` | oui | `src/rag_vector.py:86` |
| RAG | `ODYSSEUS_MEILISEARCH` | `off` | `off` | oui | `services/search/meilisearch_client.py:21` |

**67 descripteurs · 17 ON par défaut · 8 non câblés · 14/14 P0 à `on`.**

- 🔒P0 = bascule à `on` par le **Palier 0** (2026-09-26), sur les 14 principes cœur.
- ⚠️non câblé = aucun lecteur dans le code. Le registre l'affiche `off` et `wired=False` : il ne peut **pas** se présenter comme actif. Ces 9 descripteurs étaient présentés comme `on` avant le 2026-09-26.
- « Effectif » = valeur lue après application de `.env` (`is_default=False` ⇒ surcharge).
<!-- gen:killswitchs:end -->

> La table ci-dessus est la **source unique** de l'état des kill-switchs. Elle est régénérée depuis `src/killswitch_registry.py` : toute valeur écrite à la main ici serait périmée au prochain changement de registre.
