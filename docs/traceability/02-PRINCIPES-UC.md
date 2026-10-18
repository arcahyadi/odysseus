# Traçabilité PRINCIPES & USE CASES → Code réel

*Mesuré le 2026-09-26 (après activation du Palier 0) · branche `feat/inventaire-global-v1`*

Document **vérifiable** reliant les **22 principes SFD v3.1** (P1→P22, `docs/master-ref/01-SFD-v3.1.md` §3) et les **19 cas d'usage** (UC-01→UC-19, §4) au code réellement présent.

> **Méthode.** Analyse statique en lecture seule : `grep` ciblé dans `src/`, `routes/`, `core/`, `archive/`, `services/`, `mcp_servers/`, `.opencode/`, `packages/` ; vérification d'existence des fichiers ; lecture du kill-switch dans `src/killswitch_registry.py` et de sa valeur effective dans `.env` ; comptage des `tests/test_*.py` dont le **nom** matche un mot-clé. Contrôle des routes via `app.openapi()["paths"]` — les routes sont enregistrées par des wrappers paresseux invisibles dans `app.routes`.
>
> **Statuts.**
> - `ACTIF` = présent, sur le chemin d'exécution **par défaut**, sans kill-switch OFF sur ce chemin, et le résultat agit réellement.
> - `PARTIEL` = présent mais non branché au flux live, **ou branché mais inopérant** (résultat seulement loggé, ignoré, ou calcul constant), ou activé mais dont la dépendance externe manque.
> - `DORMANT` = présent mais fermé par défaut.
> - `ABSENT` = non trouvé.
>
> Le point de vérité est le code. (L'ancienne checklist `08-VERIFICATION-ETAT-ACTUEL.md` a été **retirée le 2026-09-25** — périmée ; ce document la remplace.)

> ### ⚠️ Ce que cette révision a changé, et pourquoi c'est une mauvaise et une bonne nouvelle
>
> Ces statuts ont été **re-vérifiés intégralement** après l'activation du Palier 0 (14 kill-switchs basculés de `off` à `on` par défaut dans le code) et après la remise au vert de la suite de tests (4 792 PASS). Les statuts précédents dataient d'une époque où la suite comptait **109 faux échecs** : ils mesuraient un code que rien ne vérifiait.
>
> **Le Palier 0 a fait son travail : plus aucun principe DORMANT (4 → 0).** Les 14 modules câblés le sont pour de vrai, et le cockpit expose enfin leur état.
>
> **Mais l'activation a aussi révélé que « codé » ne veut pas dire « actif »**, et le score a **baissé** là où on l'attendait pas :
> - **ACTIF 12 → 10.** UC-01 perd son statut : sans `OPENCODE_API_KEY` (le projet utilise OpenCode Zen et la clé n'est pas dans `.env`), `model_endpoints` est vide et l'agent n'a aucun endpoint. UC-05 le perd aussi : `on_round_start` **écrase en `BUILD`** la phase posée par l'API avant qu'elle ne soit appliquée. P7 et P11 sont déclassés (structure cosmétique, « complexifier sur preuve » sans mécanisme).
> - **DORMANT 5 → 1.** Les 4 principes DORMANT sont devenus PARTIEL, pas ACTIF : leur switch est `on`, mais le module est appelé avec une entrée vide ou son résultat est seulement loggé. C'est la distinction que l'ancien document ne faisait pas.
>
> Autrement dit : le Palier 0 a démasqué du travail réellement inachevé. C'est le but.

---

## 1. PRINCIPES P1 → P22

| # | Principe | Fichiers (vérifiés) | Kill-switch (défaut) | Tests | Statut | Preuve |
|---|---|---|---|---|---|---|
| **P1** | Le risque modifie la boucle | `src/risk_classifier.py`, `src/orchestrator/gate.py`, `src/tool_execution.py`, `config/phase-lock.yaml` | `DESTRUCTIVE_GATE=on` ; `PHASE_TRACKER=on` (Palier 0) | 7 | **PARTIEL** | `classify_tool` exécuté par outil (`tool_execution.py:573`) ; gate ON (`gate.py:26`) et appelé (`:588-596`) ; phase-lock désormais **vivante** (`phase_tracker.py:25` → poussée `agent_loop.py:2934` → appliquée `tool_execution.py:625-630`). **Mais** l'inférence ne produit que `PLAN`/`BUILD` (`phase_tracker.py:52-54`) et `BUILD` ne bloque rien (`phase-lock.yaml:39`) : le risque ne change ni la phase, ni le modèle, ni l'approbation. Le gate risque→humain de LangGraph (`:802-833`) reste **inatteignable** (`ODYSSEUS_LANGGRAPH` lu `""` puis `off`, absent de `.env`). |
| **P2** | Un brouillon n'est pas un commit | `routes/editor_draft_routes.py`, `archive/legacy/agent_loop.py`, `opencode.json` | — | 2 | **PARTIEL** | Dénylist du mode plan (`agent_loop.py:2241` → `tool_security.py:156-178`) ; plan approuvé épinglé au prompt (`build_active_plan_note`, `:2650-2655`) ; 5 endpoints brouillon **sans** commit/apply (`editor_draft_routes.py:81-165+`) ; écriture mémoire directe (`memory_routes.py:85-118`). |
| **P3** | Contexte construit, pas déversé | `src/context_budget.py`, `src/context_compactor.py`, `src/model_context.py` | — | 8 | **ACTIF** | Budget et trim calculés (`agent_loop.py:2700-2702`), journalisés (`:2704-2710`), **réassignation effective** `messages = trimmed_messages` (`:2711`). *La version précédente citait `:2664-2666` — un `try:` d'import de `context_budget`.* |
| **P4** | Budgets obligatoires par projet | `src/budget_enforcer.py`, `src/project_manifest.py`, `src/governance.py` | — | 5 | **PARTIEL** | `BudgetEnforcer` conditionné au manifeste (`load_manifest(".")` puis `agent_loop.py:2762-2765`, court-circuit `:2873`) et `PROJECT.yaml` **absent** (seul `PROJECT.yaml.example`). Un budget de contexte par défaut s'applique, mais pas de budget *projet* obligatoire. |
| **P5** | Divulgation progressive | `src/progressive_disclosure.py`, `archive/legacy/agent_loop.py` | `PROGRESSIVE_DISCLOSURE=on` (Palier 0) | **28** (`test_progressive_disclosure.py`) + **11** (preuve, partagées avec P21) | **ACTIF** ⬆ | **Sprint 3 item 8 : la restriction retire enfin des outils.** Le bloc M6.8 calculait un `allowed_tools` et ne le **journalisait** que — `get_allowed_tools` n'avait **aucun appelant** dans la boucle. Le corriger là n'aurait rien changé : M6.8 tourne à `:4625-4652`, les schémas partent à `:3210`. Le filtre agit désormais **là où la liste est construite**, après `disabled_tools` et sur tous les chemins de sélection (`agent_loop.py:3158-3169`), via `filter_schemas` (`progressive_disclosure.py:146-182`). Preuve de fin du plan : **le modèle ne reçoit plus les outils hors de sa phase** (`tests/test_sprint3_p5_p21_disclosure_restricts.py`, 11 tests, **4 mutations**), avec la contre-épreuve `test_the_common_path_loses_nothing` (`BUILD` = niveau `full` ⇒ retrait **nul**). **La règle est bornée, délibérément** : `_TOOL_CATEGORY_MAP` ne connaît que **37 des 68** schémas natifs, donc un filtrage strict par allowlist aurait supprimé **31 outils dans toutes les phases, `BUILD` comprise** — `web_search`, `ask_user`, toute la surface e-mail. Un outil inconnu de la carte est *inconnu ici*, pas interdit. La mutation M2, qui supprime cette borne, est attrapée par les deux tests écrits pour elle. **Une seule lecture du switch** (`progressive_disclosure_enabled`, `progressive_disclosure.py:26-28`), appelante réelle désormais ; l'inline dupliqué de M6.8 est supprimé. **Défaut constaté, signalé, non corrigé** : `agent_loop.py:3040` avance la boucle canonique **avant** de résoudre la phase (`:3049`), donc le round 1 est `KNOW` et `CANONICAL_SEQUENCE[0]` (`CLASSIFY`) n'est **jamais atteinte** — donnée présente, jamais atteinte, même famille que §4.6 ; `test_the_first_sequence_phase_is_dead` le rend visible. |
| **P6** | Échecs répétés → fonctionnalités du harnais | `src/orchestrator/autoeval.py`, `autoevolve.py`, `codeburn_runner.py`, `src/observer.py` | `AUTOEVAL=on`, `AUTOEVOLVE=on`, `CHECKPOINT=on` (Palier 0) ; `CODEBURN=off` ; `AUTOEVAL_ALLOW_RESET=off` | 5 | **PARTIEL** | Observer/dérive réel par run (`agent_loop.py:4154-4164`) ; décision AUTOEVAL tracée en live (`apply_autoeval`, `:4201-4204`) ; CHECKPOINT appelé (`record_checkpoint`, `:4121-4126`). **Mais** la recherche autoevolve n'est **jamais réinjectée** dans la boucle (donc aucune règle auto-apprise) ; `CODEBURN=off` ; et surtout l'**action** est *branchée mais armée par le Chef, pas dormante* : la boucle injecte un vrai `git_runner` (`agent_loop.py:4325`, passé à `apply_autoeval` en `:4349`), et `apply_autoeval` n'invoque le revert que si la décision est `revert` **et** `destructive_revert_allowed()` (`autoeval.py:108-140`). Ce switch est `AUTOEVAL_ALLOW_RESET=off` par défaut — donc l'action est **présente, câblée, et volontairement désarmée**, ce qui n'est pas la même chose que « jamais exécutée ». *La version précédente de cette ligne disait « jamais exécutée » : c'était inexact, le `git_runner` était déjà injecté.* |
| **P7** | Structure > autonomie | `src/opencode_engine.py`, `src/orchestrator/phases.py` | `LIVE_ORCHESTRATION=off` (CanonicalLoop Python) | 3 | **PARTIEL** ⬇ | `walk()` est bien appelé par défaut (`chat_routes.py:1413` → `opencode_engine.py:251-325`). **Mais seule `BUILD` streame l'agent** (`:291-318`) ; les 6 autres n'émettent qu'une chaîne SSE `phase_active` (`:319-322`). `PHASE_TOOLS`/`PHASE_AGENTS`/`PHASE_MODELS` (`:104-240`) ne contraignent **jamais** `agent_stream_fn()`. La structure est cosmétique. |
| **P8** | Le plan passe les mêmes portes | `src/planning_engine.py`, `archive/legacy/agent_loop.py`, `routes/phase_routes.py` | `PLANNING_ENGINE=off` (code) | 2 | **PARTIEL** | Mode plan réel (`agent_loop.py:2252`), `PLAN` bloque `bash` (`phase-lock.yaml:32-33`). **Mais** le moteur de planification structuré est `off` (`planning_engine.py:27`), absent du registre et du `.env` ; `approved_plan` n'est qu'une note de prompt injectée en message system (`:2650-2655`). |
| **P9** | Évaluer le harnais, pas le modèle | `src/observer.py`, `src/trace_writer.py`, `src/sse_indicators.py` | `LANGFUSE=off` (sous-partie) | 3 | **ACTIF** | Drift par run (`agent_loop.py:4151-4154`) ; `run_status` émis à chaque tour (`:2982`) et en fin de run (`:4161`) ; `/api/observer/drift` (`observer_routes.py:17-18`) ; trace écrite pour **chaque** appel outil (`tool_execution.py:665-683`). `perf_profiler.py` n'a toujours aucun appelant ; `LANGFUSE` reste `off`. |
| **P10** | Humain ON the loop | `src/tool_index.py`, `archive/legacy/agent_loop.py`, `routes/chat_routes.py` | — | 2 | **ACTIF** | `ask_user` toujours disponible (`tool_index.py:42`, implémentation `agent_loop.py:3778-3980`) ; Stop/Resume du run (`chat_routes.py:1466`/`:1455`). **Réserve** : aucun gate humain n'est lié au risque — `ask_user` part à l'initiative du modèle. |
| **P11** | Commencer simple, complexifier sur preuve | `archive/legacy/agent_loop.py`, `src/orchestrator/agent_dispatcher.py` | 12 `AGENT_*=off`, `LIVE_ORCHESTRATION=off` | 4 | **PARTIEL** ⬇ | La moitié « simple » est réelle : agent unique par défaut, `agents_for_phase` → `[]` (`agent_dispatcher.py:118-121`). La moitié « sur preuve » est **absente du chemin d'exécution** : `get_decision_engine()` (`src/decision_engine.py:749`) a 0 appelant, et `MultiAgentWorkflow` exige `LIVE_ORCHESTRATION=on` (OFF). |
| **P12** | Découpage par contexte, pas par métier | `src/orchestrator/agent_dispatcher.py`, `multi_agent.py`, `phases.py` | 13 switches agents `off` | 9 | **PARTIEL** | `dispatch_for_phase` (`agent_dispatcher.py:123`) a **0 appelant en production** ; seul `dispatch_explicit` est utilisé (`core/route_loader.py:45-50`). |
| **P13** | Contexte = budget d'attention | `src/context_compactor.py`, `src/provenance_memory.py` | `PROVENANCE_MEMORY=on` (Palier 0) | 8 | **ACTIF** ⬆ | Compaction **appliquée** (`messages = trimmed_messages`, `agent_loop.py:2711`). Mémoire incrémentale vivante (`agent_loop.py:4294` → `provenance_memory.py:366-381`) ; preuve empirique : `data/memory-fs/profile.md`. **Réserve** : seule la branche `[stated]` est vive (cf. P16). |
| **P14** | Survivre à une panne | `src/durable_execution.py`, `src/orchestrator/checkpoint_tracker.py` | `DURABLE_EXECUTION=on`, `CHECKPOINT=on` (Palier 0) | 13 | **PARTIEL** ⬆ | La reprise est **câblée et effective** : `begin_run` (`durable_execution.py:349`) ouvre ou reprend le run **avant** la boucle de rounds (`agent_loop.py:3058`), `record_progress` (`:4214`) persiste la conversation dès qu'elle grandit, et `finish_run` (`:4252`) clôt en fin de run — volontairement **hors** d'un `finally`, sans quoi une déconnexion clôrait le run et le rendrait non reprenable. **Trois défauts distincts** ont dû être corrigés, pas un : (1) `create_workflow` n'avait aucun appelant ; (2) le bloc M6.3 appelait `resume()` **après** la boucle, donc ne pouvait rien restaurer ; (3) `resume()` charge par **id de workflow** (`<uuid>.json`) alors qu'on lui passait un id de session — `path.exists()` était donc toujours `False`. `resume_session` (`:257`) ferme le troisième. **Reste** : le checkpoint Obsidian échoue car `_ensure_vault()` ne trouve pas `/obsidian-vault` (`obsidian_mcp.py:12-18`) et `checkpoint_tracker.py:120` saute l'écriture ; l'état est ancré sur un répertoire local, donc la reprise ne franchit pas une frontière de machine. |
| **P15** | On n'observe pas ce qu'on ne trace pas | `src/trace_writer.py`, `src/event_bus.py`, `src/opencode_engine.py` | `UNIFIED_TOKENS=on` (Palier 0) | 8 | **ACTIF** | `UNIFIED_TOKENS` défaut `"on"` et `wired=True` ; publication effective (`agent_loop.py:4050-4057`, `run_id` posé à `:4045`) ; **réconciliation** réelle (`routes/chat_helpers.py:783-785`). |
| **P16** | Provenance explicite | `src/provenance_memory.py`, `src/memory_writer.py` | `PROVENANCE_MEMORY=on` (Palier 0) | 9 | **PARTIEL** ⬆ | `update_profile` (`agent_loop.py:4410` → `provenance_memory.py:366`) écrit réellement des entrées `[stated]` — **conditionné** au verdict P19 (`:4401`). **Sprint 3 item 6 : `[observed]` n'avait aucun producteur vivant.** `add_observed` refuse d'écrire si le fichier de domaine n'existe pas (`provenance_memory.py:344-346`) — un contrat **délibéré et testé** (`test_add_observed_requires_existing_file`) — mais rien ne créait `topics/agent-output.md`, donc l'appel live était un **no-op garanti** dont le `False` était jeté. Le domaine est amorcé une fois (`agent_loop.py:4390-4391`) ; l'absence de fichier est un problème de **démarrage**, pas une garantie de provenance. **Le log mentait** : `« provenance memory updated »` sortait inconditionnellement (`:4420`), y compris quand les deux écritures avaient été refusées — c'est ce qui a laissé un no-op garanti rester invisible. Il annonce désormais **ce qui a atterri** (`_m62_written`, `:4408-4427`), avec un test qui compare le log au disque. Preuve de fin du plan : **`[observed]` et `[inferred]` atterrissent dans `data/memory-fs/`** (`tests/test_sprint3_p16_provenance_writes.py`, 9 tests, 2 mutations vérifiées). **Ce qui reste** : `memory_writer.py` a toujours 0 appelant. **Vérifié, pas un défaut** : l'amorce ne s'accumule pas — `memory_append` est idempotent (« Déjà présent, pas d'erreur », `provenance_memory.py:248-250`) ; un test verrouille la propriété. |
| **P17** | Ne jamais stocker le sensible | `src/data_classification.py`, `src/content_security.py`, `routes/memory_routes.py` | `DATA_CLASSIFICATION=on`, `CONTENT_SECURITY=on` (Palier 0) | 14 | **PARTIEL** ⬆ | **Sprint 3 item 1 : la porte PROTECTED bloque réellement.** Classification remontée avant l'écriture (`agent_loop.py:4315`), gate l'écriture durable de M6.2 (`:4767`), blocage visible (`memory_blocked`). **Sprint 3 item 11 : l'émission est bloquée, plus seulement annoncée.** Un seul « verdict d'émission » (`:4279`) calcule classification (`:4315`) ET sécurité des contenus (`:4317`) **avant le premier consommateur**, et `:4351` en tire `_emission_refusee` / `_texte_diffusable` (`:4354`) — cinq consommateurs en dépendent : diffusion canal (`:4393`), accroche enseignant (`:4650`), vérificateur d'impact (`:4713`), écriture M6.2 (`:4767`), routeur de sortie (`:4849`). Le refus est **annoncé** sur le flux (`content_blocked`, `:4344`). **Trois trouvailles de mesure, toutes dans le reliquat** : (a) M6.6 était le *dernier* à voir le texte — il journalisait « output blocked » alors que la sortie était déjà partie ; (b) la porte PROTECTED de l'item 1 était posée **après** la diffusion canal, donc la seule émission vers des tiers n'était pas couverte ; (c) `sanitize_memory` n'avait **aucun appelant** — `MEMORY_INJECTION_PATTERNS` (`:41`) ne protégeait rien. Appliqué au seul point de passage de toute écriture mémoire (`provenance_memory.py:308`), et **les motifs sont trop étroits** : mesuré, `ignore (all |your |previous )?(instructions|…)` détectait « ignore all instructions » et manquait « ignore all previous instructions », la forme canonique — un qualificatif optionnel **unique** là où l'anglais en empile trois. **Limite, dite** : les octets déjà diffusés en streaming ne se reprennent pas ; ce qui est contenu, c'est toute propagation en aval, toute écriture durable, et un refus annoncé. 24 tests, 12 mutations. |
| **P18** | Lire avant d'écrire | `src/provenance_memory.py`, `src/hash_edit_validator.py` | `PROVENANCE_MEMORY=on` (Palier 0) | 1 | **PARTIEL** | `if_version` réel avec rejet (`provenance_memory.py:273`), désormais **atomique** : verrou reentrant par chemin résolu (`:238`) tenu sur tout le compare-and-swap (`append_cas:491`), et écriture par fichier temporaire puis `os.replace` (`:316`) — donc jamais de version à moitié écrite. **La fiche précédente disait faux sur le lieu, et vrai sur le fond.** Elle attribuait la tautologie à `:237` → `:253` ; mesuré, `memory_write` relit le disque avant de comparer, donc un jeton venant d'un appel antérieur était déjà rejeté. Le vrai défaut était ailleurs : les quatre aides relisaient et écrivaient dans le même corps, donc le jeton ne sortait jamais de l'appel et la branche de rejet n'avait **aucune route de production**. Elle ne mentionnait pas non plus la perte silencieuse : barrière placée entre la vérification et l'écriture, les **deux** passent et **les deux** écrivent — un fait disparaît sans bruit, le jeton ne
  protégeant que le cas fortuit où la collision tombe entre lecture et relecture. Le jeton circule maintenant d'un tour à l'autre (`agent_loop.py:72`, `:4701`) et le refus est **rapporté** sur le flux (`memory_conflict`, `:4713`, les deux jetons via `ConflitMemoire:201`) puis réessayé — un fait perdu n'est pas une écriture rejetée. `hash_edit_validator.py` reste sans appelant fonctionnel : inchangé, et dit comme tel. 6 tests, 9 mutations. |
| **P19** | La mémoire s'applique seulement si elle change la réponse | `src/memory_impact.py` | `MEMORY_IMPACT=on` (Palier 0) | 13 | **PARTIEL** ⬆ | **Sprint 3 item 4 : le verdict décide, il ne raconte plus.** `hypothetical_response=""` court-circuitait `evaluate_impact` à `0.0` ⇒ `should_store` **toujours** `False`. Le comparatif est maintenant construit — « et sans ce fait ? » par ablation des phrases dominées par le fait (`build_hypothetical_response`, `memory_impact.py:156-198`) — et le verdict est **remonté avant l'écriture** qu'il doit gouverner (`agent_loop.py:4350-4370`), puis **gate `update_profile`** (`:4390-4392`) : un fait que la réponse n'a pas servi n'est plus retenu. Le verdict est publié sur le flux (`memory_impact`, `:4541`) et écrit dans le store de provenance taggé (`:4526`). Preuve de fin du plan : **`score > 0` sur un tour réel** (`tests/test_sprint3_p19_memory_impact.py`, 13 tests, 2 mutations vérifiées), avec la contre-épreuve « le fait ignoré par la réponse ⇒ `score == 0`, rien n'est écrit ». **Deux défauts corrigés au passage** : (a) une réponse entièrement dominée par le fait renvoyait l'original en repli, donc **zéro impact au moment où l'impact est maximal** — remplacée par un sentinelle explicite (`:41`) ; (b) une réponse trop courte pour être comparée renvoyait `0.0`, indiscernable d'un zéro **mesuré** : `_is_measurable` (`:142`) distingue les deux et le fait est **gardé par défaut** plutôt que jeté sur une conjecture. **Croisement P17** : le store d'impact respecte aussi le verdict de classification — « impactant » n'est pas une dérogation de rétention (`:4524`), avec un test de régression dédié. |
| **P20** | Les préférences se résolvent par priorité décroissante | `src/preferences.py`, `routes/prefs_routes.py` | `PREFERENCES=on` (Palier 0) | 11 | **PARTIEL** ⬆ | **Sprint 3 item 2 : la résolution atteint enfin le modèle.** `build_prompt_directive()` (`preferences.py:231-256`) traduit la résolution 5-niveaux en directive, injectée **en tête du system prompt** (`agent_loop.py:2645-2652`, à côté de `PLAN_MODE_DIRECTIVE`) ; le bloc M6.1 de fin de boucle ne fait plus que ** rapporter** ce qui a été injecté (`:4323-4341`). La preuve est comportementale, pas un log : le **stub LLM répond en français** quand la préférence est `fr`, et en anglais quand elle est `english` (`tests/test_sprint3_p20_preferences_prompt.py`, 11 tests, vérifiés par mutation). **Trou de sécurité corrigé au passage** : le guardrail `ignore (all \|your )?rules` ne filtrait pas « ignore **all your** rules » — et ces préférences étant désormais injectées au prompt, un guardrail troué est une **prompt injection stockée**. Motif durci (`preferences.py:63-67`) et implémentation unique partagée à l'entrée et à la sortie (`passes_behavioral_guardrails`, `:75-86`). **Réserves** : la directive ne couvre que `language`/`tone`/`format`/`length` — les autres préférences ne sont pas traduisibles en prompt ; `data/preferences.json` n'existe toujours pas par défaut ; l'API live reste un **autre** store, sans priorité contextuelle. |
| **P21** | Le bon outil au bon moment, sans friction | `src/tool_index.py`, `src/content_security.py`, `routes/mcp_routes.py` | `TOOL_DISCOVERY=off` (code), absent du registre | 19 + **11** (preuve, partagées avec P5) | **PARTIEL** ⬆ | **Sprint 3 item 8 : la surface d'outils est restreinte par la phase** — voir la preuve P5. `get_allowed_tools` a désormais un **appelant en production** (`agent_loop.py:3161`), et la restriction se lit sur les schémas **réellement envoyés** au modèle, pas sur un calcul jeté (mutation M4 : calculer sans affecter le résultat fait échouer les 6 tests de la preuve). **Index d'outils statique vivant** (`agent_loop.py:1646`) ; gestion MCP manuelle (`mcp_routes.py`, 11 endpoints). **Ce qui reste mort** : `ToolDiscovery` / `suggest_connectors` ont **0 appelant dans tout le dépôt** ; `@agentos/sfd-discovery` absent de `opencode.json` ; `TOOL_DISCOVERY` toujours `off` et absent du registre. **Constat hors périmètre, signalé** : `blocked_tools_for_owner` (`tool_security.py:226`) renvoie les **mêmes 38 outils** pour `None`, pour un utilisateur et pour `"admin"` — la fonction dépend du rôle, pas de l'owner, malgré son nom. Mesuré avant de câbler, car il retire 38 outils **avant** la divulgation : les jeux de la preuve sont choisis parmi les 33 survivants, et `_assert_sets_are_reachable` échoue si l'un d'eux passe dans le lot bloqué. |
| **P22** | La sortie visuelle est une modalité de premier rang | `src/output_router.py`, `routes/mcp_tools_routes.py`, `src/visual_report.py` | `OUTPUT_ROUTER=on` (Palier 0) | 10 | **PARTIEL** ⬆ | **Sprint 3 item 3 : `OutputDecision` a un effet de bord.** `route()` **reste pur** (décider ≠ écrire : le premier se teste sans disque) et le nouvel `apply()` (`output_router.py:210-250`) exécute la décision ; la boucle l'appelle (`agent_loop.py:4398`) et **annonce le fichier produit** sur le flux (`output_routed`, `:4407`). Preuve de fin du plan : **une demande de diagramme écrit un fichier** contenant la source (`tests/test_sprint3_p22_output_side_effect.py`, 10 tests, vérifiés par mutation). `apply()` n'écrit jamais par-dessus un fichier existant sans le dire (`_unique_path`, `:260`) et **ne fait rien** pour `TEXT_ONLY` / `MCP_TOOL` (l'invocation MCP appartient à l'appelant). **Réserves** : `connected_mcp_tools` n'est **jamais peuplé** ⇒ la branche `MCP_TOOL` (`output_router.py:181-185`) reste du code mort, et `apply()` ne l'exerce donc pas ; Kroki reste le seul chemin visuel **affiché** — le fichier écrit n'est pas encore rendu dans l'UI. |

> ⬆ = promu · ⬇ = rétrogradé par rapport à la mesure du 2026-09-25.

---

## 2. USE CASES UC-01 → UC-19

| ID | Cas d'usage | Statut | Preuve |
|---|---|---|---|
| **UC-01** | Lancer un nouveau projet | **PARTIEL** ⬇ | Le mode est détecté par mots-clés, pas par défaut agent (`opencode_engine.py:259`) ; `model_endpoints` est **vide** et `OPENCODE_API_KEY` est absent de `.env` ⇒ `agent_loop.py:2118` n'a aucun endpoint. Le flux nominal est donc inatteignable en l'état. |
| **UC-02** | Interrompre / modifier un projet | **PARTIEL** | Stop/Resume d'un run détaché opérationnels (`chat_routes.py:1455-1470`). La reprise d'un run interrompu est désormais **réellement branchée** : `begin_run` (`agent_loop.py:3058`) restaure la conversation et le round atteint, et l'événement `run_resumed` (`:3065`) l'annonce dans le flux. *Historique : cette ligne disait « `resume()` est appelé puis seulement loggé » — le bloc était bien atteint, mais après la boucle et avec le mauvais identifiant, donc il ne pouvait rien restaurer.* **Reste** : « modifier un projet » n'est pas couvert — la reprise se fait au dernier round enregistré, pas à un round choisi par l'utilisateur, et un run en cours n'est pas éditable. |
| **UC-03** | Consulter l'état d'avancement | **ACTIF** | `/api/observer/drift` (`observer_routes.py:17`) et `/current/{session_id}` (`phase_routes.py:38`) ; vérifié en exécution : HTTP 200 `{"ok":true,"drift_level":"low"}`. |
| **UC-04** | Ajouter un nouvel outil (MCP) | **ACTIF** | `POST /api/mcp/servers` persiste en base (`mcp_routes.py:163`) ; route enregistrée au boot (`core/route_loader.py:30`). La *découverte dynamique* reste partielle (cf. UC-15). |
| **UC-05** | Modifier le workflow d'un projet | **PARTIEL** ⬆ | `POST /api/phase/set` (`phase_routes.py:27`) + `config/phase-lock.yaml` existent. **Sprint 3 item 5 : le verrou tenait jusqu'au round suivant, puis disparaissait sans trace.** Ce n'était pas cosmétique — `RESEARCH` bloque `write_file`, `edit_file` et `bash` (`config/phase-lock.yaml:9-12`), gate réel lu par `is_tool_allowed` (`tool_registry.py:154-159`) et appliqué à l'exécution (`tool_execution.py:625`). Mais `on_round_start` réécrivait la phase **inconditionnellement** à chaque round (`agent_loop.py:2956`), et le tracker est `on` par défaut : un module activé désarmait silencieusement un contrôle de gouvernance. **Le tracker ne peut plus que resserrer** (`phase_tracker.py:85-121`) : il n'écrit que si le registre ne porte aucune phase pour la session, ou si la phase présente est celle qu'il a lui-même écrite (`_foreign_phase`, `:63-83` + `_TRACKER_LAST_WRITE`, `:33`). Preuve de fin du plan : **`RESEARCH` posé par l'API survit au round start, `bash` reste bloqué** (`tests/test_sprint3_uc05_phase_lock_holds.py`, 8 tests, 2 mutations vérifiées), avec contre-épreuve « une phase que le tracker a lui-même posée, il peut la refaire » — sinon `plan_mode` produirait un verrou **collé pour toujours** sur les streams suivants, puisque `PhaseTracker` est reconstruit à chaque stream (`:2845`) alors que le registre survit. **Ce qui reste** : `resolve_current_phase` (`phase_resolver.py:37-38`) appelle `infer_phase` et **ne lit pas le registre** — le verrou d'outils tient, mais le *dispatch* d'agents (M4) suit toujours BUILD/PLAN et ignore une phase posée par l'API. |
| **UC-06** | Forker un projet (worktree) | **ABSENT** | 0 occurrence de `git worktree`. `opencode_engine.py:188` : `worktree=` n'est qu'un `cwd` de travail. Confirmé par l'audit interne `tools/sfd_audit.py:286`. |
| **UC-07** | Fusionner un worktree | **ABSENT** | 0 appel git `merge`/`worktree` dans `src/`, `routes/`, `core/`, `services/`, `archive/`. `tools/sfd_audit.py:287` : « Non implémenté ». |
| **UC-08** | Consulter la mémoire transversale | **ACTIF** | 14 endpoints sur SQLite (`memory_routes.py:132/138/156/531`) ; ChromaDB dégradé **sans impact** (vérifié en exécution : `GET /api/memory` → 200). |
| **UC-09** | Recevoir une alerte | **ACTIF** | Une dérive `MEDIUM`/`HIGH` déclenche maintenant une alerte ayant trois propriétés qu'un statut n'a pas : **indiscutable** (un événement SSE `drift_alert`, distinct de `run_status`, `agent_loop.py:4530`), **durable** (écrite sur la piste d'audit par `write_alert`, `src/trace_writer.py:228`, puis relisible après coup par un administrateur via `GET /api/audit/traces?kind=alert`), et **actionnable** (elle porte `Observer.get_summary()` — cause, recommandation, runs au-dessus du seuil — pas seulement un niveau). Table de gravité `agent_loop.py:85`, seuil `:4524`. **Avant** : un `logger.warning` unique, alors que le niveau atteignait déjà le client — mais dans `run_status`, donc comme un statut parmi d'autres, dans un flux que personne n'est obligé de regarder, et perdu dès la déconnexion du client (le cas nominal, mesuré à l'item 9). `MEDIUM` alerte aussi, parce que `DriftLevel` le documente lui-même comme alerte : n'alerter que sur `HIGH` laisserait la gradation non exprimée. Push externe (Apprise) reste `off` (`apprise_service.py:37`) — inchangé. **Non fait, délibérément** : agir sur l'alerte. Un re-boucle automatique dépense des jetons sans borne ni condition d'arrêt — c'est une décision produit, dite ici et non glissée dans le code. 6 tests, 10 mutations. |
| **UC-10** | Escalader vers une architecture multi-agent | **DORMANT** ⬇ | L'endpoint lève `ValueError` car les 12 switches agents sont `off` (`agent_dispatcher.py:201-204`), puis `RuntimeError` car `AGENT_CATALOG` est `off` (`:206-208`). Le dispatch explicite existe mais **fermé par défaut**. |
| **UC-11** | Reprendre après panne | **PARTIEL** ⬆ | Un run interrompu puis relancé **reprend** : la conversation persistée est restaurée (`agent_loop.py:3058`) et l'événement `run_resumed` (`:3065`) l'annonce dans le flux. Preuve de fin : après une interruption en plein flux, le run relancé envoie au modèle une conversation **plus avancée** que la première, au lieu de repartir de zéro. **Garde anti-écrasement** : la reprise n'a lieu que si la conversation entrante est un préfixe de celle persistée (`is_continuation`, `durable_execution.py:394`) ; sinon l'ancien run est clôturé `FAILED` et un neuf est ouvert (`restart_run`, `:413`) — sans ce garde, une **nouvelle question** posée sur la même session serait remplacée en silence par l'ancienne conversation. **Reste** : l'état vit dans un répertoire local (`durable_execution.py:44`), donc la reprise ne franchit pas une frontière de machine ; la rétention garde un run par session, sans historique. |
| **UC-12** | Auditer une décision passée | **ACTIF** | `GET /api/audit/traces` (`routes/audit_routes.py:41`, `require_admin` `:56`) rend ce que la boucle a décidé : `read_traces` (`src/trace_writer.py:228`) relit la piste, bornée à `MAX_READ_LIMIT` `:40`. **Deux trous, pas un** : avant, `trace_writer.py` n'avait aucune fonction de lecture, et la décision AUTOEVAL n'était écrite **nulle part** — seulement journalisée puis diffusée en SSE, donc perdue pour tout client déconnecté. `write_decision` (`src/trace_writer.py:172`) est appelé par la boucle (`archive/legacy/agent_loop.py:4511`). Garde P17 : la classification est **remontée** au-dessus de cette écriture (`agent_loop.py:4412`), sinon les motifs du vérificateur — texte dérivé de la demande — atterrivaient sur disque avant que le contenu soit jugé ; la trace porte alors `reasons_omitted: "protected"`. Une ligne tronquée (crash pendant l'écriture) est **comptée**, jamais sautée en silence. 14 tests, 16 mutations, dont 3 sans test initialement (`read_traces` sans borne, filtre `kind` inopérant, lecteur qui créait son propre dossier). |
| **UC-13** | Retrouver une conversation passée | **ACTIF** | `GET /api/search` → `search_session_messages` (`chat_routes.py:1508-1520`, `session_search.py:301`, FTS5 avec repli `LIKE`) + outil agent. |
| **UC-14** | Définir une préférence persistante | **ACTIF** ⬆ | `GET /api/prefs` / `PUT /api/prefs/{key}` (`prefs_routes.py:79`/`:85`) avec écriture atomique (`os.replace`, `:30`) et scoping utilisateur (`:33-43`). |
| **UC-15** | Découvrir et connecter un nouveau service | **PARTIEL** | Découverte locale de modèles active (`model_routes.py:1743`), **mais** `suggest_connectors` (`content_security.py:245`) a 0 appelant. |
| **UC-16** | Obtenir une visualisation d'un concept | **PARTIEL** | La route existe (`mcp_tools_routes.py:24`) **mais Kroki est injoignable** (`curl` → code 000) et `KROKI_ENABLED=off` (`.env:371`). Le rapport visuel de recherche reste le seul chemin vivant. |
| **UC-17** | Exporter un artefact visuel | **PARTIEL** | `OUTPUT_ROUTER=on` et la décision est **appliquée** : `output_router.apply()` est appelé sur la réponse finale (`agent_loop.py:4584`) et le chemin écrit est publié en SSE (`output_routed`, `:4593`). *La version précédente de cette ligne affirmait « `FILE_DOWNLOAD` n'est jamais appliqué » en citant `agent_loop.py:4330-4339` — c'était faux, l'item 3 (P22) l'avait livré, et la citation était décalée d'environ 250 lignes.* Le résiduel réel n'est plus la décision : c'est l'**offre** — le fichier écrit n'est pas rendu comme téléchargement dans l'UI, donc seul le chemin Kroki est visible de l'utilisateur. |
| **UC-18** | Gérer ses préférences | **PARTIEL** | `GET /api/prefs`, `GET /api/prefs/{key}`, `PUT /api/prefs/{key}` existent (`prefs_routes.py:74/79/85`) ; **aucun** `@router.delete` dans le fichier (confirmé via `openapi()["paths"]`). |
| **UC-19** | Consulter et gérer ses données (droit à l'oubli) | **PARTIEL** | La vraie route d'export est `GET /api/export` (`backup_routes.py:19-62`, `require_admin`) — vérifiée en exécution, 200, ~4,9 Ko. `admin_wipe_routes.py:76` : wipe global **admin-only**, pas d'auto-purge utilisateur. ⚠️ Les routes `POST /api/backup/export` (`:206`) et `/import` (`:211`) sont des **stubs** (`{"ok":true,"export":null}`) et ne doivent pas servir de preuve. |

> ⬆ = promu · ⬇ = rétrogradé par rapport à la mesure du 2026-09-25.

---

## 3. Résumé chiffré

### Principes P1 → P22

| Statut | Nombre | IDs |
|---|---|---|
| **ACTIF** | **6** | P3, P5, P9, P10, P13, P15 |
| **PARTIEL** | **16** | P1, P2, P4, P6, P7, P8, P11, P12, P14, P16, P17, P18, P19, P20, P21, P22 |
| **DORMANT** | **0** | — |
| **ABSENT** | **0** | — |
| **Total** | **22** | |

### Use cases UC-01 → UC-19

| Statut | Nombre | IDs |
|---|---|---|
| **ACTIF** | **7** | UC-03, UC-04, UC-08, UC-09, UC-12, UC-13, UC-14 |
| **PARTIEL** | **9** | UC-01, UC-02, UC-05, UC-11, UC-15, UC-16, UC-17, UC-18, UC-19 |
| **DORMANT** | **1** | UC-10 |
| **ABSENT** | **2** | UC-06, UC-07 |
| **Total** | **19** | |

### Items de la vision **sans fiche** — INT

`../VISION-INTEGRATION.md` promet 21 intégrations (INT-1 → INT-21) et 11 chantiers
de modularité (MOD-1 → MOD-11). La grille ci-dessus en suit 22 principes et 19 cas
d'usage. **Sept items de la vision n'avaient aucune ligne qui les suive** : la
grille a été dérivée du SFD, pas de la vision intégrée.

C'est le trou qui a permis à `core.database` de passer de 64 à 120 importeurs sans
qu'une porte le voie : une promesse que rien ne mesure n'est pas une promesse, et
une vision que la traçabilité ne suit pas ne se contrôle pas, elle se raconte.

Inscrits ici, en `NON SUIVI`, pour que le vide soit compté. Aucun n'est résolu par
cette ligne : les inscrire est un **pré-requis de mesure**, pas un chantier.

| ID | Apport (vision) | Fiche qui le suit | État mesuré au `0e4d4f9` |
|---|---|---|---|
| **INT-4** | Routage modèle live, modèle par phase/agent, bandeau modèle | *aucune* | `ModelEndpoint` et `model-routing.json` existent (383 occurrences) mais la source de vérité est dupliquée — voir MOD-3. |
| **INT-6** | Skills à chargement obligatoire + catalogue | *aucune* | `routes/skills_routes.py` existe ; **aucun gate** de chargement obligatoire. |
| **INT-7** | Découverte dynamique d'outils (`tool_search`) | *aucune* | `tool_search` : **0 occurrence**. L'interrupteur `ODYSSEUS_TOOL_DISCOVERY` est désormais inscrit (item 2 du Sprint 4) et vaut `off`. |
| **INT-10** | Grounding + citations dans les livrables | *aucune* | **Absent.** `tools/check_citations.py` vérifie la **documentation** du dépôt — ne pas le confondre (item 6 du Sprint 4). |
| **INT-11** | Heartbeat / cron / briefs en langage naturel | *aucune* | Un ordonnanceur existe (`src/task_scheduler.py`) ; le « en langage naturel » n'est pas mesuré. |
| **INT-12** | Wide Research (recherches parallèles bornées) | *aucune* | **0 occurrence.** Rien à mesurer, rien à corriger. |
| **INT-15** | `AGENTS.md` généré par projet | *aucune* | **0 occurrence.** |

| Statut | Nombre | IDs |
|---|---:|---|
| **NON SUIVI** | **7** | INT-4, INT-6, INT-7, INT-10, INT-11, INT-12, INT-15 |

### Bilan

| | Avant (2026-09-25) | Après (Palier 0) | Δ |
|---|---:|---:|---:|
| ACTIF | 12 | **10** | −2 |
| PARTIEL | 22 | **28** | +6 |
| DORMANT | 5 | **1** | −4 |
| ABSENT | 2 | **2** | = |
| **Total** | 41 | **41** | |

Les 4 principes DORMANT ont migré vers PARTIEL : leur switch est `on`, mais le module est soit appelé avec une entrée vide, soit branché sur un `logger.info`. **C'est la seule interprétation honnête** : « le switch est activé » n'a jamais voulu dire « le module agit ».

Les 2 ACTIF perdus ne sont pas des régressions du code : ce sont des dépendances et des câblages que la mesure précédente ne pouvait pas voir. **UC-01** attend une clé d'API absente. **UC-05** est écrasé par la phase-lock. Les corriger est du travail, pas de la documentation.

> **Suite Sprint 3 (postérieur au tableau ci-dessus, qui reste le bilan du Palier 0).** Sur ces deux pertes : **UC-05 est corrigé** (item 5) — un module activé par défaut réécrivait la phase du registre à chaque round et désarmait `RESEARCH`, qui bloque `bash`/`write_file`/`edit_file`. **UC-01 reste ouvert** et n'est pas un problème de code : il attend `OPENCODE_API_KEY`. Les comptes ACTIF/PARTIEL ci-dessus sont donc ceux du Palier 0 ; UC-05 est passé de PARTIEL à PARTIEL **plus complet** depuis, et le reliquat est nommé dans sa ligne.
>
> **Promotions Sprint 3, postérieures au bilan ci-dessus** (le tableau « Bilan » reste donc une photo du Palier 0 ; ci-dessous l'état atteint ensuite) :
>
> | Item | Promu | De → Vers | Preuve |
> |---|---|---|---|
> | 5 | UC-05 | PARTIEL → **PARTIEL plus complet** | le verrou de phase tient d'un tour à l'autre |
> | 8 | **P5** | PARTIEL → **ACTIF** | le modèle ne reçoit plus les outils hors de sa phase (11 tests, 4 mutations) |
>
> **Conséquence mesurée sur le décompte** : P5 promu, les deux tables de la section 3 passent à **ACTIF 6 / PARTIEL 16** (principes) et **ACTIF 5 / PARTIEL 11** (use cases, inchangés). Ces tables sont **dérivées des lignes de la section 1**, jamais recopiées à la main. P16, P17, P19, P20, P22 restent PARTIEL : leurs principes sont câblés, mais chacun garde un reliquat nommé dans sa ligne — les garder PARTIEL est l' lecture honnête, pas un oubli de mise à jour.

---

## 4. Écarts de configuration (section réécue le 2026-09-26)

### 4.1 Kill-switchs enregistrés **sans aucun lecteur dans le code**

Le cockpit (registre) en présentait 9 comme `on`. Aucun code ne les lit : ils annonçaient de l'activation. Marqués `wired=False` et remis à `off` — le registre ne peut plus afficher un switch inatteignable comme actif.

`ODYSSEUS_DEEPEVAL`, `ODYSSEUS_SUPABASE`, `ODYSSEUS_VAULTWARDEN`, `ODYSSEUS_PLAYWRIGHT`, `ODYSSEUS_BROWSER_HARNESS`, `ODYSSEUS_ZEN_FROM_ENDPOINT`, `ODYSSEUS_INPROCESS_DISCORD`, `ODYSSEUS_INPROCESS_TELEGRAM`, `ODYSSEUS_CHANNEL_AGENT_REPLY`

`tests/test_killswitch_registry.py` interdit désormais le retour de cette dérive : un descripteur `wired=True` doit avoir un lecteur réel, un `wired=False` ne doit pas en avoir, et le `default` affiché doit être celui que le code appliquera.

### 4.2 Descripteurs du registre contredisant leur propre lecteur

Seize descripteurs déclaraient `default: "on"` alors que leur lecteur retombe sur `off` ou sur chaîne vide — le cockpit affichait donc `effective=true` sur du OFF.

`LIVE_ORCHESTRATION`, `CODEBURN`, `LANGFUSE`, `GOVERNANCE_ANCESTRY`, `LANGGRAPH`, `RRF_FUSION`, `DOCLING`, `TREESITTER`, `DISABLE_MCP`, `OBSIDIAN_MCP`, `GRAPHIFY`, `CBM`, `SERENA_MCP`, `AGENTSEAL`, `N8N`, `AGENT_CATALOG`

Tous réalignés sur le code. **Corollaire notable** : `AGENT_CATALOG` est `off`, donc `/api/agents` renvoie `[]` — ce qui confirme UC-10 en DORMANT.

### 4.3 Variables d'environnement (la liste précédente était périmée)

Les divergences de nom signalées le 2026-09-25 ont été **nettoyées** : `ODYSSEUS_DURABLE_EXEC`, `ODYSSEUS_MEMORY_PROVENANCE`, `ODYSSEUS_VISUAL_OUTPUT` et `ODYSSEUS_PROJECT_MANIFEST` ont **0 occurrence** dans `.env`. `ODYSSEUS_THOUGHT_BUS` n'y est plus non plus et n'est posée que par `launch_fast.py:8`, sans lecteur — l'événement SSE `thought_bus` (`opencode_engine.py:349`) est inconditionnel.

| Constat | État réel |
|---|---|
| `ODYSSEUS_TRAEFIK=on` | Seule variable `ODYSSEUS_*` de `.env` (**49**) qu'aucun `.py` du dépôt ne lit. Relève du Palier P2 (reverse proxy). |
| `ODYSSEUS_TOOL_DISCOVERY` | Lue (`content_security.py:101`) mais `ToolDiscovery` a 0 appelant ⇒ sans effet. Défaut `off`, et absent du registre. |
| 5 variables P2 lues hors Python | `ODYSSEUS_OPA`, `ODYSSEUS_PREFECT`, `ODYSSEUS_OPA_URL`, `ODYSSEUS_API_TOKEN` : lues par les scripts de lancement, pas par le cœur applicatif. |

### 4.4 Divergences de décompte

- « 35 descriptors » puis « 47 étendus aux switches agents » (mesure du 2026-09-25) → le registre en compte **54**.
- Le bloc « Sprint 1a » de `04-OBJECTIFS-COUVERTURE.md` affirme que « les statuts ACTIF/PARTIEL/DORMANT n'ont pas bougé » et que l'Activation montera « plus tard ». C'est faux : le Palier 0 a **rétrogradé** UC-05 et fait passer UC-11 de DORMANT à PARTIEL.
- La liste « Actives (28) » de ce même document inclut « multi-agent live » et « goal-ancestry live », ce que les switches agents tous `off` contredisent.

### 4.5 Concordance avec l'audit interne existant

**Levée au Sprint 5 (v10 §1).** `tools/sfd_audit.py` n'est plus seulement un audit préexistant non daté : il **se vérifie lui-même** à chaque exécution. Le balayage initial a mesuré que **19 de ses 22 affirmations de chemin étaient fausses** (3 vraies, 3 déplacées, 16 périmées) et que **32 fiches booléennes ne nommaient aucun fichier**. Les 18 chemins corrigibles ont été réécrits vers des fichiers vérifiés ; les 3 sans équivalent sont tracés dans `CHEMINS_RETIRES`, qui fait **échouer** l'outil s'ils sont réaffirmés comme code. La réserve est donc levée en **preuve** : l'outil ne peut plus être cité à l'appui d'une affirmation sans avoir été exécuté.

### 4.6 Défaut d'atteignabilité : des principes câblés hors d'atteinte (trouvé au Sprint 3, item 7)

Le modèle de statut ci-dessus demande « le switch est-il `on` ? le module est-il
appelé ? », jamais « **le chemin principal atteint-t-il ce module ?** ». Les deux
questions ne sont pas équivalentes, et l'écart s'est avéré décisif.

**Mesuré.** `_classify_agent_request` calculait
`low_signal = not continuation and not domains` (`agent_loop.py:1123`), `domains`
venant d'une liste **fermée** de mots-clés presque entièrement **anglaise**. Un tour
qui n'y correspondait pas était donc classé « conversation sans objet » :

| Tour | `low_signal` avant |
|---|---|
| « écris un script pour lister les fichiers du projet » | `True` |
| « ajoute une fonction de tri à src/parser.py » | `True` |
| « explique-moi la différence entre ces deux approches » | `True` |

Or la porte `_direct_low_signal` (`agent_loop.py:2339-2347`) teste
`not relevant_tools` — l'**argument de l'appelant**, jamais la récupération interne,
qui a lieu plus bas. `routes/chat_routes.py:1388`, la route de chat principale, ne
passe pas `relevant_tools`. La voie directe émet `metrics` puis `return`
(`agent_loop.py:2436`) : **tout ce qui suit est sauté**, M6.1 à M6.9 comprises.

Un tour réel donnait **0 événement M6** depuis la route principale, et des
événements dès qu'on passait `relevant_tools` — ce que faisaient tous les tests des
items 1 à 6, c'est-à-dire qu'ils testaient un chemin que les gens n'empruntent pas.
Seul `src/task_scheduler.py:1692` compose `relevant_tools` et atteignait M6.

**Conséquence sur l'Activation.** P16, P17, P19, P20 et P22 étaient câblés, testés et
mutation-vérifiés — et injoignables depuis la route principale. C'est la raison la
plus probable pour laquelle l'Activation ne bougeait pas. Ce n'est pas le modèle de
statut qui mentait sur ces cinq lignes : il ne les interrogeait pas sur ce point.

**Corrigé** dans le même correctif : `_is_substantive_request` (`agent_loop.py:950`,
avec `_fold` `:891` et trois motifs) donne un second avis, et `low_signal` signifie désormais
« rien à faire ici » au lieu de « aucun mot-clé reconnu ». Quatre signaux : verbe
d'action, référence à un artefact, question ayant une matière, plancher de longueur.
Le routage par domaine est **inchangé** — un test le verrouille — donc la sélection
d'outils n'a pas bougé ; seule l'habilitation à entrer dans la boucle a changé.

Preuve : `tests/test_sprint3_reachability_m6.py` (18 tests, 2 mutations vérifiées),
dont la preuve de fin qui appelle la boucle **comme le fait `chat_routes.py:1388`**
et exige qu'un événement M6 soit émis. Contre-épreuve explicite : les salutations
restent sur la voie directe — une boucle agent complète pour « bonjour » serait un
aller-retour LLM payé sans rien apporter.

**Ce que ça ne change pas.** Le compteur ACTIF/PARTIEL de la section 3 reste celui du
Palier 0 : ces cinq principes étaient comptés wired, et ils le sont toujours. Ce qui
a changé, c'est qu'ils sont enfin **atteignables**. Une re-mesure des statuts tenant
compte de l'atteignabilité reste à faire — c'est une décision de modèle, pas un
câblage.

---

## 4 bis. Statut des défauts trouvés **hors plan**

Le rapport de clôture du Sprint 3 listait, sous « ce que la mesure a contredit »,
des défauts trouvés hors plan sans dire s'ils avaient été **corrigés** ou
seulement **observés**. Cette ambiguïté a coûté un aller-retour. Règle désormais
appliquée : *tout défaut listé porte un statut explicite — corrigé avec preuve, ou
ouvert avec la raison de ne pas l'avoir traité.*

Ces deux-là sont des **corrections**, pas des principes supplémentaires : ils
n'ont donc pas de numéro, et les compteurs des tableaux ci-dessus n'en tiennent
pas compte.

| Défaut trouvé hors plan | Statut | Preuve | Reste |
| **La compensation de saga : l'affirmation d'origine était fausse, et mon correctif du v10 l'était aussi** | **CONSIGNÉE ABSENTE (décision v11)** | Mesuré à `2c59704`, **par lecture du code et non par nom** : le **déclencheur** est câblé — `DurableExecutor._handle_step_failure` (`src/durable_execution.py:200`), 2 appelants réels (`:161`, `:188`) ; le **mécanisme** n'est **jamais armé** — `WorkflowStep.compensation` vaut `None` (`:88`) et **0 construction** du dépôt ne fournit `compensation=` ; l'**action** n'est **pas exécutée** — la branche journalise `Compensating step …` et passe à `COMPENSATED` sans rien lancer. Le paquet npm **a** la compensation (`packages/sfd-durable/src/index.ts`, `async compensate(id)`) : le port Python non, et l'affirmation d'origine ne parlait pas du bon port. | **ABSENTE (avec la raison)** — et non *dormante* : une capacité dormante s'allumerait avec un interrupteur, or **aucun interrupteur ne peut armer ce crochet**, puisque rien ne fournit `compensation=`. **Non implémentée**, comme décidé : candidat de sprint à scoper séparément. **Faux positif retracté** : l'`ABSENTE` écrit au v10 était une déduction par nom de symbole — exactement ce que la règle du v11 §3.1 interdit. |
| Le point demandé par le v10 sur les portes de modularité : 6 des 10 chantiers MOD-1→10 agissaient sur une grandeur que rien ne surveillait | **CORRIGÉ (avec preuve)** — 5 seuils ajoutés, les 10 chantiers couverts | Les 3 seuils du Sprint 4 couvraient 4 chantiers (MOD-1, MOD-2, MOD-6, MOD-8). Les 6 autres agissaient sur une grandeur non gelée : `paquets_sfd_non_tranches` **9**, `globals_dans_src` **46**, `fournisseurs_hors_interface` **0**, `modules_resolution_modele` **12**, `imports_de_shim` **78**. Toutes mesurées **structurellement** (AST, résolution d'import, JSON parsé) et confirmées par une **seconde mesure indépendante** — la règle du Sprint 4 : un chiffre ne devient une vérité qu'après avoir survécu à deux mesures. **10 mutations, 10 capturées**, dont une qui faisait compter une mention de paquet dans un commentaire comme une référence. | **CORRIGÉ**. Trois conséquences, dans le rapport : une règle du Sprint 4 ("une porte à 0 est une porte cassée") était **absolue alors qu'elle n'est dérivée que du cas descendant** — précisée, pas contournée, et la non-vacuité du seuil à 0 est prouvée ; un seuil au-dessus de la mesure exige désormais `releve_si` ; et **MOD-11bis est retiré du plan** car `packages/` contient 13 `.ts` et 0 `.py` — la porte y gèlerait un zéro qui surveille du vide. |
| `tools/sfd_audit.py` affirme 7 chemins de code inexistants, dont `src/thought_bus/` | **CORRIGÉ (avec preuve)** — l'outil se vérifie lui-même désormais | Balayage **structurel** (existence de fichier + résolution AST), pas par sous-chaîne : sur **22 affirmations de chemin**, **3 étaient vraies, 3 simplement déplacées, 16 périmées**. La plupart des *capacités* existent, sous d'autres noms — c'est le chemin qui mentait, sauf pour la compensation de saga : `src/durable_execution.py` définit `DurableExecutor`, `WorkflowStep` et `RetryPolicy`, mais **ni classe Saga ni fonction de compensation** (vérifié par AST), et la note affirmait « Saga compensation implémentée ». **Une vérification par existence ne l'aurait pas vu** : il fallait lire l'affirmation. Il fallait lire l'affirmation. **↺ CORRECTION v11 : cette lecture était elle-même fausse, dans l'autre sens.** Le mécanisme existe : `DurableExecutor._handle_step_failure` (`src/durable_execution.py:200`), avec **2 appelants réels** (`:161`, `:188`). J'avais cherché des symboles dont le *nom* portait `compens`/`saga` ; la méthode porte le nom de son **déclencheur**, pas de son action. État consigné depuis : la compensation est un **échafaudage câblé, jamais armé** (0 construction ne fournit `compensation=`) et **l'action n'est pas exécutée**. | (`code: True`, `ok: True`) ne nommaient aucun fichier** — un booléen n'est falsifiable par personne ; elles sont désormais comptées et visibles. 18 chemin réécrits vers des fichiers vérifiés, 3 chemins retirés tracés dans `CHEMINS_RETIRES`. Le champ `note` était balayé aussi : `agent_instructions.py` y était réaffirmé, et chercher le seul champ `code` aurait laissé la moitié du problème debout. | **CORRIGÉ** : `verifier()` résout chaque chemin et sort en erreur si une affirmation n'est ni vérifiée ni déclarée. `CHEMINS_PERIMES` est **vide parce qu'elle l'est**, et non supprimée — le mécanisme reste, le chemin pourri ne peut plus passer. **10 tests, 12 mutations, 12 capturées** — dont celle qui supprime le `sys.exit(1)`, que neuf tests laissaient passer. |
| « Bus de pensées » signalé comme une capacité de 11 fichiers | **CORRIGÉ PAR LA MESURE — il n'y a pas de capacité à interrupter** | Mesuré au `0e4d4f9` : `src/thought_bus/` **n'existe pas** — et `tools/sfd_audit.py:32` l'affirme pourtant comme code implémenté de P3. Le seul « bus » réel est `self.bus.emit(...)` dans `src/opencode_engine.py`, et l'unique événement SSE étiqueté `thought_bus` (`:349`) porte un **`phases_walked: 7` en dur** — une constante, pas une mesure. Mes « 11 fichiers » étaient un **compte de chaîne** : ils comptaient `chain-of-thought` et `_replace_gemma_thought`, sans rapport. | **Aucun interrupteur créé, délibérément** : un interrupteur pour une capacité qui n'existe serait exactement le défaut que le registre existe pour interdire — une entrée `wired=False` pour un switch qui n'a rien a gouverner. La décision du Chef (garder, étendre, retirer) doit être reprise sur ces faits, pas sur mon compte. **CORRIGÉ (Sprint 5, v10 §1)** : voir la ligne dédiée ci-dessous. |
| Deux pièges de lecture, qui n'étaient pas des bugs mais des occasions de se tromper : `check_citations` se confond avec INT-10, et `run_script`/`ssh_command` ressemblaient à une escalade | **TRAITÉS (Sprint 4 items 6 et 7)** — aucun des deux n'était un défaut, tous deux devenaient un piège le jour où le code change | **Item 6** : la section « ce que cet outil NE fait PAS » est écrite dans `check_citations.py` lui-même, et un test échoue si `DOC_GLOBS` s'élargit hors documentation ou si la section disparaît. **Item 7** : la contrainte latente est transformée en deux tests — l'**atteinte** (`BUILTIN_ACTION` n'est pas référencé par la boucle : pas d'outil d'agent, donc pas de voie d'escalade) et la **couverture** (la détection des actions exécutantes est vérifiée non vide, parce qu'une détection qui ne trouve plus rien donnerait un vide silencieux). `tests/test_sprint4_faux_amis.py`, 6 tests. | **Ce que ces items ne font pas, et qu'il faut dire** : ils ne ferment rien aujourd'hui. La porte du propriétaire ne couvre toujours pas `run_script` — elle n'a pas à le faire, puisque l'atteinte est absente, et c'est ce qui est vérifié à chaque exécution. Le jour où la boucle exposerait les actions builtin, les deux tests tomberaient ensemble. |
| Les mesures du constat vivaient dans `/tmp` : elles disparaissaient au redémarrage, et la discipline « mesurer avant de croire » reposait sur la mémoire d'un agent | **CORRIGÉ** (Sprint 4 item 5) | `tools/check_governance.py` + `tests/test_sprint4_gouvernance_porte.py` — 7 tests, 8 mutations (2 mortes, voir le commit). Le **tri** capacités/configuration est **extrait** du test de l'item 2, jamais recopié : deux listes divergeraient et la divergence serait invisible. Le compte est **écrit** dans `TRACEABILITY.md` par `--write`, jamais recopié. Apporte aussi le signal **`called`** — avoir un lecteur n'est pas être appelé — que `wired` ne peut pas dire. | **Le signal `called` a été écrit faux trois fois avant d'être juste** : un import prend quatre formes (`from a.b.c`, `from .c`, `from src import trace_writer`, et les shims `src/agent_loop.py` ↔ `archive/legacy/`). Chaque forme omise faisait annoncer « jamais appelé » pour un module appelé à chaque tour : le compte est passé de **9 à 5**, et les 5 restants ont été vérifiés à la main. Un signal qui **exagère** est aussi un mensonge : il décourage de lire celui qui dit juste. |
| La modularité ne se mesurait nulle part : `core.database` est passé de 64 à 120 importeurs sans qu'une porte le voie, et les dix chantiers MOD-1→MOD-10 n'étaient pas conduisables | **CORRIGÉ** (Sprint 4 item 4, MOD-11) | `tools/check_modularity.py` + `tests/test_sprint4_modularite_porte.py` — 9 tests, 14 mutations. Trois seuils **au niveau actuel** : god node 120, arêtes `src/*→routes.*` 30, imports statiques de `route_loader` 0 (dynamique via pkgutil). 9 tests, dont la **frontière exacte** (30 vert / 31 rouge) et un garde anti-inflation. | **Deux pièges corrigés en route** : compter les arêtes depuis les tests et le chargeur donnait 421 et un seuil que l'on contourne en supprimant un test — donc un seuil qui mesure la mauvaise grandeur **et** se contourne seul ; et `packages/sfd-*/src/` existe dix fois, donc un test par « `src` dans le chemin » aurait compté des paquets sans `.py` aujourd'hui et explosé demain. Le seuil est « ne pas augmenter », jamais « être sous un idéal » : l'idéal, c'est MOD-6. |
| Le vérificateur du registre était **aveugle** aux lectures sans défaut littéral (`os.getenv("X")`), et une entrée portait `wired=False` à tort | **CORRIGÉ** (Sprint 4 item 2) | `tests/test_killswitch_registry.py` — 6 variables étaient invisibles ; `ODYSSEUS_ZEN_FROM_ENDPOINT` était donc déclaré non câblé alors que `src/zen_router.py:130` le lit. Le drapeau avait **pourri sans bruit**, exactement ce que la docstring du test interdisait. Vérificateur réparé, entrée corrigée dans le même mouvement, sinon le mensonge serait revenu au prochain nettoyage. | rien |
| Le tableau des kill-switchs ne pouvait pas répondre à sa question : **12** capacités lues par le code de production, absentes du registre, dont 2 à `on` | **CORRIGÉ** (Sprint 4 item 2) | `tests/test_sprint4_gouvernance_registre.py` — 6 tests, 10 mutations. Toute variable lue par la production doit être **au registre ou classée** comme configuration, avec sa raison écrite à la main. Registre : 54 → **65** entrées, 16 → **17** `on` (seul ajout : `ODYSSEUS_OTEL`, déjà actif ; OPA retiré). | **Deux écarts distincts, signalés et non corrigés** : (a) l'exécution **distante** de scripts (`ODYSSEUS_SCRIPT_HOST` = cible SSH) n'a aucun interrupteur — la variable est un paramètre, la capacité qu'elle garde n'a pas d'interrupteur ; (b) la fonctionnalité « bus de pensées » (11 fichiers) est dans le même cas. Ce sont des capacités **sans** interrupteur, l'inverse du défaut d'audit croisé. Candidats de sprint futur. |
| `ODYSSEUS_OPA` : moteur de politique sécurité, `on` par défaut, invisible, et **0 importateur** hors tests | **CORRIGÉ** (Sprint 4 item 2), conformément à la décision v8 | **Le défaut a dû être coupé dans le CODE**, pas au registre : `opa_client.py:23` lisait `os.getenv("ODYSSEUS_OPA", "on")`, donc poser `default=off` au registre n'aurait changé que l'affichage — le tableau aurait menti, ce qui est précisément ce que le registre existe pour interdire. Attrapé par `tests/test_killswitch_registry.py`, qui compare le défaut déclaré à celui que le lecteur réel applique. 15 tests cumulés, 15 mutations. | **Écart assumé, à valider** : le v8 proposait aussi `wired=False`. **Refusé** — `wired` signifie « un lecteur existe », et `opa_client.py:23` en est un ; écrire `wired=False` afficherait « ce switch n'est pas réel » alors que la lecture est réelle et que c'est l'**intégration** qui manque. Un mensonge dans l'autre sens n'est pas mieux. Le signal `called` (avoir un lecteur ≠ être appelé) reste à faire en item 5. Le **branchement réel** d'OPA est un chantier séparé. |
| Le lanceur écrivait **trois** variables que rien ne lit — `ODYSSEUS_DURABLE_EXEC`, `ODYSSEUS_THOUGHT_BUS`, `MCP_CONNECT_TIMEOUT` (`launch_fast.py`) | **CORRIGÉ** (Sprint 4 item 1) | `tests/test_sprint4_lanceur.py` — un test échoue pour **toute** variable écrite par le lanceur sans lecteur, donc pour la forme du défaut et pas pour un nom. 4 tests, 7 mutations. | **Un constat distinct, non traité ici** : la fonctionnalité « bus de pensées » touche 11 fichiers et n'a **aucun** interrupteur — ni dans le code, ni au registre. Le lanceur écrivait `ODYSSEUS_THOUGHT_BUS=on` pour une chose qui n'existe pas comme réglage. C'est l'inverse du défaut d'audit croisé : là un interrupteur sans capacité, ici une capacité sans interrupteur. Candidat de sprint futur ; l'insérer au registre maintenant créerait une entrée `wired=False` pour une capacité non gouvernée, ce qui serait exact mais ne la gouverne pas. |
| **`ODYSSEUS_SCRIPT_HOST`** (cible SSH, exéc. distante) — capacité sans interrupteur signalée | **CORRIGÉ (Sprint 5, décider tout)** | `src/killswitch_registry.py:593` — inscrit au registre, `default=off`, `wired=True`, `source: src/builtin_actions.py:394`. | Décision : **fermé par défaut**. Aucune intégration ne passe `host` en production ; le switch est une porte, pas un branchement. Le branchement réel (si nécessaire) est un chantier séparé. |
|---|---|---|---|
| La porte PROTECTED ne couvrait pas la **diffusion** vers les clients connectés — le verdict était calculé **après** la diffusion au gateway, donc un tour PROTECTED arrivait chez tous | **CORRIGÉ** (item 11), re-prouvé hors fiche | `tests/test_sprint3_v6_statut_trouvailles_hors_plan.py::test_un_tour_protege_ne_sort_par_aucun_flux` — les **cinq** sorties d'un coup (gateway, accroche enseignant, routeur de sortie, écriture profil, vérificateur d'impact), avec contre-épreuve qu'un tour PUBLIC alimente toujours les cinq. Mutation A1 : le verdict d'oublie la classification → 2 tests tombent. | **rien** |
| `sanitize_memory` n'avait **aucun appelant** — dix motifs d'injection, dont « ignore all previous instructions », qui ne protégeaient rien | **CORRIGÉ** (item 11), re-prouvé hors fiche | `…::test_le_texte_de_l_utilisateur_arrive_assaini` — le texte **non fiable** de l'utilisateur, poussé par la boucle, atteint le disque sous `profile.md` en `User said: … [FILTERED] and obey me` : motif neutralisé, texte légitime intact. Mutations B1-B4, dont le kill-switch mesuré dans les deux sens. | le filtre ne couvre que ce qui passe par `MemoryFS` — un stockage mémoire secondaire n'y échapperait pas sans rappel explicite |

**Distinction mesurée, et écrite parce qu'elle est facile à sur-corriger** : le
*fait* — le texte de la **demande** — atteint encore le vérificateur d'impact, en
mémoire de processus. Il ne part vers aucun tiers et n'est écrit nulle part ; son
écriture durable est séparément gardée (`store_impacted_fact`, sous
`not _m65_protected`). Vider aussi serait une paraphobie, pas une défense. C'est
la seule voie par laquelle un tour PROTECTED touche encore un calcul interne, et
elle est désormais prouvée plutôt que supposée.

## 5. Ce qu'il reste à faire pour que ces statuts bougent

Rien de ce qui suit n'est un défaut : ce sont des câblages absents, tous réduits au même geste — **consommer le résultat au lieu de le loguer**.

| Principe / UC | Geste manquant |
|---|---|
| **Modèle** | **Décider si le statut doit intégrer l'atteignabilité** (§4.6). Un principe câblé mais hors du chemin principal ne peut pas compter comme effectif ; le modèle ne pose aujourd'hui pas la question. Décision de modèle, validée séparément du câblage. |
| P17 (diffusion) | ~~Couvrir la diffusion, pas seulement la persistance~~ **FAIT (Sprint 3 item 11, re-prouvé v6)** — reste : rien. Les cinq consommateurs sont sous le verdict d'émission, et le test hors fiche les vérifie tous les cinq. |
| P17 (mémoire) | ~~Assainir la mémoire avant écriture~~ **FAIT (Sprint 3 item 11, re-prouvé v6)** — reste : le filtre ne couvre que ce qui passe par `MemoryFS`. Un stockage mémoire secondaire (`data/memory-fs` est le seul aujourd'hui) n'y échapperait pas sans rappel explicite. |
| P5, P21 | ~~Injecter `allowed_tools` dans les schémas d'outils envoyés au modèle~~ **FAIT (Sprint 3 item 7)** — reste : **`CLASSIFY` n'est jamais atteinte** (`agent_loop.py:3040` avance la boucle canonique avant de résoudre la phase, `:3049`) ; `_TOOL_CATEGORY_MAP` ne couvre que 37 des 68 schémas, donc 31 outils ne sont **jamais** restreints, quelle que soit la phase ; `blocked_tools_for_owner` (`tool_security.py:226`, appelée `agent_loop.py:2320`) retire 38 outils en amont et **ne dépend pas de l'owner** ; `TOOL_DISCOVERY=off` et absent du registre. |
| P19 | ~~Fournir une vraie `hypothetical_response` au vérificateur d'impact, et relier `should_store` au store~~ **FAIT (Sprint 3 item 4)** — reste : le comparatif est une ablation lexicale, pas un vrai « et sans ce fait ? » généré ; un LLM nominal donnerait un contrefactual plus fidèle (bloqué par `OPENCODE_API_KEY` absente). |
| P14, UC-02, UC-11 | ~~Appeler `create_workflow` pour persister un workflow, et résoudre le chemin du vault pour le checkpoint~~ **FAIT (Sprint 3 item 8)** — reste : la conversation persistée se termine sur un message `tool` sans tour assistant suivant, forme que certains endpoints OpenAI-compatibles stricts refusent ; le plateau est donc le debut d'un round, pas sa fin. Arbitrage assumé — l'alternative perdait exactement le travail à sauver. |
| P16 | ~~Créer `topics/agent-output.md` (ou gérer son absence) pour que `[observed]`/`[inferred]` aient un producteur~~ **FAIT (Sprint 3 item 6)** — reste : `memory_writer.py` a toujours 0 appelant ; c'est une brique orpheline, pas un câblage manquant. |
| P17 | ~~Bloquer l'écriture durable sur une branche `PROTECTED`~~ **FAIT (Sprint 3 item 1)** — reste : ~~faire **bloquer l'émission** par M6.6~~ **FAIT (Sprint 3 item 11)** — reste : (`:4386-4388` loggue « output blocked » sans bloquer) et appliquer `validate_memory_entry` sur `POST /api/memory/add` (0 appelant). |
| P20 | ~~Injecter `language`/`tone`/`format` dans le prompt~~ **FAIT (Sprint 3 item 2)** — reste : élargir la directive aux autres préférences, et brancher l'API live sur le même moteur de priorité. |
| P22, UC-17 | ~~Donner un effet de bord à `OutputDecision`~~ **FAIT pour l'écriture (Sprint 3 item 3)** — reste : peupler `connected_mcp_tools` (branche `MCP_TOOL` morte) et **rendre** le fichier produit dans l'UI. |
| UC-05 | ~~Empêcher `on_round_start` d'écraser une phase posée explicitement par l'API~~ **FAIT (Sprint 3 item 5)** — reste : faire suivre au *dispatch* d'agents (M4) la phase du registre ; aujourd'hui `resolve_current_phase` (`phase_resolver.py:37-38`) réinfère au lieu de lire, donc le verrou d'outils tient mais l'aiguillage d'agents ignore un choix d'API. |
| UC-12 | ~~Exposer une lecture des traces (route d'audit), ou assumer que les traces sont un artefact de debogage~~ **FAIT (Sprint 3 item 9)** — reste : la lecture est **bornée à un jour** et sans pagination ; sur une journée de plusieurs milliers de traces, un audit doit encore descendre page par page. Et le filtrage multi-critères est un `ET` strict, donc « les décisions de ce run **et** de ce jour » demande deux appels. Non traités, et dits comme tels. |
| P18 | ~~Faire circuler le jeton de version entre deux appels distincts, sinon le contrôle ne peut pas s'exercer~~ **FAIT (Sprint 3 item 10)** — reste : deux limites, dites et non dissimulées. (a) Le verrou est un `threading.RLock` **en mémoire** : il sérialise les fils d'un même processus, pas deux processus ni deux réplicas sur le même dossier — la garantie `os.replace` tient, pas l'exclusion. (b) Un `SIGKILL` entre la création du temporaire et le `os.replace` laisse un `.tmp` dans l'arborescence mémoire ; il ne pollue pas `memory_list` (qui ne globbe que `*.md`) mais il s'accumule. Les deux sont des limites de conception, pas des défauts de l'item. |

---

## 6. Décisions prises sur les escalades gelées (décision Chef, Sprint 5)

| Escalade | Variable | Décision | Raison |
|----------|----------|----------|--------|
| P8 | `ODYSSEUS_PLANNING_ENGINE` | **OFF** (gelé) | Le moteur de planification structuré est absent du registre et du `.env`. `approved_plan` n'est qu'une note de prompt. Activer est une décision de politique, pas de câblage. |
| P12 | `ODYSSEUS_AGENT_CATALOG` | **OFF** (gelé) | Le catalogue d'agents .opencode n'est pas chargé au boot. `dispatch_for_phase` a 0 appelant en production. |
| UC-10 | `ODYSSEUS_MULTI_AGENT` | **OFF** (gelé) | 12 switches agents `off` par conception. Démultiplication coûteuse. Ne pas casser. |
| LangGraph | `ODYSSEUS_LANGGRAPH` | **OFF** (gelé) | Flag absent, default off. Indépendant de CLASSIFY. |
| AUTOEVAL_ALLOW_RESET | `ODYSSEUS_AUTOEVAL_ALLOW_RESET` | **OFF** (gelé) | Un `git reset --hard` sur un arbre non commité détruit le travail. Ce n'est pas un item de backlog. |

---

## 7. Sources

- `docs/master-ref/01-SFD-v3.1.md` §3 (P1-P22) et §4 (UC-01-19).
- Ancienne checklist `08-VERIFICATION-ETAT-ACTUEL.md` (retirée le 2026-09-25) — conservée dans l'historique Git.
- `src/killswitch_registry.py` — **54** descripteurs, `read_states()` (expose `default`, `raw`, `is_default`, `effective`, `wired`).
- `.env` — **49** variables `ODYSSEUS_*` (gitignoré) ; `.env.example` — template committé.
- `tests/test_killswitch_registry.py` — 4 tests d'audit qui interdisent au registre de mentir.
- `tests/test_progressive_disclosure.py` — 28 tests, dont la garde statique sur le site d'appel mort.
- `tests/test_sprint3_p5_p21_disclosure_restricts.py` — 11 tests, 4 mutations vérifiées (preuve P5/P21).
- Mesure de tests : `docs/traceability/04-TESTS-REALITE.md` (4 887 PASS · 2 skipped · 0 FAILED).
- `tools/sfd_audit.py` — **auto-vérifié** depuis le Sprint 5 : 36 chemins vérifiés, 0 non résolu. À exécuter avant d'être cité ; sa sortie seule ne suffit pas (32 fiches booléennes restent sans preuve et sont comptées comme telles).
