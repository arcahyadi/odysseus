# Agent OS — Objectifs & Couverture (score mesuré)

> **Fusion de :** objectifs du projet (`PROJECT-2026-06-27.md`) + matrice de couverture.
> **MAJ :** 2026-09-26 — **source unique de couverture** : le score est **recalculé depuis la traçabilité vérifiée** (`../traceability/`), en remplacement des scores contradictoires antérieurs (59 % / 83 % / 90 %). Recalculé après activation du Palier 0.

---

## Core Value

**Un agent reçoit un objectif, l'exécute jusqu'au bout sans dériver, apprend de chaque run, et ne dépasse jamais ses limites — sans intervention humaine constante.**

Workspace AI self-hosté complet bâti sur OpenCode (fork Odysseus), transformé en système d'agents autonomes de niveau production. Architecture déterministe multi-couches (Connaissance → Exécution → Automatisation → Gouvernance) capable de faire tourner des agents longue durée, bornés par des budgets et des objectifs, avec une mémoire d'apprentissage continue.

---

## Architecture — 5 Couches

```
CONNAISSANCE (Trinité)    → CBM + Graphify + Obsidian
EXÉCUTION                 → Agents, MCP, Sandbox, Routing
DESIGN                    → Extract + Open Design
OBSERVABILITÉ             → Traces, CodeBurn, AutoEval
GOUVERNANCE               → Budgets, Goal-Ancestry, Heartbeat
```

---

## Objectifs — 8 Axes

| Axe | Objectif |
|---|---|
| **1 — Orchestration** | Lancer des plans entiers avec subagents, déléguer et spécialiser les tâches au bon agent avec les bons outils. |
| **2 — Modularité** | Chaque brique interchangeable sauf le cœur ; ajouter/retirer un service, un agent, un outil sans redémarrage. |
| **3 — Routage** | Sélectionner automatiquement le bon modèle par tâche/phase/agent, avec repli. |
| **4 — Connaissance (Trinité)** | Interroger CBM (code) + Graphify (sémantique) + Obsidian (mémoire) avant de répondre. |
| **5 — Sandbox** | Toute exécution de code isolée, validée, tracée. |
| **6 — Gouvernance** | Budgets granulaires, goal-ancestry, approval gates, heartbeat. |
| **7 — Apprentissage** | Distiller les runs en compétences, mémoire persistante à provenance. |
| **8 — UI Cockpit** | Tableau de bord live : phase, santé, dérive, budget, agents. |

---

## Score de couverture MESURÉ (source unique)

**Méthode** (reprise de la traçabilité, pondération « codé ») :

- `Couverture (codé)` = (ACTIF × 1 + PARTIEL × 0.5 + DORMANT × 0.5) ÷ total — mesure *ce qui est écrit dans le code*, dormant inclus.
- `Activation (live)` = ACTIF ÷ total — mesure *ce qui tourne par défaut*.

Statuts issus de `../traceability/02-PRINCIPES-UC.md` (vérifiés sur le code).

| Ensemble | ACTIF | PARTIEL | DORMANT | ABSENT | Total | Couverture (codé) | Activation (live) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Principes P1-P22** | 5 | 17 | 0 | 0 | 22 | **61 %** | **23 %** |
| **Cas d'usage UC-01→19** | 5 | 11 | 1 | 2 | 19 | **58 %** | **26 %** |
| **TOTAL (41 exigences)** | 10 | 28 | 1 | 2 | 41 | **≈ 60 %** | **≈ 24 %** |

> **SFD v3.1** ajoute P23-P25 et UC-20-21 (proactivité, grounding, data flywheel, brief planifié, vérifier la source). Non encore vérifiés côté code (spec only) → à intégrer au score lors de leur implémentation.

> **🟡 Sprint 1b (2026-09-26) — le score a BAISSÉ : ~62 % → ~60 % de couverture, ~29 % → ~24 % d'activation.**
> Le Palier 0 a activé 14 kill-switchs **dans le code** (défaut `on`, plus seulement dans `.env`), et les 41 statuts ont été intégralement re-vérifiés contre le code, suite verte à l'appui (4 792 PASS).
> - **DORMANT 5 → 1.** Le levier a fonctionné : plus aucun principe fermé par défaut.
> - **ACTIF 12 → 10.** C'est le contrepoint honnête : en branchant les modules, on a découvert que « codé » ≠ « actif ». **UC-01** attend une `OPENCODE_API_KEY` absente de `.env` (le projet utilise OpenCode Zen) ⇒ l'agent n'a aucun endpoint. **UC-05** est écrasé : `on_round_start` réimpose `BUILD` sur la phase posée par l'API. **P7** et **P11** sont déclassés (structure cosmétique, `get_decision_engine()` sans appelant).
> - Les 4 DORMANT devenus PARTIEL ne sont pas des résurrections : leur switch est `on`, mais le résultat est **seulement loggé** ou calculé sur une entrée vide.
>
> Le score baisse donc parce qu'il est **plus juste**, pas parce que le code a régressé. Détail : `../traceability/02-PRINCIPES-UC.md`.

**Lecture :** le système est **codé à ~60 %** de ses exigences, mais **~24 % seulement sont actives en production** — et l'écart n'est plus constitué de switchs OFF, il est constitué de **résultats calculés puis ignorés**. C'est un backlog de câblage, pas de fonctionnalité manquante. Détail : `../traceability/TRACEABILITY.md` et `../traceability/02-PRINCIPES-UC.md`.

---

## Exigences fondatrices (historique)

- **Validées** (12) : FastAPI, LLM routing + fallback, MCP servers, Deep Research, Task scheduler, Context compactor, CalDAV/Email, PWA UI, Cookbook, Auth, Claude/Codex integrations, ChromaDB RAG.
- **Actives** (16 listées, l'en-tête « 28 » était faux) : loop canonique + invariants, phase-lock, Serena/Scrapling MCP, observations JSONL, CodeBurn, GSD, PROJECT.yaml + autoeval, Acontext, Governance, Channel Gateway, Trinité UI, Decision Engine, Sandbox durci, Design Extract/Open Design, Debate 5 personas, RRF hybrid search…
- **Planifiées** (7) : Trinité branchée UI, Graphify pipeline, Obsidian second-brain, Heartbeat, budgets granulaires live, goal-ancestry live, multi-agent live.

> ⚠️ Ces listes proviennent de l'ère v3.0 et **recoupent** les statuts ci-dessus ; en cas de conflit, **le score mesuré et `../traceability/` font foi**.
>
> **Trois entrées de la liste « Actives » sont contredites par la mesure du 2026-09-26**, et sont donc à relire :
> - **Decision Engine** — `get_decision_engine()` (`src/decision_engine.py:749`) n'a **aucun appelant** : le moteur existe, rien ne l'interroge (cf. P11).
> - **CodeBurn** — `ODYSSEUS_CODEBURN` est `off` par défaut dans le code.
> - **PROJECT.yaml + autoeval** — `PROJECT.yaml` n'existe pas (seul l'exemple) ; autoeval est bien `on`, mais son action reste dormante (cf. P4, P6).
>
> `phase-lock`, lui, est désormais **vivante** (poussée par le phase tracker, appliquée par `tool_execution.py:625-630`) mais **cosmétique** : l'inférence ne produit que `PLAN`/`BUILD` et `BUILD` ne bloque rien. Cf. P1.

---

## Séquence de Build (Constitution)

```
loop manuel → tools → permissions → observations → budgets → tracing
→ planning → context/memory → compaction → skills/connectors
→ goal loop → subagents
```

Ne jamais sauter d'étape.
