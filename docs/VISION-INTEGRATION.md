# AgentOS — VISION INTÉGRÉE (document unifié)

> **Objet :** rassembler *l'entièreté des apports* (veille + écarts projet + modularité) et les **intégrer à la vision complète** du projet, en un plan unique et séquencé.
> **Entrées fusionnées :** `docs/master-ref/01-SFD-v3.1.md` · `04-OBJECTIFS-COUVERTURE.md` · `09-PLAN-ACTIONS-RESTANTES.md` · `docs/traceability/*` (00→04 + TRACEABILITY) · `docs/veille/VEILLE-EXTRACTION.md` · `VEILLE-FEATURES.md` · `VEILLE-COMPLEMENTAIRE.md`.
> **Date :** 2026-09-25 · **Branche :** `feat/inventaire-global-v1`.

---

## 0. Vision cible (rappel)

**Core value :** *Un agent reçoit un objectif, l'exécute jusqu'au bout sans dériver, apprend de chaque run, et ne dépasse jamais ses limites — sans intervention humaine constante.*

**Architecture — 5 couches :** CONNAISSANCE (Trinité CBM/Graphify/Obsidian) → EXÉCUTION (agents, MCP, sandbox, routing) → DESIGN → OBSERVABILITÉ → GOUVERNANCE (budgets, goal-ancestry, heartbeat).

**8 axes :** Orchestration · Modularité · Routing · Trinité · Sandbox · Gouvernance · Apprentissage · UI Cockpit.

**Constitution (séquence à ne jamais sauter) :**
`loop manuel → tools → permissions → observations → budgets → tracing → planning → context/memory → compaction → skills/connectors → goal loop → subagents`.

---

## 1. État réel (base de départ — vérifié)

| Constat | Chiffre |
|---|---|
| Code réel | 63 routes · 503 endpoints · 1 071 `.py` · 136 modules `src/` |
| SFD modules codés | 20/20 présents · **2 kill-switches ON / 35** |
| Principes / UC ACTIFS | **6/22** · **6/19** (UC-06/07 **absents**) |
| Environnement | **non exécutable** (pas de venv/deps) · code **0 erreur de syntaxe** |
| Doc vs code | divergente (tailles, couverture, 6 variables d'env jamais lues) |
| Modularité | couplages : `core.database` (64), `route_loader` non dynamique (58), shims legacy (71 fichiers) |

---

## 2. Apports à intégrer — inventaire consolidé

Chaque item a un **ID**, une **source** (veille / traceabilité / modularité / SFD), un **module SFD**, et est **dédupliqué** (un même besoin exprimé par plusieurs sources n'apparaît qu'une fois).

### 2.A — FONDATIONS (déblocage immédiat, faible risque)

| ID | Apport | Source | Module SFD | Effort |
|---|---|---|---|---|
| FND-1 | **Corriger 6 noms de variables d'env** (`DURABLE_EXEC`→`_EXECUTION`, `MEMORY_PROVENANCE`→`PROVENANCE_MEMORY`, `VISUAL_OUTPUT`→`OUTPUT_ROUTER`, `THOUGHT_BUS`, `PROJECT_MANIFEST`, `TOOL_DISCOVERY`) | Traçabilité §6.1 | — | 10 min |
| FND-2 | **Rendre le projet exécutable** (venv 3.12 + deps + ruff + pytest) et mesurer réellement | Traçabilité 04 | — | 30 min |
| FND-3 | **Corriger la doc divergente** (03/07 tailles, 08 couverture non traçable) ou la marquer obsolète | Traçabilité §1/§6 | — | 1 h |
| FND-4 | **Décision défaut ON/OFF** des kill-switches, activable par paliers | Traçabilité §3 | — | décision |

### 2.B — INTÉGRATIONS (features codées mais dormantes / absentes)

| ID | Apport | Source | Module SFD | Axe | Effort |
|---|---|---|---|---|---|
| INT-1 | **Orchestration live + phase-tracker** (activer `LIVE_ORCHESTRATION`, `PHASE_TRACKER`) | Traçabilité 02 (P1/P5/P12) | §5.1, §5.4.2 | 1 | M |
| INT-2 | **Exécution durable réelle** (workflows + saga + approbations longues) | Trace 02 (P14), Veille C4 | §5.5 | 6 | M |
| INT-3 | **Mémoire à provenance** (`[stated]/[observed]/[inferred]`) + **impact mémoire** ("earn its place") | Trace 02 (P16/P18/P19) | §5.7 | 7 | M |
| INT-4 | **Routage modèle live** + modèle par phase/agent + bandeau modèle | Trace 01/02 (Axe 3), Veille D5 | §5.6 | 3 | M |
| INT-5 | **Trinité branchée** (Graphify + Obsidian dans le pipeline + dashboard unifié) | Trace 01/02 (Axe 4) | §5.7, §5.11 | 4 | L |
| INT-6 | **Skills à chargement obligatoire** + catalogue | Veille D2/QW1 | §5.13.5, §5.17 | 7 | S |
| INT-7 | **Découverte dynamique d'outils** (`tool_search` + registre MCP + suggestion connecteurs) | Veille CH2/QW7 | §5.13.2/4 | 2 | L |
| INT-8 | **Goal-ancestry live** (mission→goal→projet→tâche) | Trace 02 (P4), Backlog P0.3 | §5.3, §5.9 | 6 | M |
| INT-9 | **Observabilité budget tokens** (chips + multiplicateur multi-agent visible) | Veille QW3/CH12 | §5.9, §5.11 | 6/8 | S |
| INT-10 | **Grounding + citations** dans les livrables de recherche | Veille C5/D19 | §5.10, §5.11 | 4 | S |
| INT-11 | **Heartbeat / cron en langage naturel / briefs planifiés** | Veille C6/QW10/CH5 | §5.5, §5.9 | 6 | M |
| INT-12 | **Wide Research** (recherches parallèles bornées) | Veille C1/D13 | §5.1.2 | 1 | M |
| INT-13 | **Session replay / auditabilité** (vue de rejeu sur les traces) | Veille C2/D14/QW9 | §5.11 | 8 | S |
| INT-14 | **Multi-canal étendu** (Slack/WhatsApp/Email/CLI via gateway unique) | Veille C8/APP1 (OpenClaw) | §5.8 | 2 | M |
| INT-15 | **`AGENTS.md` généré par projet** (repo compréhensible par l'agent) | Veille C7/QW4 | §5.13 | 2 | XS |
| INT-16 | **Mode local / dégradé de 1er rang** (Ollama / llama.cpp) | Veille T1/QW2 | §5.6, NF-06 | 3 | S |
| INT-17 | **Worktrees de projet** (fork/merge) — **absents** | Trace 02 (UC-06/07) | §5.12 | 1 | M |
| INT-18 | **Défaut d'écriture mémoire** (staging draft/commit généralisé) | Trace 02 (P2) | §5.4.1 | 7 | M |
| INT-19 | **Classification & rétention + droit à l'oubli** (5 niveaux, suppression unitaire/globale) | Trace 02 (P17/UC-19) | §5.19 | 6 | M |
| INT-20 | **Sécurité contenus & prompt-injection** sur les surfaces live | Trace 02 (P17) | §5.20 | 5 | M |
| INT-21 | **Préférences: application contextuelle** (pas seulement loggée) + DELETE | Trace 02 (P20/UC-18) | §5.15 | 7 | M |

### 2.C — MODULARITÉ (interchangeabilité — exigence structurelle du projet)

| ID | Apport | Source | Effort |
|---|---|---|---|
| MOD-1 | **`route_loader` réellement dynamique** (découverte `pkgutil`/manifest au lieu de 58 imports) | Modularité §6.1 | M |
| MOD-2 | **Inverser les ~30 arêtes `src/* → routes.*`** (extraire le métier vers `services/`) | Modularité §6.2 | L |
| MOD-3 | **Unifier la source de vérité du routage modèle** (`ModelEndpoint` unique ; `model-routing.json` = seed) | Modularité §6.3 | M |
| MOD-4 | **Éliminer les shims `llm_core`/`agent_loop` → `archive/legacy/`** (migrer 71 importeurs) | Modularité §6.4 | L |
| MOD-5 | **Injection au lieu de singletons globaux** (`AppContext`) | Modularité §6.5 | M |
| MOD-6 | **Contrat DB** (`Protocol`/repository sur `core.database`) | Modularité §6.6 | M |
| MOD-7 | **Généraliser le pattern `MemoryProvider`** (ABC pour VectorStore/Search/Notifications/TTS/STT) | Modularité §6.7 | M |
| MOD-8 | **Outils découplés de `routes`** (auto-enregistrement déclaratif) | Modularité §6.8 | M |
| MOD-9 | **Trancher le statut des 9 packages `@agentos/sfd-*`** (brancher ou archiver) + arbitrer le doublon du bus Python/TS | Modularité §6.9 | S |
| MOD-10 | **Agents déclaratifs** (front-matter YAML → activation sans edit d'orchestrateur) | Modularité §6.10 | M |
| MOD-11 | **CI de modularité** (échec si god node > seuil, ou nouvelle arête `src→routes`) | Modularité §6.11 | S |

### 2.D — VEILLE — nouveaux entrants (absents de la grille de juin)

| ID | Ressource | Apport | Type | Décision | Module SFD |
|---|---|---|---|---|---|
| VEI-1 | **Magic UI (+MCP)** | MCP de composants UI / design system | Techno | Évaluer (cockpit) | §5.13, §5.18 |
| VEI-2 | **OpenRAG** | Blueprint RAG+MCP+Langflow | Applicatif | Veille | §5.11, §5.13 |
| VEI-3 | **open-notebook** | Podcast multi-voix (4) | Applicatif | Veille | §5.18 |
| VEI-4 | **PrivateGPT** | Gateway local « façon API » | Concept | Absorber | §5.6 |
| VEI-5 | **DeerFlow 2.0** | Concurrent deep-research (référence) | Applicatif | Veille | §5.16 |
| VEI-6 | **Kimi K2.6** | Modèle open-weight 256k (routeur) | Techno | Veille | §5.6 |
| VEI-7 | **Claw Code / agentty** | Écosystème agents CLI OSS | Techno | Veille | §5.6 |
| VEI-8 | **AirLLM** | Gros modèles / petite VRAM | Techno | Banque | §5.6 |
| VEI-9 | **Cap** | CAPTCHA self-hosted | Techno | Banque | §5.4 |
| VEI-10 | **Hermes — data flywheel MLOps** | Export des trajectoires → entraînement/RL | Concept | Absorber (LT) | §5.11, §5.7.7 |
| VEI-11 | **Hermes — déploiement élastique** | Exécution à la demande (Daytona/Modal/SSH) | Concept | Veille | §5.5, NF-06 |
| VEI-12 | **Mistral Vibe 2.0** | Sous-agents par tâche (contre-exemple P12) | Concept | Veille | §5.1.3 |

### 2.E — HORS SCOPE / LOT LONG TERME (explicitement écartés du plan)

- **Génération média/pub** (Arcads, Higgsfield, Meta Ads, TopView) · **navigateur autonome visible** (fort effet, coût infra) · **podcast/vidéo avancés** · **AirLLM** (dépendance lourde) · **OSINT perso / hardware / apps grand public** · tout le divertissement.

---

## 3. Plan intégré (séquencé selon la Constitution)

> Principe : **on ne saute pas d'étape**. On consolide d'abord le socle, puis on active, puis on étend.

### Sprint 0 — Vérité & déblocage (fondations)
`FND-1 · FND-2 · FND-3 · FND-4`
→ Objectif : projet **exécutable**, doc **honnête**, variables **réparées**, décision ON/OFF prise.

### Sprint 1 — Socle actif (tracing, permissions, budget)
`INT-1 · INT-4 · INT-9 · INT-13 · INT-16 · INT-15`
→ Objectif : orchestration/phase-lock réels, routing visible, budget visible, traces rejouables, mode local, AGENTS.md.
*(Respecte l'ordre : permissions → observations → budgets → tracing.)*

### Sprint 2 — Mémoire & contexte
`INT-3 · INT-18 · INT-19 · INT-21 · INT-2`
→ Objectif : mémoire à provenance appliquée, draft/commit, rétention/droit à l'oubli, préférences contextuelles, **exécution durable**.

### Sprint 3 — Skills & outils (extensibilité)
`INT-6 · INT-7 · MOD-9 · VEI-1`
→ Objectif : catalogue de skills obligatoire, découverte MCP dynamique, packages TS tranchés.

### Sprint 4 — Connaissance & gouvernance
`INT-5 · INT-8 · INT-10 · INT-11 · INT-17`
→ Objectif : Trinité branchée + dashboard, goal-ancestry live, grounding/citations, heartbeat, worktrees.

### Sprint 5 — Orchestration avancée (sur preuve uniquement)
`INT-12 · INT-14 · VEI-4 · VEI-11`
→ Objectif : Wide Research bornée, multi-canal étendu, gateway local, déploiement élastique.

### En continu — Modularité (transversal, à chaque sprint)
`MOD-1 → MOD-11` (priorité : MOD-1, MOD-3, MOD-2, MOD-4) + CI de modularité (MOD-11).

### Lot long terme (banque)
`VEI-2 · VEI-3 · VEI-5→VEI-8 · VEI-10 · VEI-12` + navigateur visible + média.

---

## 4. Matrice de priorité (impact / effort)

| Priorité | Items |
|---|---|
| 🟢 **Quick wins** (≤ ½ j) | FND-1, FND-2, INT-6, INT-9, INT-10, INT-13, INT-15, INT-16, MOD-9, MOD-11 |
| 🟡 **Chantiers structurants** | INT-1→INT-5, INT-7, INT-8, INT-11, INT-12, INT-14, INT-17→INT-21, MOD-1→MOD-8, MOD-10 |
| 🔵 **Long terme / banque** | VEI-2, VEI-3, VEI-5→VEI-11 |

**Chemin critique :** FND-1 → FND-2 → INT-1 (socle actif) → INT-3/INT-2 (mémoire+durable) → INT-6/INT-7 (skills+outils) → INT-5/INT-8 (Trinité+gouvernance) → INT-12/INT-14 (avancé).

---

## 5. Traçabilité de ce document

| Bloc | Source vérifiable |
|---|---|
| État réel | `docs/traceability/TRACEABILITY.md` + `00→04` |
| Apports veille | `docs/veille/VEILLE-COMPLEMENTAIRE.md` (+ `VEILLE-EXTRACTION`, `VEILLE-FEATURES`) |
| Modularité | `docs/traceability/03-MODULARITE.md` §6 |
| Backlog d'origine | `docs/master-ref/09-PLAN-ACTIONS-RESTANTES.md` |
| Spec | `docs/master-ref/01-SFD-v3.1.md`, `04-OBJECTIFS-COUVERTURE.md` |

---

*Fin du document unifié. Prochaine étape recommandée : exécuter le Sprint 0 (déblocage), puis valider le chemin critique.*
