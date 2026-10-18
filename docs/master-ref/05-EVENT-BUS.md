# Event Bus Central — Spécification

> **Couverture :** 01-SFD-v3.1 (25 principes, 22 modules) + 02-OUTILS-TIERS (60 outils, 5 couches) + 03-OBJECTIFS (plugins, bridge) + 04-COUVERTURE (8 axes)
> **Principe :** Chaque action, chaque décision, chaque erreur émet un événement structuré. Rien n'est invisible.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       EVENT BUS CENTRAL                           │
│                                                                   │
│  SOURCES (15 familles)         CONSOMMATEURS (6)                  │
│  ─────────────────────         ────────────────                    │
│  phase      ──┐                ┌──→ Cockpit UI                    │
│  tool       ──┤                ├──→ Chat UI (agent/tool blocks)  │
│  agent      ──┤                ├──→ Traces JSONL (audit)          │
│  model      ──┤   EVENT BUS    ├──→ LangFuse (métriques)          │
│  memory     ──┤   =========    ├──→ Plugins SFD (réactions)       │
│  budget     ──┤                └──→ Alertes (ntfy/email)          │
│  security   ──┤                                                   │
│  workflow   ──┤                                                   │
│  discovery  ──┤                                                   │
│  search     ──┤                                                   │
│  session    ──┤                                                   │
│  system     ──┤                                                   │
│  user       ──┤                                                   │
│  preference ──┤                                                   │
│  mcp        ──┘                                                   │
│                                                                   │
│  FORMAT : { event_id, timestamp, source, type, data, trace_id }  │
│  TRANSPORT : SSE (UI) + JSONL (audit) + WebSocket (plugins)      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Couverture Complète — 15 Familles, 62 Types d'Événements

### 1. PHASE (SFD §5.1-5.4, Axe 1)

| Événement | Source SFD | Données |
|-----------|-----------|---------|
| `phase_enter` | §5.4.2 Phase-lock | phase, index, total, risk_level |
| `phase_exit` | §5.4.2 | phase, duration_ms, decisions_made |
| `phase_skip` | §5.1.2 | phase, reason (not needed) |
| `phase_error` | §5.4 | phase, error, stack |

### 2. TOOL (SFD §5.13, Axe 3, Outils Couches 2-4)

| Événement | Source | Données |
|-----------|--------|---------|
| `tool_start` | Tout outil | tool_name, args_preview, phase |
| `tool_output` | Tout outil | tool_name, exit_code, output_preview, duration_ms |
| `tool_error` | Tout outil | tool_name, error, retry_attempt |
| `tool_blocked` | §5.4.2, §5.20 | tool_name, reason (phase-lock/security) |
| `tool_retry` | §5.5.2 | tool_name, attempt, max_attempts, backoff_ms |

### 3. AGENT (SFD §5.1, Axe 1, .opencode/agents)

| Événement | Source | Données |
|-----------|--------|---------|
| `agent_spawn` | AgentDispatcher | agent_name, phase, model, tools |
| `agent_result` | Fin d'exécution | agent_name, status, tokens_used, cost |
| `agent_error` | Erreur agent | agent_name, error, phase |
| `agent_dispatch` | Orchestrateur | agents_list, phase, reason |
| `agent_sub_spawn` | Sub-agent créé | parent_agent, child_agent, task |

### 4. MODEL (SFD §5.6, Axe 3, ZenRouter)

| Événement | Source | Données |
|-----------|--------|---------|
| `model_selected` | ZenRouter | model, tier, reason (complexity score) |
| `model_fallback` | Fallback chain | from_model, to_model, reason |
| `model_error` | Échec appel | model, status_code, error |
| `model_metrics` | Fin de réponse | model, tokens_in, tokens_out, duration_ms, tok/s |

### 5. MEMORY (SFD §5.7, Axe 7, @agentos/sfd-memory)

| Événement | Source | Données |
|-----------|--------|---------|
| `memory_read` | MemoryOperations | path, entries_count |
| `memory_write` | MemoryOperations | path, tag ([stated]/[observed]/[inferred]) |
| `memory_omitted` | OmissionFilter | content_preview, reason (protected/sensitive) |
| `memory_conflict` | Version mismatch | path, expected_version, actual_version |
| `memory_classified` | Classification | path, retention_level |

### 6. BUDGET (SFD §5.9, Axe 6)

| Événement | Source | Données |
|-----------|--------|---------|
| `budget_updated` | BudgetEnforcer | tokens_used, cost, percent |
| `budget_warning` | Seuil dépassé | threshold_pct, current_pct |
| `budget_exceeded` | Hard stop | limit, current, project_id |

### 7. SECURITY (SFD §5.20, Outils Couche 4)

| Événement | Source | Données |
|-----------|--------|---------|
| `injection_detected` | InjectionGuard | source (memory file), pattern_matched |
| `content_blocked` | OutputFilter | category (violence/copyright/...), preview |
| `destructive_blocked` | DestructiveGate | command, reason |
| `permission_denied` | Phase-lock | tool, phase, required_permission |

### 8. WORKFLOW (SFD §5.5, @agentos/sfd-durable)

| Événement | Source | Données |
|-----------|--------|---------|
| `workflow_start` | DurableEngine | workflow_id, name, activities_count |
| `workflow_step_complete` | Activity done | activity_id, attempt, duration_ms |
| `workflow_step_retry` | Retry | activity_id, attempt, delay_ms |
| `workflow_saga_compensate` | Saga trigger | failed_activity, compensated_count |
| `workflow_approval_needed` | Signal | signal_id, message, timeout_days |
| `workflow_approval_resolved` | Signal répondu | signal_id, approved, response |

### 9. DISCOVERY (SFD §5.13.4, @agentos/sfd-discovery)

| Événement | Source | Données |
|-----------|--------|---------|
| `discovery_search` | tool_search | query, results_count |
| `registry_found` | search_mcp_registry | service_name, is_third_party |
| `connector_suggested` | suggest_connectors | connectors_list |
| `connector_connected` | Connexion établie | service_name, transport |

### 10. SEARCH (SFD §5.16, conversation_search)

| Événement | Source | Données |
|-----------|--------|---------|
| `signal_detected` | LinguisticSignalDetector | signal_type, matched_text |
| `conversation_search` | Recherche lancée | query, results_count |
| `past_context_loaded` | Contexte rappelé | session_id, snippet |

### 11. SESSION (SFD §5.12, Axe 1)

| Événement | Source | Données |
|-----------|--------|---------|
| `session_created` | Nouvelle session | session_id, project_id |
| `session_compacted` | Compaction | tokens_before, tokens_after |
| `session_saved` | Sauvegarde | message_count |
| `session_error` | Erreur session | error |

### 12. SYSTEM (SFD §5.11, Axe 5)

| Événement | Source | Données |
|-----------|--------|---------|
| `startup` | app.py | version, services_status |
| `shutdown` | app.py | uptime_seconds |
| `health_change` | Health check | service, old_status, new_status |
| `error` | Toute erreur non catchée | error, traceback |

### 13. USER (SFD §5.15, Axe 8)

| Événement | Source | Données |
|-----------|--------|---------|
| `message_sent` | Chat POST | message_preview, mode (chat/agent) |
| `preference_updated` | Preferences | preference_type, rule |
| `preference_blocked` | Guardrail | rule, reason |
| `feedback_given` | User feedback | rating, comment |

### 14. PREFERENCE (SFD §5.15, @agentos/sfd-prefs)

| Événement | Source | Données |
|-----------|--------|---------|
| `prefs_loaded` | PreferenceEngine | count, source |
| `prefs_resolved` | Resolution | priority_level, winning_rule |
| `prefs_injected` | System prompt | keys_injected |

### 15. MCP (SFD §5.13, Outils Couche 2)

| Événement | Source | Données |
|-----------|--------|---------|
| `mcp_connected` | McpManager | server_id, transport, tools_count |
| `mcp_disconnected` | McpManager | server_id, reason |
| `mcp_tool_registered` | Nouvel outil | server_id, tool_name |
| `mcp_error` | Erreur MCP | server_id, error |

---

## Modularité

Le bus est un **plugin** OpenCode (@agentos/sfd-eventbus) :
- Chaque module émet via `bus.emit(source, type, data)`
- Les consommateurs s'abonnent via `bus.on(type, handler)`
- Transport : SSE pour l'UI, JSONL pour l'audit, WebSocket pour les plugins
- Filtrage par session, projet, type
- Buffering pour les consommateurs lents

```typescript
// Exemple d'émission
bus.emit("tool", "tool_start", {
  tool_name: "BASH",
  args_preview: "pip install fastapi",
  phase: "BUILD",
  session_id: "abc",
  trace_id: "xyz"
});

// Exemple d'abonnement
bus.on("phase_enter", (event) => {
  cockpit.update({ phase: event.data.phase, index: event.data.index });
});
```

---

## Couverture par Fichier Maître

| Fichier | Événements couverts |
|---------|-------------------|
| 01-SFD-v3.1 | 22/22 principes → 62 événements |
| 02-OUTILS-TIERS | 5 couches → events discovery, mcp, tool |
| 03-OBJECTIFS | Architecture → events session, system, bridge |
| 04-COUVERTURE | 8 axes → events budget, phase, memory, agent |
