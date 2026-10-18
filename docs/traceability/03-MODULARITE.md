# 03 — Analyse de modularité — AgentOS

*Généré: 2026-09-25 · branche `feat/inventaire-global-v1` · analyse statique en lecture seule (329 fichiers `.py`, ~2 809 statements d'import internes, 959 arêtes uniques)*

> Objectif du projet : système **holistique et modulaire** — briques interchangeables, technologies remplaçables.
> Ce document mesure l'écart entre l'objectif et le code réel, sans rien modifier.

## Méthode

Scripts shell/Python en **lecture seule** (aucune écriture dans le dépôt) :

- Parsing `ast` des imports `src.*`, `core.*`, `routes.*`, `services.*`, `mcp_servers.*`, `companion.*` dans `src/`, `routes/`, `core/`, `services/`, `mcp_servers/`, `companion/`, plus `app.py`, `launcher.py`, `launch_fast.py`.
- Normalisation de chaque cible au module-fichier réel (ex. `from src.orchestrator.registry import AgentRegistry` → `src.orchestrator.registry`).
- Comptage des dépendances **entrantes** (nombre de fichiers distincts qui importent un module = *afferent coupling*) et **sortantes** (nombre de modules internes distincts importés = *efferent coupling*).
- Détection des cycles (`A→B` et `B→A`) et des inversions d'architecture (`src/*` ou `services/*` important `routes.*`).

Le graphe n'est **pas** un graphe d'exécution (les imports paresseux dans les fonctions sont comptés comme des arêtes réelles, car ils traduisent un couplage effectif).

---

## 1. Carte des briques et points d'extension

| Brique | Emplacement | Mode de chargement | Point d'extension | Verdict |
|---|---|---|---|---|
| **Route loader** | `core/route_loader.py` · appelé par `app.py:343` | **Statique** — 58 imports codés en dur + `app.include_router(...)` × 60, **aucune** découverte auto | Ajouter/éditer une fonction `setup_*_routes()` puis l'appeler dans `register_all_routes()` | ⚠️ **Couplée** (hub de boot) |
| **Packages npm `@agentos/sfd-*`** | `packages/` (10 workspaces TS) | Workspace npm ; seul `sfd-eventbus` est branché (`opencode.json` → `plugin[]`, `Dockerfile:98-100`) | Créer un package + l'ajouter à `packages/package.json` et à `opencode.json` | ✅ **Interchangeable** (mais 9/10 non branchés) |
| **Serveurs MCP** | `mcp_servers/` (6 serveurs Python) + MCP externes Docker | stdio via `McpManager`; enregistrement dans `src/builtin_mcp.py` (`_BUILTIN_SERVERS` + `_optional_python_servers()`) | Ajouter une entrée dans le dict, ou enregistrer un serveur externe via `routes/mcp_routes.py` | ✅ **Interchangeable** (interface MCP standard) |
| **Agents** | `.opencode/agents/` (20 fichiers `.md`) | **Découverte dynamique** par `glob("*.md")` — `src/orchestrator/registry.py`; parsing `src/orchestrator/spec.py` | Déposer un `.md` dans le dossier (auto-découvert) | ✅ **Interchangeable** pour l'ajout de spec ; ⚠️ orchestration couplée (voir §3) |
| **Skills** | `.opencode/skills/` (3) + `skills/` (11) | `SkillsManager` (`services/memory/skills.py`) sur `DATA_DIR`; découverte `rglob("SKILL.md")`; natif OpenCode | Déposer un dossier `<nom>/SKILL.md` | ✅ **Interchangeable** |
| **Kill-switches** | `src/killswitch_registry.py` | Registre **read-only** pur (35 switches + 12 switches d'agents = **47 entrées**), lu par `routes/killswitch_routes.py` (1 seul importateur) | Ajouter une entrée `_SWITCHES` / `_AGENT_SWITCHES` | ✅ **Interchangeable** (le registre) — ⚠️ l'application effective est dispersée dans `os.environ` |
| **Providers de modèles** | `model-routing.json` · `core.database.ModelEndpoint` + `src/endpoint_resolver.py` · `opencode.json` | ZenRouter recharge `model-routing.json` sur mtime (`src/zen_router.py`); DB lue à chaud | JSON `providers{}` + `models{}` + `fallback_chains{}`, **ou** enregistrer un `ModelEndpoint` en DB | ⚠️ **Couplée** — 3 sources de vérité concurrentes |
| **Services Docker** | `docker-compose.yml` (33 services) + 3 overlays GPU/isolated | Conteneurs ; hostnames/ports injectés par env (`CHROMADB_HOST`, `SEARXNG_INSTANCE`, `QDRANT_URL`…) | Ajouter un service compose + une variable d'env + un probe `src/service_health.py` | ✅ **Interchangeable** au niveau conteneur ; ⚠️ couplage implicite par hostname/port |
| **Providers mémoire** | `src/memory_provider.py` + `services/memory/{letta,mem0}_provider.py` | ABC `MemoryProvider` + `MemoryProviderRegistry` (register/get/all) | Implémenter `MemoryProvider` puis `registry.register()` | ✅ **Interchangeable** — **modèle de référence du projet** |
| **Providers de recherche** | `services/search/providers.py` | Table `PROVIDER_INFO` (7 entrées : searxng, brave, duckduckgo, google_pse, tavily, serper, disabled) + dispatch | Ajouter une entrée + branche de dispatch | ✅ **Interchangeable** (avec dispatch à compléter) |
| **Outils** | `src/tools/` (11) + `src/agent_tools/` (façade) | Dict statique `TOOL_HANDLERS` (`src/agent_tools/__init__.py`) ; `src/tool_registry.py` (briques YAML) | Enregistrer un handler ; déclarer une brique dans `config/tool-decision-tree.yaml` | ⚠️ **Couplée** (dict statique + imports `routes.*` + singletons globaux) |
| **Event bus** | `src/event_bus.py` (Python) ↔ `@agentos/sfd-eventbus` (TS) | Singleton Python importé par 19 modules ; plugin TS côté OpenCode | Abonnement `.on(type)` / émission `.emit()` | ⚠️ **Semi-couplée** — 2 implémentations parallèles du même concept |

---

## 2. Graphe de dépendances (analyse statique)

### 2.1 Chiffres clés

| Indicateur | Valeur |
|---|---|
| Fichiers Python scannés | **329** |
| Arêtes internes uniques (module → module) | **959** |
| Statements d'import internes bruts | **~2 809** |
| Cycles courts (`A↔B`) détectés | **8** |
| Inversions `src/*` ou `services/*` → `routes.*` | **~30 arêtes** |
| Modules SFD/racine les plus importés (god node) | `core.database` (64) |
| Module le plus dépendant | `core.route_loader` (58) |
| Endpoints HTTP (décorateurs `@app/@router`) | **523** dans `routes/` (63 fichiers) + `app.py` |

### 2.2 God nodes — les nœuds les plus couplés (importés par le plus de modules)

Un **god node** est un module dont le changement de signature casse le plus de monde.

| Rang | Module | Importateurs distincts | Nature |
|---|---|---:|---|
| 1 | `core.database` | **64** | Cœur de données (SQLAlchemy, modèles, `SessionLocal`) |
| 2 | `src.constants` | **61** | Constantes globales (chemins, clés, timeouts) |
| 3 | `src.auth_helpers` | **42** | Auth transverse (routes + services) |
| 4 | `src.llm_core` | **33** | **Shim** → `archive/legacy/llm_core.py` |
| 5 | `src.endpoint_resolver` | **28** | Résolution d'endpoint provider-agnostique |
| 6 | `src.settings` | **28** | Réglages admin + prefs |
| 7 | `core.middleware` | **28** | Middlewares sécurité |
| 8 | `src.event_bus` | **19** | Bus d'événements applicatif |
| 9 | `src.database` | **16** | Façade DB (shim par domaine) |
| 10 | `core.constants` | **15** | Constantes cœur |
| 11 | `core.models` | **14** | Modèles d'API/chat |
| 12 | `routes.prefs_routes` | **14** | ⚠️ **Un module de route importé par 14 autres** |
| 13 | `src.secret_storage` | **14** | Chiffrement des secrets |
| 14 | `core.atomic_io` | **13** | Écritures atomiques |
| 15 | `core.platform_compat` | **12** | Compatibilité OS |
| 16 | `src.ai_interaction` | **12** | Façade outils LLM (singletons globaux) |
| 17 | `src.tool_implementations` | **12** | Façade implémentations d'outils |
| 18 | `core.auth` | **11** | `AuthManager` |
| 19 | `routes.email_helpers` | **10** | ⚠️ Helper d'une route partagé par `src/*` |
| 20 | `src.task_endpoint` | **10** | Résolution d'endpoint de tâche |
| — | `src.text_helpers`, `src.tools._common` | 10 | Utilitaires |

**Lectures :**
- Les 4 premiers god nodes (`core.database`, `src.constants`, `src.auth_helpers`, `src.llm_core`) concentrent **200 arêtes entrantes** à eux seuls → toute rupture de contrat est systémique.
- La présence de `routes.prefs_routes` et `routes.email_helpers` dans le top 20 est un **smell architectural majeur** : des modules de *présentation HTTP* sont devenus des *bibliothèques partagées*.
- `src.llm_core` est un **shim** : 33 modules dépendent d'un fichier de compatibilité qui ne contient aucune logique, et pointent en réalité vers `archive/legacy/`. `src/agent_loop` (shim jumeau) a 7 importateurs. Au total, **71 fichiers (tests inclus)** importent `src.llm_core` ou `src.agent_loop`.

### 2.3 Modules les plus dépendants (efferent coupling)

| Rang | Module | Cibles internes distinctes | Rôle |
|---|---|---:|---|
| 1 | `core.route_loader` | **58** | Enregistre toutes les routes (hub de boot) |
| 2 | `routes.chat_routes` | **31** | Route chat — importe 4 autres routes |
| 3 | `app.py` | **24** | Câblage global au démarrage |
| 4 | `src.task_scheduler` | **23** | Scheduler — importe 3 routes |
| 5 | `src.builtin_actions` | **21** | Actions built-in — importe 4 routes |
| 6 | `src.app_initializer` | **18** | Construit tous les managers |
| 7 | `routes.document_routes` | **18** | Route documents |
| 8 | `routes.chat_helpers` | **15** | Helpers chat |
| 9 | `routes.cookbook_routes` | **15** | Route cookbook |
| 10 | `routes.email_routes` | **14** | Route email |

### 2.4 Détection d'anti-patterns

**Cycles courts (`A↔B`, 8 détectés)** :
`src.builtin_actions ↔ src.document_actions` · `src.caldav_sync ↔ src.caldav_writeback` · `src.tool_parsing ↔ src.tool_schemas` · `src.tool_implementations ↔ src.tools.{contacts,cookbook,image,research,system}`.

**Inversions d'architecture (`src/` → `routes/`)** — un module métier importe la couche HTTP, souvent via des imports paresseux en fonction (contournement de cycle) :

| Source (`src/`, `services/`, `mcp_servers/`) | Importe depuis `routes.*` |
|---|---|
| `src.builtin_actions` | `email_pollers`, `email_helpers`, `skills_routes`, `note_routes` |
| `src.task_scheduler` | `email_helpers`, `email_routes`, `prefs_routes` |
| `src.settings` | `prefs_routes` (`_load_for_user`) |
| `src.ai_interaction` | `prefs_routes` (`_load`) |
| `src.caldav_sync` | `prefs_routes` (`_load_for_user`, `_save_for_user`) |
| `src.service_health` | `email_helpers`, `model_routes` |
| `src.tools.{calendar,cookbook,notes,system}` | `calendar_routes`, `cookbook_helpers`, `_validators`, `prefs_routes` |
| `services.memory.skill_extractor` | `prefs_routes` |
| `mcp_servers.email_server` | `email_helpers` |

**Imports inter-routes** (une route importe une autre route) :
`chat_routes → {email_routes, model_routes, research_routes, session_routes, chat_helpers, document_helpers}` ; `codex_routes → {calendar_routes, document_routes, email_routes, …}` ; `cookbook_routes → {model_routes, shell_routes, …}` ; `note_routes → email_routes` ; `document_routes → email_routes` ; `history_routes → session_routes` ; `compare_routes → session_routes`.

---

## 3. Verdict par brique

### ✅ Interchangeables (remplacement local, sans impact systémique)

| Brique | Justification |
|---|---|
| **Providers mémoire** (`src/memory_provider.py`, `services/memory/*_provider.py`) | Vrai pattern *Strategy/Adapter* : ABC `MemoryProvider` + `MemoryProviderRegistry.register()`. Ajouter/retirer Letta, Mem0, Acontext ou natif ne touche qu'un enregistrement. **À ériger en standard.** |
| **Skills** (`skills/`, `.opencode/skills/`) | Fichiers `SKILL.md` autonomes, découverte par glob, aucune référence croisée. |
| **Serveurs MCP Python** (`mcp_servers/`) | Frontière de processus + protocole MCP standard. *Réserve* : `email_server.py` importe `routes.email_helpers` (inversion à corriger). |
| **Packages npm `@agentos/sfd-*`** | Isolation totale : chaque package ne dépend que de `@opencode-ai/plugin`. *Réserve* : 9/10 packages non branchés (dette d'intégration, pas de couplage). |
| **Kill-switch registry** (`src/killswitch_registry.py`) | Module pur (aucune I/O, aucune mutation d'env), 1 seul importateur. |
| **Providers de recherche** (`services/search/providers.py`) | Table déclarative `PROVIDER_INFO`, 7 backends interchangeables à l'exécution. |
| **Services Docker** (mail, vector, notifications, TTS/STT, diagrammes…) | Chaque technologie (ChromaDB, Qdrant, Meilisearch, SearXNG, Kroki, ntfy, LocalAI…) est un conteneur remplaçable, exposé par env. |
| **Agents** (ajout de spec) | Découverte `glob("*.md")` + parsing défensif. |

### ⚠️ Couplées (remplacement coûteux, effets de bord larges)

| Brique | Nature du couplage | Preuve |
|---|---|---|
| **`core/route_loader.py`** | Hub statique de boot : 58 imports codés en dur, aucune découverte. Ajouter une route = éditer un fichier central. | 58 cibles distinctes, 1 point d'entrée unique (`app.py:345`) |
| **`src/llm_core.py` / `src/agent_loop.py`** | Shims vers `archive/legacy/`. Le vrai moteur est hors arborescence; 71 fichiers en dépendent indirectement. | 33 + 7 importateurs, `core/__init__.py` en tête de chaîne |
| **`src/agent_tools`** + **`src/ai_interaction`** + **`src/tool_utils`** | État global mutable injecté par setters (`set_mcp_manager`, `set_memory_manager`, `set_session_manager`…) → dépendances implicites non testables en isolation. | `_session_manager=None`, `_mcp_manager=None`, singletons module-level |
| **`src/builtin_actions`, `src/task_scheduler`, `src/settings`** | Inversion de dépendance vers `routes.*` via imports paresseux (contournement de cycle). | ~30 arêtes `src→routes` |
| **`routes.chat_routes`, `codex_routes`, `cookbook_routes`** | Routes couplées à d'autres routes (jusqu'à 6 imports inter-routes). | `chat_routes` → 31 cibles internes |
| **Routage modèle** (`model-routing.json` + DB + `opencode.json`) | Trois sources de vérité concurrentes; mapping `providers_litellm` codé en Python; `_DEFAULT_ZEN_MODEL` en dur. | `src/zen_router.py`, `src/orchestrator/router_advice.py`, `src/intent_gate.py` |
| **Outils** (`src/agent_tools/__init__.py`) | Enregistrement statique `TOOL_HANDLERS`, chaîne de ré-export, singletons. | dict de ~30 handlers codés en dur |
| **Event bus** | Deux implémentations dupliquées (Python `src/event_bus.py` et TS `@agentos/sfd-eventbus`) → risque de divergence de contrat. | 19 importateurs Python, 1 plugin TS |

### 🔒 Cœur (ne peut pas être remplacé sans réécriture ; à stabiliser/figer derrière une interface)

| Module | Rôle | Importateurs |
|---|---|---:|
| `core.database` | Persistance (SQLAlchemy), modèles, `SessionLocal` | 64 |
| `src.constants` | Constantes globales de chemin/config | 61 |
| `src.auth_helpers` | Contrat d'authentification transverse | 42 |
| `core.middleware` / `core.auth` / `core.models` | Sécurité, auth, modèles | 28 / 11 / 14 |
| `src.settings` | Réglages admin + prefs utilisateur | 28 |
| `src.endpoint_resolver` | Résolution d'endpoint provider | 28 |
| `app.py` + `core/startup.py` + `core/route_loader.py` | Cycle de vie et câblage | 24 |
| `src/opencode_engine.py` | « THE single engine » (EventBus Python, phases, budget) | 2 directs (`decision_engine`, `chat_routes`) — mais cœur fonctionnel |

---

## 4. Dépendances dures (fichiers/config dont le changement casse tout)

| Fichier | Pourquoi c'est dur | Rayon d'impact |
|---|---|---|
| **`app.py`** | Câble 24 modules, crée `app.state.*`, appelle `register_all_routes()`, branche le lifespan. | Tout le boot ; 523 endpoints |
| **`core/route_loader.py`** | 58 imports codés en dur, un seul point d'enregistrement. Toute route renommée/absente fait échouer le boot. | 60 routeurs / 523 endpoints |
| **`model-routing.json`** | Lu à chaud par `zen_router` (rechargement sur mtime) ; les signaux `heuristic.strong_signals` sont dupliqués dans `src/intent_gate.py` ; des tests asservissent le catalogue (`tests/test_zen_no_phantom_model.py`). | Tout le routage modèle + tests |
| **`opencode.json`** | Charge le plugin `@agentos/sfd-eventbus`, définit modèles et agents pour le CLI OpenCode. | Exécution OpenCode (plugins, agents, modèles) |
| **`docker-compose.yml`** | 33 services ; hostnames/ports consommés en dur par le code (`chromadb`, `searxng`, `qdrant`, `meilisearch`, `localai`…). | Services externes + `/api/services` |
| **`src/opencode_engine.py`** | Moteur central (EventBus Python, 7 phases, budget, outils/agents par phase). | `src/decision_engine.py`, `routes/chat_routes.py` |
| **`src/llm_core.py` / `src/agent_loop.py`** | Shims dont le contenu réel vit dans `archive/legacy/`. Les déplacer/supprimer casse `core/__init__.py` et 71 importeurs. | 71 fichiers |
| **`src/orchestrator/agent_dispatcher.py` + `src/killswitch_registry.py`** | Mapping phase→agent et switches codés en dur (au-delà de la découverte dynamique des `.md`). | Orchestration des agents |
| **`config/tool-decision-tree.yaml` + `config/phase-lock.yaml` + `config/policies/*.rego`** | Politiques de phase/outils lues par `src/tool_registry.py` et OPA (`decision-engine`, `opa`). | Gating outils/phases |

---

## 5. Top 20 des modules les plus importés + Top 10 des plus dépendants

### 5.1 Top 20 — dépendances entrantes (god nodes)

| # | Module | Importateurs | Catégorie (§3) |
|---:|---|---:|:--:|
| 1 | `core.database` | 64 | 🔒 cœur |
| 2 | `src.constants` | 61 | 🔒 cœur |
| 3 | `src.auth_helpers` | 42 | 🔒 cœur |
| 4 | `src.llm_core` *(shim)* | 33 | ⚠️ couplée |
| 5 | `src.endpoint_resolver` | 28 | 🔒 cœur |
| 6 | `src.settings` | 28 | 🔒 cœur |
| 7 | `core.middleware` | 28 | 🔒 cœur |
| 8 | `src.event_bus` | 19 | ⚠️ couplée |
| 9 | `src.database` | 16 | ⚠️ couplée (façade) |
| 10 | `core.constants` | 15 | 🔒 cœur |
| 11 | `core.models` | 14 | 🔒 cœur |
| 12 | `routes.prefs_routes` | 14 | ⚠️ couplée (smell) |
| 13 | `src.secret_storage` | 14 | 🔒 cœur (sécurité) |
| 14 | `core.atomic_io` | 13 | 🔒 cœur (I/O) |
| 15 | `core.platform_compat` | 12 | 🔒 cœur (OS) |
| 16 | `src.ai_interaction` | 12 | ⚠️ couplée (singletons) |
| 17 | `src.tool_implementations` | 12 | ⚠️ couplée (façade) |
| 18 | `core.auth` | 11 | 🔒 cœur |
| 19 | `routes.email_helpers` | 10 | ⚠️ couplée (smell) |
| 20 | `src.task_endpoint` | 10 | ⚠️ couplée |

*(ex æquo au rang 20 : `src.text_helpers`, `src.tools._common` — 10 chacun.)*

### 5.2 Top 10 — dépendances sortantes (modules les plus dépendants)

| # | Module | Cibles internes | Catégorie |
|---:|---|---:|:--:|
| 1 | `core.route_loader` | 58 | ⚠️ couplée (hub) |
| 2 | `routes.chat_routes` | 31 | ⚠️ couplée |
| 3 | `app.py` | 24 | 🔒 cœur (câblage) |
| 4 | `src.task_scheduler` | 23 | ⚠️ couplée |
| 5 | `src.builtin_actions` | 21 | ⚠️ couplée |
| 6 | `src.app_initializer` | 18 | ⚠️ couplée |
| 7 | `routes.document_routes` | 18 | ⚠️ couplée |
| 8 | `routes.chat_helpers` | 15 | ⚠️ couplée |
| 9 | `routes.cookbook_routes` | 15 | ⚠️ couplée |
| 10 | `routes.email_routes` | 14 | ⚠️ couplée |

*(ex æquo au rang 10 : `routes.note_routes`, `routes.task_routes` — 14.)*

---

## 6. Recommandations — où casser les couplages en priorité

Classées par ratio **impact modularité / effort**.

1. **Rendre `route_loader` réellement dynamique.** Remplacer les 58 imports codés en dur par une découverte (`pkgutil.iter_modules(routes.__path__)` ou manifest `config/routes.yaml`) sur convention `setup_<name>_routes()`. Bénéfice : ajouter une route devient purement additif ; supprime le nœud le plus dépendant du graphe.
2. **Inverser les 30 arêtes `src/* → routes.*`.** Extraire la logique métier des modules de route (`email_helpers`, `prefs_routes._load_for_user/_save_for_user`, `skills_routes._run_skill_test_once`, `note_routes.dispatch_reminder`, `calendar_routes.parse_due_for_user`) vers `services/` ou `src/`, et faire des routes de simples adaptateurs HTTP. Casse les cycles et rend `builtin_actions`/`task_scheduler`/`settings` testables isolément.
3. **Unifier la source de vérité du routage modèle.** Désigner `core.database.ModelEndpoint` (via `src/endpoint_resolver.py`) comme source unique ; traiter `model-routing.json` comme *seed* de démarrage uniquement. Supprimer la table `providers_litellm` codée en Python, `_DEFAULT_ZEN_MODEL`, et la duplication des signaux heuristiques dans `src/intent_gate.py`.
4. **Éliminer les shims `src/llm_core.py` / `src/agent_loop.py`.** Rapatrier `archive/legacy/` dans un vrai package versionné (`src/legacy/` avec façade dépréciée) ou migrer les 71 importeurs. Un shim qui re-exporte `*` masque le graphe réel et empêche tout remplacement.
5. **Remplacer les singletons globaux par l'injection.** `src/ai_interaction`, `src/agent_tools`, `src/tool_utils`, `src/assistant_log`, `memory_provider.set_active_registry` utilisent des setters globaux. Introduire un conteneur de contexte (`AppContext`) passé explicitement, ou au minimum des `Protocol` injectables.
6. **Extraire un contrat DB.** `core.database` (64 importateurs) doit exposer une interface (`Protocol`/repository) pour que l'implémentation SQLAlchemy soit remplaçable et testable (DB en mémoire).
7. **Généraliser le pattern `MemoryProvider`.** Créer des ABC équivalents pour chaque technologie externe : `VectorStore`, `SearchProvider`, `NotificationChannel`, `TTSEngine`, `STTEngine`. Objectif : qu'aucun module métier n'appelle directement un hostname Docker.
8. **Découpler les outils de `routes`.** Rendre `TOOL_HANDLERS` déclaratif (chaque module d'outil s'auto-enregistre) et supprimer les imports `routes.*` depuis `src/tools/*` et `src/builtin_actions`.
9. **Trancher le statut TS.** Soit brancher les 9 packages `@agentos/sfd-*` non utilisés (dans `opencode.json` / `packages/package.json`), soit les archiver. Le doublon Python/TS du bus d'événements doit être arbitré (une seule source de contrat).
10. **Découpler les agents de l'orchestration.** Le mapping `_PHASE_AGENTS`/`_EXPLICIT_AGENTS` et les switches devraient être déclaratifs (front-matter YAML dans le `.md`, ou `config/agents.yaml`) pour que déposer un agent suffise à l'activer.
11. **Instrumenter le graphe en CI.** Le script d'analyse de ce document peut devenir un job qui échoue si un god node dépasse un seuil (ex. > 40 importateurs) ou si une nouvelle arête `src→routes` apparaît.

---

## 7. Synthèse

### Les 5 couplages les plus critiques

1. **`core.database` — 64 importateurs.** Nœud le plus central ; aucune abstraction de persistance. Toute évolution de schéma se propage à tout le dépôt.
2. **`core/route_loader.py` — 58 imports codés en dur.** Point de boot monolithique : ajouter une route exige d'éditer un fichier central, et toute signature de routeur devient un contrat global.
3. **Inversion de dépendance `src/* → routes.*` (~30 arêtes).** Des modules métier (`builtin_actions`, `task_scheduler`, `settings`, `ai_interaction`, `tools/*`) dépendent de la couche HTTP via des imports paresseux — preuve que le couplage est subi, pas choisi.
4. **Shims `src/llm_core.py` / `src/agent_loop.py` → `archive/legacy/`.** 71 fichiers dépendent d'un moteur hors arborescence, masqué derrière un re-export `*`. C'est le principal obstacle à la « technologie remplaçable » du cœur LLM.
5. **Routage modèle à trois sources de vérité** (`model-routing.json`, `ModelEndpoint` en DB, `opencode.json`) + mappings codés en Python. Remplacer un provider LLM exige aujourd'hui de toucher plusieurs fichiers et des tests.

### Les 5 briques les plus remplaçables

1. **Providers mémoire** (`src/memory_provider.py` : ABC + registre) — interchangeables sans modifier les appelants. **Modèle à répliquer.**
2. **Skills** (`skills/`, `.opencode/skills/` : `SKILL.md` découverts par glob) — briques totalement autonomes.
3. **Serveurs MCP** (`mcp_servers/`, frontière processus + protocole standard) — seul le serveur `email` traîne une inversion à corriger.
4. **Packages npm `@agentos/sfd-*`** (isolation TS totale) — remplaçables/supprimables individuellement ; à condition de trancher leur branchement.
5. **Kill-switch registry** (`src/killswitch_registry.py`, module pur, 1 importateur) — surface minimale, aucune dépendance sortante significative.

*(Mention honorable : les **services Docker** et les **providers de recherche**, remplaçables au niveau de la configuration, sous réserve d'extraire les hostnames/ports derrière les interfaces recommandées au §6.7.)*

---

*Fin de l'analyse. Aucun fichier de code n'a été modifié ; seuls des scripts de parsing temporaires ont été exécutés.*
