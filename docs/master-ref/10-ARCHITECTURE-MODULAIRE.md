# Analyse Combinatoire Complète — Outils & Vision AgentOS

> **Date :** 2026-08-05 | **Question :** Comment chaque outil s'aligne sur notre vision, et comment se combinent-ils pour former un système cohérent ?

---

## Table des matières

1. [Notre Vision — Rappel](#1-notre-vision--rappel)
2. [Les 68 Outils — Classés par Alignement Vision](#2-les-68-outils--classés-par-alignement-vision)
3. [Matrices Combinatoires — Quel outil avec quel autre ?](#3-matrices-combinatoires--quel-outil-avec-quel-autre-)
4. [Chaînes d'Outils par Use Case SFD](#4-chaînes-doutils-par-use-case-sfd)
5. [Le Service Mesh Complet](#5-le-service-mesh-complet)
6. [Decision Engine — L'Orchestrateur](#6-decision-engine--lorchestrateur)
7. [Workflows Combinatoires Concrets](#7-workflows-combinatoires-concrets)
8. [Roadmap d'Intégration](#8-roadmap-dintégration)

---

## 1. Notre Vision — Rappel

> **« Un agent reçoit un objectif, l'exécute jusqu'au bout sans dériver, apprend de chaque run, et ne dépasse jamais ses limites — sans intervention humaine constante. »**

Extrait de la SFD v3.1, nos **5 principes directeurs** pour le choix et la combinaison des outils :

| # | Principe directeur | Ce que ça implique pour les outils |
|---|-------------------|-------------------------------------|
| **V1** | **Autonomie bornée** | L'agent décide quels outils appeler, mais dans un cadre de permissions strict |
| **V2** | **Apprentissage continu** | Chaque run doit nourrir le run suivant. Pas de mémoire volatile |
| **V3** | **Exécution déterministe** | Mêmes entrées = même résultat. Pas de boîte noire |
| **V4** | **Modularité totale** | Chaque brique remplaçable sans casser le système |
| **V5** | **Self-hosted first** | Tout tourne chez nous. Pas de dépendance cloud obligatoire |

Ces 5 principes déterminent pourquoi on choisit (ou rejette) chaque outil.

---

## 2. Les 68 Outils — Classés par Alignement Vision

### Grille de lecture

Chaque outil est évalué sur son alignement avec nos 5 principes (✓ = aligné, ~ = neutre, ✗ = contraire).

### 2.1 Coeur du Système — Intégrés Actifs (14 outils)

Ces outils tournent EN CE MOMENT dans notre Docker Compose. Ils sont le socle.

| # | Outil | Rôle | V1 | V2 | V3 | V4 | V5 | Score Vision |
|---|-------|------|----|----|----|----|----|-------------|
| 1 | **OpenCode Engine** | Moteur d'agents 7 phases | ✓ | ✓ | ✓ | ✓ | ✓ | **5/5** |
| 2 | **ZenRouter** | Routing 24 modèles LLM | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 3 | **CBM** (codebase-memory) | Graphe de code 11K nœuds | ✓ | ✓ | ✓ | ✓ | ✓ | **5/5** |
| 4 | **Graphify** | Graphe sémantique concepts | ✓ | ✓ | ✓ | ✓ | ✓ | **5/5** |
| 5 | **Scrapling** | Web scraping unifié | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 6 | **Serena** | Édition sémantique LSP | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 7 | **Kroki** | Diagrammes 25+ langages | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 8 | **SearXNG** | Meta-search engine | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 9 | **ChromaDB** | Vector database | ✓ | ✓ | ✓ | ✓ | ✓ | **5/5** |
| 10 | **Meilisearch** | Full-text search | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 11 | **Supabase MCP** | DB branching + state | ✓ | ✓ | ✓ | ✓ | ✓ | **5/5** |
| 12 | **Playwright** | Tests E2E sandbox | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 13 | **ntfy** | Alertes push | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 14 | **Paperclip** | Gouvernance agents | ✓ | ✓ | ✓ | ~ | ✓ | **4/5** |

**Score moyen : 4.4/5** — Excellente base.

### 2.2 À Activer (P0–P1) — Déjà configurés, juste OFF (8 outils)

| # | Outil | Pourquoi OFF | Action | V1–V5 |
|---|-------|-------------|--------|-------|
| 15 | **Obsidian Vault** | Kill-switch OFF | Activer `ODYSSEUS_OBSIDIAN_MCP=on` | 5/5 |
| 16 | **Design Extract** (designlang) | OFF par défaut | Activer pour phase DESIGN | 4/5 |
| 17 | **Open Design** (nexu-io) | OFF par défaut | Activer pour phase DESIGN | 4/5 |
| 18 | **CodeBurn** | OFF par défaut | Activer pour observabilité tokens | 4/5 |
| 19 | **Acontext** | Configuré, pas actif | Activer pour distillation auto skills | 5/5 |
| 20 | **Browser-Harness** | Fallback Scrapling | Rester en fallback | 4/5 |
| 21 | **Crawl4AI** | Fallback Scrapling | Rester en fallback | 4/5 |
| 22 | **LangFuse** | Pas activé live | Activer pour traces LLM | 4/5 |

**Score moyen : 4.3/5** — Plus-value immédiate, effort minimal.

### 2.3 Nouveaux Outils (Août 2026) — 8 outils

| # | Outil | Rôle | V1 | V2 | V3 | V4 | V5 | Score |
|---|-------|------|----|----|----|----|----|-------|
| 23 | **Dockge** | Manager Docker Compose | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 24 | **Forgejo** | Git + CI/CD self-hosted | ✓ | ✓ | ✓ | ✓ | ✓ | **5/5** |
| 25 | **Uptime Kuma** | Monitoring 17 briques | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 26 | **Gotify** | Notifications push | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 27 | **Vaultwarden** | Secrets manager | ✓ | - | ✓ | ✓ | ✓ | **4/5** |
| 28 | **AdGuard Home** | DNS + filtrage | ✓ | - | ✓ | ✓ | ✗ | **3/5** |
| 29 | **Bitwarden** | Password manager | ✓ | - | ~ | ✓ | ✗ | **3/5** |
| 30 | **Pterodactyl** | Panel serveurs jeu | ✓ | - | ✓ | ~ | ✓ | **3/5** |

**Note AdGuard/Bitwarden :** V5 = ✗ car le cloud Bitwarden casse « self-hosted first », mais Vaultwarden résout ce problème. AdGuard a un score plus bas car c'est un service réseau global, pas modulaire.

### 2.4 Patterns Absorbés — Pas d'outil, mais la logique intégrée (7 patterns)

Ces « outils » n'existent pas comme conteneurs séparés. Leur logique a été absorbée dans notre codebase.

| # | Pattern Source | Absorbé dans | Principe |
|---|---------------|-------------|----------|
| 31 | **OmO** (tiered routing) | `ZenRouter` → `resolve_model()` | Classification auto de complexité |
| 32 | **HexStrike AI** (permissions) | `tool_security.py` → permission matrix | Chaque outil a un niveau de risque |
| 33 | **HolyClaude** (Docker infra) | `docker-compose.yml` → profils sécurité | Sandboxing par défaut |
| 34 | **vibecode-pro-max-kit** (quality) | `agent_loop.py` → phase-locking | Chaque phase a ses outils autorisés |
| 35 | **Caveman Method** (debug) | Règles de commit → draft/commit séparés | Une idée par ligne |
| 36 | **agents-best-practices** (harness) | `CanonicalLoop` → invariants par phase | Framework harness universel |
| 37 | **Build Your Own X** (corpus) | Base RAG → prompts agents | Référence pour patterns d'implémentation |

### 2.5 Veille Active — À réévaluer (6 outils)

| # | Outil | Pourquoi en veille | Déclencheur |
|---|-------|-------------------|-------------|
| 38 | **Odysseus** (original) | UI existante, en cours d'élagage | Décision finale Option A/B |
| 39 | **master-skill** | Distillation skills | Si Acontext insuffisant |
| 40 | **SurfSense** | Alternative NotebookLM | Si RAG actuel limité |
| 41 | **ANUS** | Auto-évolution roadmap | Si auto-evolve insuffisant |
| 42 | **Twenty** | CRM open-source | Si besoin CRM interne |
| 43 | **Hermes** (Nous Research) | Agent framework | Si OpenCode limité |

### 2.6 Banque d'Idées — Futur lointain (10 outils)

| # | Outil | Potentiel |
|---|-------|-----------|
| 44 | anime.js | Animations dashboard |
| 45 | reactbits.dev | Composants React (si Option B) |
| 46 | UIverse.io | Templates UI |
| 47 | Blender MCP | 3D asset generation |
| 48 | SketchUp MCP | Pattern desktop bridge |
| 49 | MediaAgent/OpenGenAI | Génération image/vidéo |
| 50 | Design Galleries | 1600+ refs UI |
| 51 | Plausible Analytics | Analytics privacy-first |
| 52 | ALTCHA | Captcha PoW self-hosted |
| 53 | ScrapGraphAI | Scraping + knowledge graph |

### 2.7 Ignorés — Hors scope (14 outils)

| # | Outil | Raison |
|---|-------|--------|
| 54–67 | Almanac, Wan2GP, Open Generative AI, etc. | Redondants, hors scope, pas d'API |

### 2.8 Supprimés — Remplacés par notre solution (1)

| # | Ex-outil | Remplacé par | Raison |
|---|---------|-------------|--------|
| 68 | **n8n** | **Decision Engine** | Trop lourd, trop couplé, pas versionnable |

---

## 3. Matrices Combinatoires — Quel outil avec quel autre ?

### 3.1 Matrice de Compatibilité (coeur du système)

Chaque case = le combo fonctionne-t-il ? ✓ = natif, ⚡ = synergie forte, ○ = compatible, ✗ = incompatible

```
                CBM GRF OBS SCR SER SRX CHR MEI KRO SUP PLW ntf UPT GOT FOR DGK
       CBM      ·   ⚡   ⚡   ○   ⚡   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○
       Graphify  ⚡   ·   ⚡   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○
       Obsidian  ⚡   ⚡   ·   ○   ○   ○   ⚡   ⚡   ○   ○   ○   ○   ○   ○   ○   ○
       Scrapling ○   ○   ○   ·   ○   ⚡   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○
       Serena    ⚡   ○   ○   ○   ·   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○
       SearXNG   ○   ○   ○   ⚡   ○   ·   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○
       ChromaDB  ○   ○   ⚡   ○   ○   ○   ·   ⚡   ○   ✓   ○   ○   ○   ○   ○   ○
       MeiliSrch ○   ○   ⚡   ○   ○   ○   ⚡   ·   ○   ○   ○   ○   ○   ○   ○   ○
       Kroki     ○   ○   ○   ○   ○   ○   ○   ○   ·   ○   ○   ○   ○   ○   ○   ○
       Supabase  ○   ○   ○   ○   ○   ○   ✓   ○   ○   ·   ○   ○   ○   ○   ⚡   ○
       Playwright○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ·   ○   ○   ○   ○   ○
       ntfy      ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ·   ○   ⚡   ○   ○
       Uptime    ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ⚡   ·   ⚡   ○   ○
       Gotify    ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ⚡   ⚡   ·   ○   ○
       Forgejo   ○   ○   ○   ○   ○   ○   ○   ○   ○   ⚡   ○   ○   ○   ○   ·   ⚡
       Dockge    ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ○   ⚡   ·
```

### 3.2 Les Combos Gagnants (synergies ⚡)

| Combo | Outils | Ce que ça débloque |
|-------|--------|-------------------|
| **Trinité** | CBM + Graphify + Obsidian | L'agent a une mémoire code + concepts + notes |
| **Recherche Web** | Scrapling + SearXNG | Web scraping avec fallback meta-search |
| **Recherche Code** | CBM + Serena | Graphe de code + intelligence LSP = compréhension profonde |
| **RAG Hybride** | ChromaDB + Meilisearch | Vector search + full-text = pertinence maximale |
| **CI/CD Auto** | Forgejo + Dockge + Uptime Kuma | Git push → déploiement → monitoring, tout self-hosted |
| **Alerting** | Uptime Kuma + Gotify + ntfy | Détection panne → notif push + email |
| **State Agents** | Supabase + Decision Engine | DB branching pour chaque agent, rollback natif |
| **Design Pipeline** | Design Extract + Open Design + Kroki | URL → design tokens → composants → diagrammes |
| **Apprentissage** | Acontext + Obsidian + CodeBurn | Run → leçon → vault → réutilisé au run suivant |
| **Secrets** | Vaultwarden + Docker secrets | Tous les secrets centralisés, jamais en clair |

### 3.3 Les Combos Anti-Pattern (ne pas faire)

| Combo | Pourquoi c'est une erreur |
|-------|--------------------------|
| n8n + Decision Engine | Redondance totale, complexité inutile |
| ChromaDB seul sans Meilisearch | Pertinence dégradée (vecteurs seuls = bruit) |
| Scrapling sans SearXNG | Pas de fallback si page bloque le scraper |
| Forgejo sans Dockge | CI/CD manuel, pas d'automatisation |
| Uptime Kuma sans Gotify | Monitoring sans alertes = aveugle |

---

## 4. Chaînes d'Outils par Use Case SFD

Chaque Use Case de la SFD v3.1 se traduit par une chaîne d'outils spécifique.

### UC-01 — Lancer un nouveau projet

```
User: "crée une app Flask todo avec SQLite"

CLASSIFY  → constitution agent           → [Paperclip] vérifie les budgets
KNOW      → explore agent                → [CBM] code existant + [SearXNG] recherche web
                                           → [Scrapling] lit la doc Flask
PLAN      → planner agent                → [CBM] vérifie les fichiers existants
BUILD     → executor agent (minimax-m3)  → [Serena] référence le code
                                           → [Kroki] génère le diagramme d'archi
                                           → [Supabase] DB branching pour l'agent
QUALITY   → reviewer agent               → [Playwright] tests E2E
                                           → [CodeBurn] mesure one-shot rate
AUTOEVAL  → gsd-verifier agent           → [LangFuse] traces de qualité
MEMORY    → gsd-roadmapper agent         → [Acontext] extrait les leçons
                                           → [Obsidian] écrit dans le vault
                                           → [ChromaDB] indexe pour futur rappel
```

**Chaîne complète :** Paperclip → CBM → SearXNG → Scrapling → Serena → Kroki → Supabase → Playwright → CodeBurn → LangFuse → Acontext → Obsidian → ChromaDB
**13 outils mobilisés** sur une tâche simple.

### UC-03 — Consulter l'état

```
Cockpit UI → [Event Bus] → [Uptime Kuma] health 17 services
                          → [Gotify] notif si dégradé
                          → [LangFuse] métriques LLM
                          → [CodeBurn] tokens consommés
```

**5 outils.** Temps réel, zéro latence.

### UC-08 — Mémoire transversale

```
Agent demande contexte
  → [ChromaDB] vector search → "quels faits sont liés ?"
  → [Meilisearch] full-text → "quels documents mentionnent ce terme ?"
  → [Obsidian] vault → "quelles notes j'ai écrites sur ce sujet ?"
  → [Graphify] concepts → "quels concepts sont voisins ?"
  → Fusion → Contexte injecté dans le prompt
```

**4 outils en parallèle**, résultat fusionné. C'est le pattern Éventail.

### UC-10 — Multi-agent spawn

```
Message complexe détecté
  → [ZenRouter] évalue la complexité → découpe en sous-tâches
  → [Paperclip] vérifie les budgets par sous-agent
  → [Supabase] crée un DB branch par agent
  → 8 agents spawnés en parallèle
  → Chaque agent a accès à [CBM, Scrapling, Serena, Kroki]
  → [Event Bus] collecte les résultats
  → [Decision Engine] fusionne et valide
```

**7 outils.** Le Decision Engine orchestre le fan-out/fan-in.

### UC-16 — Visualisation inline

```
Agent: "montre l'architecture en diagramme"
  → [Kroki] rendu Mermaid → SVG
  → [Cockpit] affiche le SVG inline dans le chat
  → [Obsidian] sauvegarde le diagramme dans le vault
```

**3 outils.** Simple, immédiat, visuel.

### UC-19 — Droit à l'oubli

```
User: "oublie tout sur le projet X"
  → [Obsidian] vault → supprime les notes taggées #projet/X
  → [ChromaDB] → supprime les vecteurs du namespace projet/X
  → [Meilisearch] → supprime l'index projet/X
  → [Supabase] → supprime le DB branch
  → [Graphify] → supprime le sous-graphe
  → [Event Bus] → émet memory.forget avec trace_id
  → [ntfy] → notifie l'admin de la suppression
```

**7 outils.** Suppression complète, tracée, irréversible (par design).

---

## 5. Le Service Mesh Complet

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AGENTOS SERVICE MESH                               │
│                        ======================                             │
│                   17 briques · 1 Event Bus · 1 Decision Engine            │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     COUCHE 1 — CONNAISSANCE                       │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │   CBM    │  │ Graphify │  │ Obsidian │  │  Serena  │        │    │
│  │  │ :9749    │  │ :9750    │  │  vault   │  │ :8765    │        │    │
│  │  │ code     │  │ concept  │  │ second   │  │ code     │        │    │
│  │  │ graph    │  │ graph    │  │ brain    │  │ intel    │        │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │    │
│  │       └──────────────┴────────────┴──────────────┘              │    │
│  │                         TRINITÉ                                  │    │
│  └──────────────────────────┬───────────────────────────────────────┘    │
│                             │                                            │
│  ┌──────────────────────────┴───────────────────────────────────────┐    │
│  │                     COUCHE 2 — RECHERCHE                          │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │Scrapling │  │ SearXNG  │  │ ChromaDB │  │MeiliSrch │        │    │
│  │  │ :8800    │  │ :8080    │  │ :8100    │  │ :7700    │        │    │
│  │  │ web      │  │ meta     │  │ vectors  │  │ fulltext │        │    │
│  │  │ fetch    │  │ search   │  │          │  │          │        │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     COUCHE 3 — EXÉCUTION                          │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │ OpenCode │  │ZenRouter │  │ Supabase │  │Playwright│        │    │
│  │  │ Engine   │  │ 24 LLMs  │  │ DB branch│  │ E2E test │        │    │
│  │  │ 7 phases │  │ fallback │  │ state    │  │ sandbox  │        │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     COUCHE 4 — DESIGN                             │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │    │
│  │  │ Design   │  │  Open    │  │  Kroki   │                       │    │
│  │  │ Extract  │  │  Design  │  │ :8700    │                       │    │
│  │  │ URL→DTCG │  │ Brief→UI │  │ 25+ diag │                       │    │
│  │  └──────────┘  └──────────┘  └──────────┘                       │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                   COUCHE 5 — OBSERVABILITÉ                        │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │ Uptime   │  │  Gotify  │  │  LangFuse│  │   ntfy   │        │    │
│  │  │ Kuma     │  │ :8085    │  │ :3030    │  │ :8091    │        │    │
│  │  │ :3001    │  │ push     │  │ LLM      │  │ multi    │        │    │
│  │  │ monitor  │  │ notifs   │  │ traces   │  │ channel  │        │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐                                      │    │
│  │  │ CodeBurn │  │ Acontext │                                      │    │
│  │  │ tokens   │  │ skills   │                                      │    │
│  │  │ metrics  │  │ auto     │                                      │    │
│  │  └──────────┘  └──────────┘                                      │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                   COUCHE 6 — AUTOMATION                            │    │
│  │                                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │ Decision │  │  Dockge  │  │ Forgejo  │  │Vaultward │        │    │
│  │  │ Engine   │  │ :5001    │  │ :3000    │  │ en :8087 │        │    │
│  │  │ workflow │  │ compose  │  │ git+CI   │  │ secrets  │        │    │
│  │  │ YAML     │  │ manager  │  │ runner   │  │ manager  │        │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│                          ═══════════════                                  │
│                          EVENT BUS CENTRAL                                │
│                          15 familles · 62 events                          │
│                          SSE + WS + JSONL                                 │
│                          ═══════════════                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Decision Engine — L'Orchestrateur

Le Decision Engine est le **chef d'orchestre** qui fait travailler tous les outils ensemble. C'est notre alternative à n8n.

### 6.1 Pourquoi pas n8n — la version définitive

| n8n | Notre Decision Engine |
|-----|----------------------|
| « Installez 300+ nodes » | « Tous nos outils sont déjà des nodes » |
| « Créez un workflow visuel » | « Écrivez 20 lignes de YAML » |
| « Exportez en JSON » | « Git commit + PR review » |
| « Debug via l'UI » | « `--dry-run` + logs JSONL » |
| « 500 MB de conteneur » | « 0 MB — intégré à l'Engine » |
| « workflows non-déterministes » | « State machine 100% reproductible » |

### 6.2 Anatomie d'un workflow Decision Engine

```yaml
# Chaque workflow = une combinaison d'outils orchestrée
name: "deploy-and-verify"
triggers:
  - event: "system.deploy_triggered"
  - cron: "0 3 * * *"        # fallback nightly

steps:
  - id: pull
    tool: forgejo             # outil #24
    action: git_pull

  - id: build
    tool: dockge              # outil #23
    action: compose_up
    services: [odysseus, cbm, graphify]

  - id: health
    tool: uptime_kuma         # outil #25
    action: check_all

  - id: test
    tool: opencode_engine     # outil #1
    action: spawn_agent
    agent: test-engineer

  - id: notify
    tool: gotify              # outil #26
    action: push
    title: "Déploiement {{ status }}"
```

**5 outils combinés en 20 lignes de YAML.** Versionné dans Forgejo. Revu par PR. Exécuté de façon déterministe.

---

## 7. Workflows Combinatoires Concrets

### 7.1 Déploiement Complet (1 clic)

```
git push → Forgejo → webhook → Decision Engine
  → Dockge: rebuild containers
  → Uptime Kuma: health check 17 services
  → OpenCode Engine: run test suite (test-engineer agent)
  → Gotify: notif résultat
  → LangFuse: log déploiement
  → Obsidian: note de déploiement dans le vault
```

**7 outils chainés.** Temps total : ~3 minutes.

### 7.2 Auto-Réparation d'un Service

```
Uptime Kuma: Scrapling DOWN (3 échecs)
  → Gotify: alerte immédiate
  → Decision Engine: workflow auto-heal
      → Dockge: restart scrapling
      → Uptime Kuma: re-check
      → Si toujours DOWN:
          → Gotify: notif critique
          → Decision Engine: active Browser-Harness en fallback
          → Obsidian: log incident
      → Si UP:
          → Gotify: notif "auto-réparé en 12s"
```

**5 outils.** Temps de réaction : < 30 secondes.

### 7.3 Distillation de Mémoire (fin de projet)

```
Agent termine BUILD
  → Event Bus: phase_exit.MEMORY_OBSERVE
  → Decision Engine: workflow memory-distillation
      → CodeBurn: extrait métriques du run
      → Graphify: extrait les concepts clés
      → Acontext: génère une leçon structurée
      → ChromaDB: vérifie si la leçon existe déjà
      → Obsidian: écrit dans le vault (si nouvelle)
      → Meilisearch: indexe pour recherche future
      → Gotify: notif si nouveau skill détecté
```

**7 outils.** Chaque run nourrit le suivant. Apprentissage continu.

### 7.4 Rotation de Modèle (blacklist auto)

```
ZenRouter: 5 erreurs consécutives sur minimax-m3
  → Event Bus: model.blacklisted
  → Decision Engine: workflow model-rotation
      → ZenRouter: bascule sur deepseek-v4-pro
      → LangFuse: log l'incident
      → Gotify: notif admin
      → Decision Engine: schedule retry dans 30 min
```

**3 outils.** Zero intervention humaine.

### 7.5 Sécurité — Détection d'Anomalie

```
Security Event: tool_blocked (rm -rf / tenté)
  → Event Bus: security.block
  → Decision Engine: workflow security-incident
      → Supabase: snapshot DB au moment du blocage
      → Obsidian: rapport d'incident
      → Gotify: alerte CRITICAL
      → AdGuard Home: ban IP temporaire (si pattern répété)
      → Forgejo: commit du rapport d'incident
```

**5 outils.** Traçabilité complète.

### 7.6 Nightly Maintenance

```
Cron 4h00 → Decision Engine
  → Dockge: docker system prune
  → ChromaDB: compact vectors
  → Supabase: pg_dump
  → Obsidian: backup vault → chiffré
  → Forgejo: push backups
  → Dockge: check màj images Docker
  → Gotify: résumé "Nightly OK: 2 backups, 0 erreurs"
```

**6 outils.** Automatique, silencieux, fiable.

---

## 8. Roadmap d'Intégration

### Vision Globale : du socle actuel au système complet

```
SEMAINE 1 : Fondation (P0)           ──── 30 min
  ├── Activer Obsidian vault
  ├── Docker login CBM registry (token)
  └── Goal-ancestry live
       ↓ Score : 83% → 91%

SEMAINE 2 : Observabilité (P1)       ──── 2 h
  ├── Installer Uptime Kuma + config 17 monitors
  ├── Installer Gotify + lier à Uptime Kuma
  ├── Installer Dockge + pointer notre compose
  ├── Installer Vaultwarden + migrer les secrets .env
  ├── Activer LangFuse pour traces LLM
  └── npm link @agentos/sfd-*
       ↓ Score : 91% → 96%

SEMAINE 3 : CI/CD (P1–P2)            ──── 3 h
  ├── Installer Forgejo + config CI runner
  ├── Workflow Deploy & Verify
  ├── Workflow Auto-Heal
  ├── Workflow Security Incident
  └── Déploiement VPS
       ↓ Score : 96% → 98%

SEMAINE 4 : Optimisation (P3)        ──── 9 h
  ├── Dashboard Trinité unifié
  ├── Workflow Memory Distillation
  ├── Workflow Model Rotation
  ├── Workflow Nightly Maintenance
  ├── Auto-skills generation (Acontext)
  └── Per-agent model routing live
       ↓ Score : 98% → 100%
```

**Total : 14.5 heures sur 4 semaines** pour passer de 83% à 100%.

---

## Synthèse — Les 5 Règles d'Or de la Combinaison

| # | Règle | Explication |
|---|-------|------------|
| **R1** | **Toute brique expose `/health`** | Sinon Uptime Kuma ne peut pas la monitorer |
| **R2** | **Toute action émet un événement** | Sinon le Decision Engine ne peut pas réagir |
| **R3** | **Toute brique a un fallback** | Scrapling → Browser-Harness, modèle A → modèle B |
| **R4** | **Tout secret passe par Vaultwarden** | Jamais de `.env` en clair dans le repo |
| **R5** | **Tout workflow est un fichier YAML dans Forgejo** | Versionné, revu, audité, reproductible |

---

> **Documents connexes :**
> - [`01-SFD-v3.1.md`](./01-SFD-v3.1.md) — La spec normative
> - [`05-EVENT-BUS.md`](./05-EVENT-BUS.md) — Les 62 événements qui alimentent ces combos
> - [`06-ENGINE-OUTILS.md`](./06-ENGINE-OUTILS.md) — Mapping outils par phase SFD
> - [`../traceability/TRACEABILITY.md`](../traceability/TRACEABILITY.md) — État réel vérifié (source de vérité)
> - [`09-PLAN-ACTIONS-RESTANTES.md`](./09-PLAN-ACTIONS-RESTANTES.md) — Les 9 actions pour atteindre 100%
