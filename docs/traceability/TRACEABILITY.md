# AgentOS — TRACEABILITY (document maître)

> **Objet :** combler la lacune de traçabilité. Répondre à : *qu'est-ce qui est fait, fonctionnel, prévu, et comment c'est fait ?*
> **Méthode :** analyse statique du code réel (branche `feat/inventaire-global-v1`), vérification d'existence, croisement avec les specs `docs/master-ref/`.
> **Date :** 2026-09-26 (après activation du Palier 0) · **Dernier commit de travail :** 2026-08-04 (`e077b3f`) · **Backup :** 2026-09-22.
> **Sous-documents :** `00-CODE-INVENTORY.md`, `01-SFD-TRACEABILITY.md`, `02-PRINCIPES-UC.md`, `03-MODULARITE.md`, `04-TESTS-REALITE.md`, `../veille/VEILLE-FEATURES.md`.

---

## TL;DR — le verdict

1. **Le projet est bien plus large que ce que la doc prétend.** `03/07` annoncent « Odysseus élagué → ~15 routes / ~50 fichiers » ; la réalité est **63 fichiers de routes, 503 endpoints, 1 071 fichiers Python actifs**. La « réduction » documentée n'a pas eu lieu.
2. **Les scores des docs sont maintenant uniques et vérifiables.** `04`=59 %, `09`=83 %, `08`=90 % ont été remplacé par un score recalculé depuis le code : **10/41 ACTIF, 28 PARTIEL, 1 DORMANT, 2 ABSENT** — soit **~60 % de couverture, ~24 % d'activation**.
3. **Le Palier 0 a supprimé les switchs OFF, et révélé le vrai taux d'inactivité.** Les 14 kill-switchs P0 sont **`on` par défaut dans le code** (plus seulement dans `.env`) : DORMANT 5 → 1. Mais ACTIF 12 → 10 — en branchant les modules, on a constaté que plusieurs ne consumaient pas leur résultat, et que **UC-01** attend une `OPENCODE_API_KEY` absente. L'écart résiduel n'est plus « des switchs », c'est **du câblage**.
4. **Le cockpit des kill-switchs ne peut plus mentir.** 9 descripteurs n'avaient **aucun lecteur** et étaient présentés comme actifs : ils sont maintenant `wired=False` + `off`, et **4 tests d'auto-police** rendent la dérive non réintroduisible.
5. **La modularité est réelle mais inégale** : bons points (packages npm, MCP, skills, `MemoryProvider`), mauvais points (`core.database` importé par 64 modules, `route_loader` non dynamique, shims vers `archive/legacy/`).
6. **La suite de tests est verte et le projet s'exécute localement** : 4 887 PASS (contre 4 633 + 109 non-verts au départ). Réserve : le « 100 % vert » est **local** — ChromaDB, Mem0, LLM et Docker sont injoignables, donc les chemins nominaux ne sont pas testés.
7. **Un défaut d'atteignabilité, trouvé au Sprint 3, expliquait l'Activation plate.** Le bloc M6 — qui porte P16, P17, P19, P20, P22 — était **injoignable depuis la route de chat principale** : un classifieur d'intention trop étroit marquait « low-signal » la plupart des demandes réelles, la voie directe `return`ait avant M6, et `routes/chat_routes.py:1388` ne passe pas `relevant_tools`. Un tour réel donnait **0 événement M6**. Le classifieur est corrigé ; les tests le prouvent en appelant la boucle **comme le fait la route principale**. Détail et mesure : `02-PRINCIPES-UC.md` §4.6.
8. **Le même examen a promoted P5 de PARTIEL à ACTIF (Sprint 3 item 8).** La divulgation progressive calculait une liste d'outils autorisés et se contentait de la **journaliser** : aucun site de la boucle n'appelait `get_allowed_tools`, et le corriger dans M6.8 n'aurait rien changé puisque ce bloc tourne après l'envoi des schémas. Le filtre agit désormais **là où la liste est construite** (`agent_loop.py:3158-3169`). La règle est bornée après mesure : `_TOOL_CATEGORY_MAP` ne connaît que 37 des 68 schémas, donc un filtrage strict aurait supprimé 31 outils dans **toutes** les phases, `BUILD` comprise. Preuve : 11 tests, **4 mutations**, dont celle qui calcule le filtre sans affecter le résultat — le test mesure ce qui est **envoyé**, pas ce qui est calculé. Le même examen a révélé que **`CLASSIFY` n'est jamais atteinte** (`agent_loop.py:3040` avance la boucle canonique avant de résoudre la phase).

---

## 1. Inventaire du code (réel)

| Élément | Volume |
|---|---|
| Fichiers Python actifs (hors `archive/`) | **1 071** |
| Fichiers legacy (`archive/legacy/`) | 2 (`agent_loop.py` 4 418 l., `llm_core.py`) |
| Fichiers de routes | **63** |
| Endpoints HTTP | **503** |
| Modules `src/` | **136** |
| Services (`services/`) | 17 |
| Serveurs MCP (`mcp_servers/`) | 7 |
| Packages npm (`@agentos/sfd-*`) | 10 |
| Agents `.opencode/agents/` | 20 |
| Skills (`skills/` + `.opencode/skills/`) | 12 + 3 |
| Fichiers de test / fonctions `test_*` | 693 / ~4 151 |
| Kill-switches curatés | 67 (**17 ON**, dont **14/14 P0** ; 8 non câblés) — *généré par* `tools/gen_killswitch_tables.py` |

Détail complet : `00-CODE-INVENTORY.md`.

---

## 2. Traçabilité SFD v3.1 ↔ code

### 2.1 Modules fonctionnels (§5.1 → §5.20)
**Tous les 20 modules ont du code présent** (vérifié par existence). Après activation du Palier 0, **aucun principe n'est plus dormant** : l'écart restant n'est plus constitué de switchs OFF mais de modules dont le résultat est calculé puis ignoré. Modules non câblés (`wired=False`, 9 descripteurs) : `02-PRINCIPES-UC.md` §4.1. Détail : `01-SFD-TRACEABILITY.md`.

### 2.2 Principes P1→P22 — vérifiés
| Statut | Nb | IDs |
|---|---:|---|
| ACTIF | **5** | P3, P9, P10, P13, P15 |
| PARTIEL | **17** | P1, P2, P4, P5, P6, P7, P8, P11, P12, P14, P16, P17, P18, P19, P20, P21, P22 |
| DORMANT | **0** | — |
| ABSENT | 0 | — |

### 2.3 Use cases UC-01→UC-19 — vérifiés
| Statut | Nb | IDs |
|---|---:|---|
| ACTIF | **5** | UC-03, UC-04, UC-08, UC-13, UC-14 |
| PARTIEL | **11** | UC-01, UC-02, UC-05, UC-09, UC-11, UC-12, UC-15, UC-16, UC-17, UC-18, UC-19 |
| DORMANT | **1** | UC-10 |
| **ABSENT** | **2** | **UC-06 (fork worktree), UC-07 (merge worktree)** |

> **Total exigences SFD : 41 → 10 ACTIVES, 28 PARTIELLES, 1 DORMANTE, 2 ABSENTES.**
>
> **Mesure du 2026-09-26, après activation du Palier 0** (14 kill-switchs basculés à `on` dans le code, pas seulement dans `.env`) : DORMANT 5 → 1, mais ACTIF 12 → 10. Le score baisse parce qu'il est **plus juste** : en branchant les modules, on a constaté que certains ne faisaient rien de leur résultat, et que **UC-01** attend une `OPENCODE_API_KEY` absente de `.env`. Détail des 20 corrections et des preuves : `02-PRINCIPES-UC.md`.

Détail (fichiers + preuves + divergences avec `08`) : `02-PRINCIPES-UC.md`.

---

## 3. Kill-switches — le levier « activable »

Registre vérifiable : `src/killswitch_registry.py` — **54 descripteurs**, `read_states()` exposant `default`, `raw`, `is_default`, `effective` et **`wired`** (existe-t-il un lecteur réel ?).

**État mesuré le 2026-09-26 :**

| Catégorie | Nombre | Détail |
|---|---:|---|
| P0 **ON par défaut dans le code** | **14** | PHASE_TRACKER, MODEL_ROUTER, PROGRESSIVE_DISCLOSURE, MEMORY_IMPACT, UNIFIED_TOKENS, OUTPUT_ROUTER, PREFERENCES, DATA_CLASSIFICATION, CONTENT_SECURITY, DURABLE_EXECUTION, PROVENANCE_MEMORY, AUTOEVAL, AUTOEVOLVE, CHECKPOINT |
| Descripteurs **non câblés** (`wired=False`, remis à `off`) | **9** | DEEPEVAL, SUPABASE, VAULTWARDEN, PLAYWRIGHT, BROWSER_HARNESS, ZEN_FROM_ENDPOINT, INPROCESS_DISCORD, INPROCESS_TELEGRAM, CHANNEL_AGENT_REPLY |
| ON mais **sous-partie** | — | `ODYSSEUS_LANGGRAPH_INTERRUPT` reste `on`, mais le chemin LangGraph est fermé (`ODYSSEUS_LANGGRAPH` lu `""` puis `off`) ⇒ le gate risque→humain est **inatteignable**. |

> **Décision FND-4 = option C, appliquée.** Le 2026-09-25 le Chef a tranché : l'activation se fait **par paliers**, et **l'activation est le flipping du défaut dans le code**, pas une simple ligne dans `.env` — les 14 lecteurs P0 lisent désormais `os.getenv("ODYSSEUS_X", "on")`, donc l'état tient même sans `.env`.
>
> **Garde-fou ajouté dans la foulée** : `ODYSSEUS_AUTOEVAL_ALLOW_RESET` (**OFF** par défaut). AUTOEVAL peut décider un revert (tracé, retourné) ; seul ce second switch autorise l'action `git reset --hard`. Raison : un reset réel détruit le travail non commité de l'arbre courant. Le chemin live (`archive/legacy/agent_loop.py:4193-4198`) exige désormais `autoeval_enabled() AND destructive_revert_allowed()`.
>
> **4 tests d'auto-police** (`tests/test_killswitch_registry.py`) rendent ce contrat exécable : un descripteur `wired=True` doit avoir un lecteur, un `wired=False` ne doit pas en avoir, et le `default` affiché doit être celui que le code appliquera. Le cockpit ne peut plus mentir.

---

## 4. Modularité — forces et couplages

### 4.1 Les 5 couplages les plus critiques (à casser en priorité)
1. **`core.database` — 64 importateurs.** Aucune abstraction de persistance.
2. **`core/route_loader.py` — 58 imports codés en dur.** Malgré son nom, **pas dynamique** : ajouter une route exige d'éditer un fichier central.
3. **Inversion de dépendance `src/* → routes.*` (~30 arêtes).** Le métier dépend de la couche HTTP (imports paresseux).
4. **Shims `src/llm_core.py` / `src/agent_loop.py` → `archive/legacy/`.** 71 fichiers dépendent d'un moteur hors arborescence masqué par un `re-export *` → principal obstacle à un cœur LLM remplaçable.
5. **Routage modèle à 3 sources de vérité** (`model-routing.json`, `ModelEndpoint` DB, `opencode.json`) + mappings en dur.

### 4.2 Les 5 briques les plus remplaçables (à généraliser)
1. **`src/memory_provider.py`** (ABC + registre) — **le modèle du projet**.
2. **Skills** (`SKILL.md` découverts par glob).
3. **Serveurs MCP** (frontière processus + protocole standard).
4. **Packages npm `@agentos/sfd-*`** (isolation TS ; 9/10 non branchés = dette d'intégration, pas de couplage).
5. **Kill-switch registry** (module pur).

11 recommandations détaillées : `03-MODULARITE.md` §6.

---

## 5. Réalité fonctionnelle (exécution)

- **Suite complète : verte.** **4 887 PASS · 2 skipped · 0 FAILED** (~120 s), sur le `venv` du dépôt. Le point de départ était 4 633 PASS / **109 non-verts**.
- **Les 109 faux échecs** portaient sur les shims `src/*.py` → `archive/legacy/*.py` : le code était **correct à l'exécution** mais insensible au `monkeypatch` des tests. Le code n'avait donc jamais été cassé — il était **invérifiable**.
- **Lint** : `ruff` strict (E,F,I,N,UP,B,C4,SIM,PL…) → **3 707** diagnostics contre une base de **3 708** mesurée sur `HEAD~2` (extrait via `git archive` dans un répertoire temporaire), soit **−1** : le `F821` du bloc M6.8 a disparu. La base n'est pas zéro, elle est **connue** et **ne descend pas**.
- **Limite honnête du « 100 % vert »** : il est **local**. ChromaDB, Mem0, les appels LLM et le moteur Docker sont injoignables ici — les chemins dégradés sont testés, les chemins nominaux non. `OPENCODE_API_KEY` est absente de `.env` (le projet utilise OpenCode Zen) : le flux LLM nominal est donc **non exécutable en l'état** (cf. UC-01).
- **CI** : `ci.yml` = Python 3.11 (pytest `continue-on-error`), `e2e.yml` = 3.14 + ruff.

Détail : `04-TESTS-REALITE.md`.

> ⚠️ **Règle permanente issue de ce chantier : toujours commiter avant de lancer la suite.** Une suite verte a exécuté un `git reset --hard` réel (via AUTOEVAL `on` alimenté par un test fournissant `verifier_reasons`) et a **effacé 14 basculements de kill-switch non commités**.

---

## 6. Divergences doc ↔ code (à corriger dans les docs)

| Sujet | Doc | Réalité |
|---|---|---|
| Taille projet | `03/07` : ~15 routes, ~50 fichiers | 63 routes, 503 endpoints, 1 071 `.py` |
| Couverture | `04`=59 %, `09`=83 %, `08`=90 % | **résolu** — score unique recalculé : **10 ACTIF / 28 PARTIEL / 1 DORMANT / 2 ABSENT** sur 41 |
| UC-06/07 | « codés » | **absents** (aucun `git worktree`) — verdict conservé |
| P18 | 08 : « if_version dans memory_writer » | faux sur deux points : le vrai `if_version` est dans `provenance_memory.py`, et `memory_writer.py` n'a **toujours aucun appelant** |
| Env | `.env` met `on` | **résolu** — les 4 divergences de nommage ont été nettoyées ; une seule variable `ODYSSEUS_*` de `.env` (sur 49) reste sans lecteur Python : `ODYSSEUS_TRAEFIK` (palier P2) |
| Kill-switchs | 2 ON / 33 OFF | **résolu** — 14 P0 à `on` dans le code, 9 descripteurs non câblés marqués `wired=False` |
| Tests | « 0 test exécutable » | **résolu** — 4 887 PASS sur le `venv` du dépôt |

### 6.1 Bugs de nommage des kill-switches — **CORRIGÉS le 2026-09-25/26**

Cette table est conservée comme **post-mortem** : les quatre divergences de nommage ont été supprimées de `.env` et de `.env.example`.

| `.env` écrivait | Code lit | Effet | État |
|---|---|---|---|
| `ODYSSEUS_DURABLE_EXEC` | `ODYSSEUS_DURABLE_EXECUTION` | durable OFF | ✅ corrigé |
| `ODYSSEUS_MEMORY_PROVENANCE` | `ODYSSEUS_PROVENANCE_MEMORY` | provenance OFF | ✅ corrigé |
| `ODYSSEUS_VISUAL_OUTPUT` | `ODYSSEUS_OUTPUT_ROUTER` | routage visuel OFF | ✅ corrigé |
| `ODYSSEUS_THOUGHT_BUS` | *(aucun)* | inerte | ✅ retiré (posé par `launch_fast.py:8`, lu par personne ; l'événement SSE `thought_bus` est inconditionnel) |
| `ODYSSEUS_PROJECT_MANIFEST` | *(aucun)* | inerte | ✅ retiré (0 occurrence) |
| `ODYSSEUS_TOOL_DISCOVERY` | lu, mais `ToolDiscovery` sans appelant | sans effet | ⚠️ **subsiste** — lue (`content_security.py:101`) mais `suggest_connectors`/`get_tool_discovery` ont 0 appelant ; défaut `off`, absent du registre |

---

## 7. Veille — synthèse exploitable

**108 ressources** inventoriées (29 outils, 34 systèmes IA, 12 repos, 33 patterns), **33 features candidates** (10 quick wins, 14 chantiers, 9 long terme). Détail : `../veille/VEILLE-EXTRACTION.md` et `../veille/VEILLE-FEATURES.md`.

**Top 5 idées fortes :**
1. **Boucle d'auto-amélioration fermée** (Génération→Réflexion→Curation + skills auto) — Axe 7, le plus grand écart.
2. **Découverte dynamique d'outils** (`tool_search` + registre MCP + suggestion connecteurs) — §5.13.4.
3. **Catalogue de skills à chargement obligatoire** — quick win fort.
4. **Exécution durable intégrée** — workflows, retry, reprise : **codés et câblés**. **Saga : échafaudage non armé** (`durable_execution.py:200` ; 0 construction ne fournit `compensation=`, et l'action n'est pas exécutée). Approbations longues : à établir.
5. **Observabilité du budget tokens** (CodeBurn → UI + multiplicateur multi-agent) — Axe 6/8.

---

## 8. Comment rendre ce document vivant (traçabilité continue)

1. **CI de modularité** : transformer le script de `03-MODULARITE.md` en job qui échoue si un god node dépasse un seuil (ex. > 40 importateurs) ou si une nouvelle arête `src→routes` apparaît.
2. **Traçabilité par switch** : générer `docs/traceability/killswitches.md` depuis `src/killswitch_registry.py` à chaque PR (source déjà citée). *Le registre expose déjà `wired` et `effective` — la génération est une formalité.*
3. **Statut SFD** : rejouer les checks de `01`/`02` (existences + switches) en CI et publier un verdict à chaque release.
4. ~~Installer les deps + activer pytest en local~~ → **fait le 2026-09-25/26** : 4 792 PASS à cette date, **4 887 PASS** après le Sprint 3 item 8, lint à 3 707 contre une base connue de 3 708.
5. **Backlog de câblage** : le résultat de 10 modules au lieu de le loguer (`02-PRINCIPES-UC.md` §5). C'est le levier qui fera monter l'*Activation* de ~24 % — pas l'activation de nouveaux switchs.

---

*Fin du document maître. Sous-documents : 00→04 (traceability), VEILLE-EXTRACTION/VEILLE-FEATURES (veille).*

<!-- gouvernance:generee -->
| Gouvernance — capacités non classées | **0** (variables lues hors registre et hors configuration) | Justifications de configuration mortes | **0** | Contradictoires (registre ET configuration) | **0** | Lecteurs sans importateur (`called=False`) | **6** | Registre | **65** entrées, **73** variables lues || Gouvernance — capacités non classées | **0** (variables lues hors registre et hors configuration) | Justifications de configuration mortes | **0** | Contradictoires (registre ET configuration) | **0** | Lecteurs sans importateur (`called=False`) | **9** | Registre | **65** entrées, **73** variables lues |