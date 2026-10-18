# ADR-0003 — Correction des noms de kill-switches (.env ↔ code)

- **Date :** 2026-09-25
- **Statut :** Accepté
- **Contexte :** FND-1 — 6 variables `.env` ne correspondaient pas aux noms lus par le code, neutralisant des features « terminées ».

## Décision

| Avant (`.env`) | Après | Lecteur |
|---|---|---|
| `ODYSSEUS_DURABLE_EXEC` | `ODYSSEUS_DURABLE_EXECUTION` | `src/durable_execution.py`, `archive/legacy/agent_loop.py` |
| `ODYSSEUS_MEMORY_PROVENANCE` | `ODYSSEUS_PROVENANCE_MEMORY` | `src/provenance_memory.py`, `archive/legacy/agent_loop.py` |
| `ODYSSEUS_VISUAL_OUTPUT` | `ODYSSEUS_OUTPUT_ROUTER` | `src/output_router.py`, `archive/legacy/agent_loop.py` |
| `ODYSSEUS_THOUGHT_BUS` | **retiré** (aucun lecteur) | — |
| `ODYSSEUS_PROJECT_MANIFEST` | **retiré** (`load_manifest()` est inconditionnel) → dette INT-8 (Sprint 2) | — |
| `ODYSSEUS_TOOL_DISCOVERY` | **conservé** (lu, `ToolDiscovery` sans appelant) → câblage INT-7 (Sprint 3) | `src/content_security.py` |

## Conséquences

Activation effective (Option C — Palier 0) de : exécution durable (P14 / UC-11), mémoire à provenance (P16), sortie visuelle routée (P22). À valider par FND-2 (tests réels).
