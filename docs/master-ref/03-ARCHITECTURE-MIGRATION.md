# Architecture & Migration — Odysseus → OpenCode Core

> ⚠️ **RÉVISÉ 2026-09-25 — réalité vérifiée.** La cible « élaguer Odysseus à ~50 fichiers / 15 routes » **n'a pas été atteinte** : le dépôt compte **63 fichiers de routes, 503 endpoints et 1 071 fichiers Python actifs** (seuls `agent_loop.py` et `llm_core.py` ont été déplacés dans `archive/legacy/`). Les chiffres de « réduction » ci-dessous sont des **cibles**, pas l'état réel. État réel : `../traceability/00-CODE-INVENTORY.md`.


**Date :** 2026-07-24 (design) → 2026-07-30 (exécution) | **Status :** En cours

---

## 1. Historique des décisions

| Date | Décision | Raison |
|------|----------|--------|
| 2026-07-22 | Audit Odysseus (171 fichiers Python) | `agent_loop.py` (3992 lignes) devenu ingérable, LLM core trop couplé |
| 2026-07-23 | Choix d'OpenCode comme moteur | Agents natifs, plugins npm, worktrees, compaction — tout déjà prêt |
| 2026-07-24 | **Big Bang** — migration en 1 commit | Pas de transition progressive : trop de dépendances croisées |
| 2026-07-24 | 7 plugins npm `@agentos/sfd-*` | Distribution indépendante, testable unitairement |
| 2026-07-24 | Bridge subprocess stdin/stdout | `opencode_bridge.py` → `asyncio.create_subprocess_exec` → OpenCode CLI |
| 2026-07-24 | Cockpit via SSE | Plugin `sfd-phase` émet JSON sur stdout → bridge → SSE → cockpit + chat UI |
| 2026-07-25 | Début exécution : suppression ~10 000 lignes Python | 23 fichiers/dossiers supprimés, 3 adaptés, 7 plugins créés |
| 2026-07-30 | Cible : Odysseus élagué — ~50 fichiers (**NON atteinte**) | Réel 2026-09 : **1 071 fichiers Python actifs** |

---

## 2. Architecture cible

```
Odysseus (Python/FastAPI) — couche mince (cible ~50 fichiers ; réel 2026-09 : 1 071 actifs)
  opencode_bridge.py → subprocess → OpenCode CLI (Node.js)
    stdin: message
    stdout: response + phase events → SSE → cockpit + chat UI
    stderr: logs

OpenCode CLI uses:
  - ZenRouter (model selection)
  - 16 agents (.opencode/agents/)
  - 8 MCP servers
  - 7 npm plugins (@agentos/sfd-*)
  - 2 skills (.opencode/skills/)
  - 1 custom tool (.opencode/tools/sfd-phase.ts)
  - Native worktrees, compaction, permissions

Services Docker (unchanged):
  ChromaDB, Kroki, Meilisearch, ntfy, SearXNG, Scrapling, Serena, LangFuse
```

---

## 3. Inventaire canonique KEEP / DELETE / ADAPT

### KEEP — composants gardés

| Composant | Lignes/Fichiers | Raison |
|-----------|-----------------|--------|
| FastAPI + SSE | 55 routes → 15 | Streaming live, socle parfait |
| Chat UI (static/) | 162 fichiers JS | SPA vanilla fonctionnelle |
| Cockpit | Phase bar, health, drift | Déjà adapté à OpenCode |
| Settings dashboard | Kill-switches, config | Réutilisable sans changement |
| Email/Calendar | IMAP/SMTP, CalDAV | Indépendant du moteur LLM |
| Docker Compose | 10 services, profils | Infrastructure inchangée |
| MCP Manager | 6 serveurs, 3 transports | Essentiel, gardé |
| Tool implementations | BASH, WRITE_FILE, WEB_SEARCH | Indépendantes du moteur |
| ZenRouter (concept) | — | Déjà natif dans OpenCode |
| `.opencode/` | agents, skills, tools, config | Cœur du nouveau système |
| `skills/` | 2 skills | SFD pipeline + decision tree |
| `tests/` | — | Adaptés au nouveau bridge |
| `scripts/` | — | Utilitaires de déploiement |
| `.github/workflows/` | — | CI/CD inchangée |
| `docker-compose.yml` | — | Services Docker |

### DELETE — composants supprimés

| Composant | Lignes | Raison |
|-----------|--------|--------|
| `src/agent_loop.py` | 3 992 | Cœur LLM remplacé par OpenCode Engine |
| `src/llm_core.py` | 2 520 | Streaming HTTP remplacé par ZenRouter natif |
| `src/zen_router.py` | 354 | Déjà natif dans OpenCode |
| `src/agent_pipeline.py` | ~200 | Remplacé par agents `.opencode/` |
| `src/full_system.py` | ~150 | Plus nécessaire |
| `src/mode_detector.py` | ~180 | Logique dans les agents |
| `src/plugin_system.py` | ~300 | Remplacé par plugins npm |
| `src/worktree_support.py` | ~120 | Natif dans OpenCode |
| `src/endpoint_resolver.py` | ~90 | Routing dans OpenCode |
| `src/sfd_wiring.py` | ~250 | SFD modules → plugins npm |
| `src/context_manager.py` | ~400 | Géré par compaction native |
| `src/agent_instructions.py` | ~150 | Dans `.opencode/agents/` |
| `src/service_connector.py` | ~100 | Plus nécessaire |
| `src/durable_execution/` | ~350 | → `@agentos/sfd-durable` |
| `src/memory_provenance/` | ~400 | → `@agentos/sfd-memory` |
| `src/preferences/` | ~200 | → `@agentos/sfd-prefs` |
| `src/visual_output/` | ~300 | → `@agentos/sfd-visual` |
| `src/classification/` | ~250 | → `@agentos/sfd-classify` |
| `src/content_security/` | ~200 | → `@agentos/sfd-security` |
| `src/tool_discovery/` | ~250 | → `@agentos/sfd-discovery` |
| `src/conversation_search/` | ~200 | Non essentiel |
| `src/multi_agent_decision/` | ~250 | Dans `.opencode/agents/` |
| `src/thought_bus/` | ~180 | Non essentiel |
| Cookbook | ~500 | Trop spécifique |
| Gallery | ~200 | Non essentiel |
| Deep Research | ~300 | Déjà dans OpenCode |
| ~40 routes | ~600 | Cible 55 → 15 routes (**réel 2026-09 : 63 fichiers de routes, 503 endpoints**) |
| **TOTAL supprimé** | **~12 300** | 23 fichiers/dossiers + 40 routes |

### ADAPT — composants modifiés

| Composant | Modification |
|-----------|-------------|
| `routes/chat_routes.py` | `stream_agent_loop` → `OpenCodeBridge.send_message()` |
| `app.py` | Supprimer init SFD, garder init Docker services |
| `Dockerfile` | Ajouter `RUN curl -fsSL https://opencode.ai/install | bash` |
| `routes/` (global) | 55 routes → 15 (chat, health, cockpit, settings, killswitches) |
| `static/` (Chat UI) | Brancher sur SSE du bridge au lieu de l'ancien stream |

---

## 4. 7 plugins npm

| Package | SFD Module | Hooks | Custom Tools |
|---------|-----------|-------|-------------|
| `@agentos/sfd-memory` | Memory Provenance | `session.created`, `tool.execute.after(write)` | `sfd-memory` |
| `@agentos/sfd-durable` | Durable Execution | `tool.execute.before/after(bash,write)` | — |
| `@agentos/sfd-prefs` | Preferences | `session.created` | — |
| `@agentos/sfd-visual` | Visual Output | — | `sfd-render` |
| `@agentos/sfd-classify` | Classification | `tool.execute.before(write)` | `sfd-forget` |
| `@agentos/sfd-security` | Content Security | `tool.execute.before(read)`, `session.updated` | — |
| `@agentos/sfd-discovery` | Tool Discovery | — | `sfd-discover` |

---

## 5. Statut actuel

| Tâche | Statut |
|-------|--------|
| Audit Odysseus (171 fichiers) | ✅ Terminé |
| Design migration (4 décisions) | ✅ Terminé |
| Suppression ~12 300 lignes Python | ⚠️ Partiel (in fine : 2 fichiers archivés) |
| Création des 7 plugins npm | ✅ Terminé |
| Bridge `opencode_bridge.py` | ✅ Terminé |
| Adaptation `chat_routes.py` | ✅ Terminé |
| Adaptation `app.py` | ✅ Terminé |
| Adaptation `Dockerfile` | ✅ Terminé |
| Réduction 55 → 15 routes | ❌ Non atteinte (63 routes) |
| Intégration Cockpit → SSE bridge | ✅ Terminé |
| Tests end-to-end bridge + plugins | 🔄 En cours |
| Documentation mise à jour | 🔄 En cours |
| Nettoyage routes résiduelles | ⬜ À faire |

---

## 6. Leçons apprises

1. **Big Bang était la bonne stratégie.** Les dépendances entre `agent_loop.py`, `llm_core.py`, et les modules SFD étaient trop profondes pour une migration progressive. Un commit unique a forcé la cohérence.

2. **Le bridge subprocess est plus fiable que prévu.** `stdin/stdout` comme protocole de communication entre Python et Node.js est simple, testable, et évite les problèmes de sérialisation complexes.

3. **Les plugins npm découplent parfaitement.** Chaque module SFD étant un package indépendant, les équipes peuvent itérer sans blocage. Les hooks OpenCode (`session.created`, `tool.execute.before/after`) couvrent tous les cas d'usage.

4. **~12 300 lignes supprimées (cible).** Réel : seuls `agent_loop.py`/`llm_core.py` archivés — voir `../traceability/00-CODE-INVENTORY.md`. Le passage de ~17 000 lignes Python à ~5 000 lignes (couche mince) + plugins npm a réduit la dette technique sans perte de fonctionnalités.

5. **Garder Odysseus comme couche UI était le bon choix.** Réécrire une UI en HTMX aurait coûté 3 semaines. Élaguer Odysseus a pris 3 jours.

6. **Les agents `.opencode/` remplacent élégamment le pipeline.** 16 agents spécialisés avec ZenRouter font mieux que `agent_pipeline.py` + `mode_detector.py` en termes de flexibilité et de testabilité.
