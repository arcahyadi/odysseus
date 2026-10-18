# Sprint 0 — Plan d'exécution & Options FND-4

> Orchestrateur : `sfd-orchestrator` · Chef : Tayk0oo · Date : 2026-09-25
> Source de vérité : `docs/traceability/` (jamais `09`/`08`).

---

## 1. État vérifié (au moment du kickoff)

| Fondation | État | Preuve |
|---|---|---|
| FND-3 (docs divergentes) | ✅ **FAIT** | bannières `RÉVISÉ 2026-09-25` dans `03`/`07` · `08`/`12` supprimés · `04` recalculé |
| FND-2 (exécutable) | ❌ à faire | `python3.12`=3.12.14 présent · **pas de venv** · `import fastapi` échoue |
| FND-1 (noms d'env) | ❌ à faire | 6 mismatches confirmés (ci-dessous) |
| FND-4 (politique kill-switch) | 🔴 **Chef** | à trancher |

### Détail FND-1 — mismatches `.env` ↔ code
| `.env` écrit | code lit | verdict |
|---|---|---|
| `ODYSSEUS_DURABLE_EXEC` | `ODYSSEUS_DURABLE_EXECUTION` | renommer dans `.env` |
| `ODYSSEUS_MEMORY_PROVENANCE` | `ODYSSEUS_PROVENANCE_MEMORY` | renommer dans `.env` |
| `ODYSSEUS_VISUAL_OUTPUT` | `ODYSSEUS_OUTPUT_ROUTER` | renommer dans `.env` |
| `ODYSSEUS_THOUGHT_BUS` | *(aucun lecteur)* | statuer : supprimer ou câbler |
| `ODYSSEUS_PROJECT_MANIFEST` | *(aucun lecteur)* | statuer : supprimer ou câbler |
| `ODYSSEUS_TOOL_DISCOVERY` | lu (`content_security.py`) mais `ToolDiscovery` sans appelant | statuer : câbler ou supprimer |

> ⚠️ Les points de lecture vivent en grande partie dans `archive/legacy/agent_loop.py` (via le shim `src/agent_loop.py`). FND-1 doit `grep` **`src/` ET `archive/legacy/`**.

---

## 2. Plan FND-1 / FND-2 (🟢 initiative agent — pas d'escalade)

| ID | Tâche | Agent | Effort | Risque | DoD |
|---|---|---|---|---|---|
| FND-1 | Corriger les 3 renames `.env` + statuer (dans un mini-ADR) sur les 3 inertes (`THOUGHT_BUS`, `PROJECT_MANIFEST`, `TOOL_DISCOVERY`) | `executor` | ~10 min | faible (réversible) | `.env` aligné code ; ADR documenté ; aucun test cassé |
| FND-2 | `python3.12 -m venv venv && pip install -r requirements.txt && pip install ruff pytest` puis `pytest -q` + `ruff check .` | `build` / `gsd-executor` | ~30 min | moyen (résolution deps réseau) | suite réelle exécutée ; chiffres de couverture réels publiés dans `traceability/04` |
| FND-3 | *(déjà fait)* vérification rapide de cohérence | `explore` | 5 min | nul | 0 lien cassé, versions alignées |

**Séquençage :** FND-1 → FND-2 (l'exécution valide les renames). FND-1 et FND-3 peuvent se faire en parallèle.

---

## 3. Options FND-4 — politique de bascule des kill-switches

**Contexte :** 35 kill-switches, **2 ON** par défaut. L'essentiel de la SFD est *câblé mais dormant*.

| Option | Description | Avantage | Inconvénient |
|---|---|---|---|
| **A — Off par défaut** (statu quo) | activer au cas par cas après validation | zéro régression | vision « holistique » jamais atteinte ; inertie |
| **B — On par défaut global** | tout activer d'un coup | vision immédiate | **risqué** : features non testées, dépendances externes absentes (token GitHub CBM, vault Obsidian, clés LangFuse/CodeBurn, tokens canaux) → risque de casse au boot |
| **C — Activation par paliers** ⭐ | 3 paliers réversibles, chacun gated par tests + observabilité | sûr **et** progresse vers la vision | un peu plus lent |

**Détail de l'option C (recommandée) :**

| Palier | Switches | Condition d'activation |
|---|---|---|
| **P0 — pur code** (aucun service externe) | `PHASE_TRACKER`, `MODEL_ROUTER`, `PROGRESSIVE_DISCLOSURE`, `MEMORY_IMPACT`, `UNIFIED_TOKENS`, `OUTPUT_ROUTER`, `PREFERENCES`, `DATA_CLASSIFICATION`, `CONTENT_SECURITY`, `DURABLE_EXECUTION`, `PROVENANCE_MEMORY`, `AUTOEVAL`/`AUTOEVOLVE`/`CHECKPOINT` (observabilité) | après FND-2, tests verts, cockpit reflète l'état |
| **P1 — services locaux Docker** | `OBSIDIAN_MCP` (vault), `GRAPHIFY`, `SERENA_MCP`, `CBM` (🔴 token GitHub), `LANGFUSE`/`CODEBURN` (clés), `INPROCESS_DISCORD`/`TELEGRAM` (tokens) | service démarré + clé fournie (escalade par clé) |
| **P2 — externes/comptes** | publication npm `@agentos/sfd-*`, VPS, OPA/Meilisearch public | 🔴 validation Chef + compte |

**Recommandation orchestrateur :** **Option C**, commencer par **P0** dès que FND-2 est vert. Aucun switch P1/P2 sans validation Chef.

---

## 4. Prochaine étape
1. **Chef tranche FND-4** (A / B / C).
2. J'exécute **FND-1 → FND-2 → FND-3(vérif)** en parallèle raisonnable.
3. Puis **Sprint 1** (uniquement après FND-1→3 + FND-4).
