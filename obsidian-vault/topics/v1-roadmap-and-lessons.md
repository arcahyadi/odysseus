---
name: v1-roadmap-and-lessons
description: V1 delivery — lessons learned + roadmap V2 for AgentOS engine
sources: [engine]
updated: 2026-07-30
---

## V1 livré (2026-07-30)

- [observed] V1 engine bridge terminé — `docker/agentos-engine/engine_server.py` importe le VRAI `OpenCodeEngine.walk()` 7 phases, plus de placeholder asyncio.sleep. Testé en local + Docker (build `agentos-engine:v1`, SSE stream 29 events, [DONE], traces JSONL, memory [observed] dans vault).
- [observed] Mode agent était cassé à l'import — `src/opencode_engine.py:12` importait `EventBus`+`_event_bus` depuis `src.event_bus` (un module hétérogène, le bus lourd scheduler) alors que la classe était déjà définie in-file. Fix c86dda5.
- [observed] Cleanup Phase A: retrait 9 packages SFD vides (sfd-memory/durable/prefs/visual/classify/security/discovery/heartbeat/phase — tous coquilles avec `package.json` seul, pas d'`index.ts`). Stratégie V1 = minimal viable, on garde `sfd-eventbus` (vraie impl) et `sfd-phase` (custom tool dans `.opencode/tools/`).
- [observed] `trace_id` ajouté à l'EventBus (a50cf1d) — master-ref 05-EVENT-BUS impose ce champ pour corrélation cross-familles (UC-12 audit). `start_trace()` / `end_trace()` + propagation automatique.
- [observed] Doc: `docs/architecture/CODEBASE-MAP.md` régénérée avec chiffres réels (247 .py / 694 tests / 101 K lignes vs anciens 94 fichiers/223 tests).

## Tests V1 (prouvés)

- [observed] `tests/test_engine_bridge_e2e.py` — 5/5 PASS en 0.68s (test_health, test_status, test_run_agent_mode_7_phases, test_run_chat_mode_short_circuit, test_run_increments_runs_counter).
- [observed] Suite orchestrator + opencode + e2e_smoke étendue — 201/201 PASS en 18.84s, 0 fail sur le cœur SFD.
- [observed] Docker run 7 phases en ordre: CLASSIFY→KNOW→PLAN→BUILD→QUALITY→AUTOEVAL→MEMORY_OBSERVE avec `mode_detected: agent` sur "build a complete flask todo app with SQLite".
- [observed] Mode CHAT court-circuit: "bonjour comment ca va ?" → 1 phase_enter max (vs 7 en agent).

## Lessons V1 (SFD P6 — échecs répétés deviennent fonctionnalités du harnais)

- [inferred] Un import cassé `from src.event_bus import EventBus` dans `opencode_engine.py` rendait le mode agent inutiliable à l'import — silencieusement, parce que les tests e2e n'importaient pas ce module. Lesson: chaque phase BUILD doit faire `python -c "from src.opencode_engine import OpenCodeEngine"` comme smoke check. À ajouter dans le sfd-decision-tree skill.
- [inferred] `sfd-phase` tool MCP en mémoire garde l'état en `sessionPhases = new Map()` — perdu au redémarrage. Pour V2: persisted state dans SQLite (SFD §5.5 durable execution).
- [inferred] Les 9 packages SFD vides créaient du bruit mental — déclarés dans `opencode.json` plugin[] ils donnaient l'illusion d'un système complet. Retrait =netteté. V2: ne créer un package npm que s'il a du vrai code TS dès la première ligne.
- [inferred] Docker `python:3.14-slim` + Node 22 (NodeSource) fonctionne pour héberger OpenCode CLI à côté d'un runtime Python. Image engine: 277MB. Acceptable.

## Roadmap V2 (priorisée par impact SFD)

| N° | Tâche | SFD ref | Effort | Impact |
|---|---|---|---|---|
| V2.1 | Brancher OpenCode CLI subprocess dans engine_server /run | §5.1 | M (1-2j) | Dispatche vrais agents dans Docker |
| V2.2 | E2E tests pour 10 UC code-only (UC-02,04,05,06,07,09,11,12,13,15) | §4 | L (3-5j) | Prouve le système pour de vrai |
| V2.3 | sfd-phase état persisté (SQLite via OpenCode plugin) | §5.5.1 | M (1j) | Survit aux redémarrages |
| V2.4 | Phase-lock strict par round (40% → 100%) | §5.4.2 | M (1j) | Constitution P5 respectée |
| V2.5 | Drift indicator cockpit (50% → 100%) | Axe 1 | M (1j) | Observabilité complète |
| V2.6 | Implémenter 9 packages SFD si distrib npm requise (sinon skip) | §5.7 §5.5 | L (5-7j) | Distribution |
| V2.7 | Acontext activation + auto-skills live | §5.7.7 | M (2j) | Axe 7 → 100% |
| V2.8 | Dashboard Trinité unifié (CBM+Graphify+Obsidian) | Axe 4 | M (2j) | Vue consolidée |
| V2.9 | gVisor `runsc` install + tests runtime | Axe 5 | S (0.5j) | Sandbox durcie |
| V2.10 | VPS deploy + backup/restore testé | §5.5 | M (1j) | Production prouvée |
| V2.11 | 14 events code-only testés live (AGENT, SECURITY, WORKFLOW...) | §5.11 | M (2j) | Observabilité 100% |

## À ne pas faire en V2 (leçons V1)

- Ne pas réintroduire `agent_loop.py` / `llm_core.py` comme monolithes (master-ref 07).
- Ne pas créer de packages npm vides "pour plus tard" (lesson V1).
- Ne pas casser le contrat bridge stdin/stdout/SSE (master-ref 03).
- Ne jamais committer `.env` (vérifié — `.env` non suivi par git en V1).
- Ne pas toucher la config locale `~/.config/opencode/` — règle utilisateur.
