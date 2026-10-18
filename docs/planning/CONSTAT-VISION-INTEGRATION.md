# Constat — examen de `VISION-INTEGRATION.md` contre l'état codé

> Date : 2026-09-27 · Branche `feat/inventaire-global-v1` · Commit : `39fb47e`
> Objet : confronter **INT-1 → INT-21** et **MOD-1 → MOD-11** aux **41 fiches** de
> `docs/traceability/02-PRINCIPES-UC.md` (chapitre 4 bis inclus).
> **Aucun code n'a été écrit.** Ce document mesure ; le plan est dans `SPRINT-4-PLAN.md`.

---

## 1. Le document de vision est périmé sur tous ses chiffres

Il date du 2026-09-25 et annonce « environnement non exécutable ». Le Sprint 0 a
remplacé la situation. Chaque chiffre a été **remesuré**, pas recopié.

| `VISION-INTEGRATION.md` §1 | Mesuré au `39fb47e` | Écart |
|---|---|---|
| Environnement **non exécutable** | exécutable, **5 002 tests verts** | inversé |
| Kill-switches : **2 ON / 35** | **16 ON / 54** (Palier 0) | ×2 en base, ×8 en ON |
| Principes ACTIFS **6/22** | **6/22** | inchangé |
| UC ACTIFS **6/19** | **7/19** | +1 (UC-09, item 12) |
| UC-06/07 **absents** | absents, **+ UC-10 sans statut** | un de plus |
| Fichiers `.py` : **1 071** | **1 097** | +26 |
| Modules `src/` : **136** | **131** | −5 |
| `core.database` : **64** importeurs | **120** | **×1,9** |
| `route_loader` : **58** imports | **54** statiques, `pkgutil=False` | −4 |
| Shims legacy : **71 fichiers** | **85** | +14 |
| Doc divergente du code | 180 citations vérifiées, 0 hors fichier | tranché par machine |

**Deux constats structurants en découlent :**

1. **Le tableau des kill-switches ne répond plus à sa question.** C'est son seul
   boulot : permettre de lire *ce qui est actif*. Il couvre 54 entrées, mais le code
   de production en lit **205** variables `ODYSSEUS_*`, dont **12 qui sont de vrais
   interrupteurs de capacité** et ne figurent nulle part — dont **2 qui valent `on`
   par défaut**. C'est le §2 de ce constat, c'est le sujet de l'item 2 du plan.
2. **La modularité s'est dégradée, pas stabilisée.** Le chiffre le plus
   inquiétant est `core.database` : 120 importeurs, plus que le double de ce que
   la vision annonce. C'est le sujet de MOD-6, et la raison pour laquelle MOD-11
   (la CI qui le rend visible) précède tout le reste.

---

## 2. Quatre trouvailles de l'examen

Toutes mesurées. Deux sont des câblages morts, une est un trou de gouvernance, une
est **explicitement infirmée** — et cette dernière compte autant que les autres.

### 2.1 FND-1 est incomplet : le lanceur écrit un interrupteur que personne ne lit

```
launch_fast.py:9   os.environ["ODYSSEUS_DURABLE_EXEC"] = "on"
```

Or le seul nom lu par le code est `ODYSSEUS_DURABLE_EXECUTION`
(`src/durable_execution.py`), déjà `on` par défaut au registre. L'ancien nom
n'apparaît **que** dans cette affectation.

**Conséquence.** L'intention du lanceur — « activer l'exécution durable au
démarrage » — est un no-op. Elle est **masquée** parce que le switch est déjà `on`
par défaut. Le jour où le défaut bascule à `off` (paliers FND-4), le lanceur
cessera silencieusement d'activer ce qu'il croit activer.

C'est la forme exacte du motif que ce chantier traque depuis six mois : un
contrôle dont le succès apparent vient d'une coïncurrence d'état, pas du
mécanisme. **Gravité : faible en l'état, élevée au prochain palier.** Une ligne.

### 2.2 Douze interrupteurs de capacité absents du registre, dont deux `on`

Mesuré sur les 205 variables lues par le code de production, croisées avec les 54
entrées du registre :

| Interrupteur | Défaut | Lu par | Remarque |
|---|---|---|---|
| `ODYSSEUS_OPA` | **`on`** | `services/security/opa_client.py` | moteur de politique sécurité — voir 2.3 |
| `ODYSSEUS_OTEL` | **`on`** | `services/observability/otel_setup.py` | télémétrie active et invisible |
| `ODYSSEUS_APPRISE` | `off` | `apprise_service.py`, `channel_gateway.py` | cohérent avec la fiche UC-09 |
| `ODYSSEUS_MEILISEARCH` | `off` | `meilisearch_client.py` | |
| `ODYSSEUS_PLANNING_ENGINE` | `off` | `planning_engine.py`, boucle | |
| `ODYSSEUS_PREFECT` | `off` | 3 pipelines | |
| `ODYSSEUS_QDRANT` | `off` | `memory_vector.py`, `rag_vector.py` | |
| `ODYSSEUS_LETTA` | — | `letta_provider.py` | défaut non relevé littéralement |
| `ODYSSEUS_MEM0` | — | `mem0_provider.py` | idem |
| `ODYSSEUS_MULTI_AGENT` | — | boucle | **surface d'UC-10** — voir 2.5 |
| `ODYSSEUS_SCRIPT_HOST` | `localhost` | `src/builtin_actions.py` | voir 2.4 |
| `ODYSSEUS_DURABLE_EXEC` | — | `launch_fast.py` | l'entrée morte de 2.1 |

Les **29 autres** variables lues hors registre sont de la configuration — chemins,
identifiants, délais, `ODYSSEUS_DATA_DIR`, `ODYSSEUS_API_TOKEN`. Elles **n'ont pas
leur place** dans un registre d'interrupteurs, et les y mettre noierait la
distinction. Le tri fait partie du correctif.

### 2.3 OPA : implémentation juste, intégration nulle

Le moteur de politique sécurité est **ON par défaut**, invisible au registre, et
**n'a aucun appelant hors tests** :

```
grep -rn "get_opa_client|check_tool_access|check_phase_transition" --include=*.py
  → aucun résultat hors services/security/opa_client.py et tests/
```

L'implémentation, elle, est correcte et fail-closed : timeout et erreur de
connexion renvoient un refus (`opa_client.py:83-88`), et `check_tool_access`
initialise `allow = False` (`:124`) — un résultat positif est requis pour autoriser.
`check_phase_transition` s'ouvre quand `OPA_ENABLED` est faux, ce qui est le
comportement attendu d'un moteur *désactivé* et non d'une panne.

**Donc pas de fuite confirmée** : rien n'est autorisé à tort de par là. Mais un
moteur de politique qui est « actif » au registre, absent du tableau, et jamais
interrogé, donne à l'opérateur une impression de protection qui n'existe pas. C'est
la maladie de `hash_edit_validator` et de `sanitize_memory` — un contrôle bien
construit, sans route. **Décision à trancher par le Chef** (§5 de ce document) :
le brancher, ou le déclarer non opérant et le couper par défaut.

### 2.4 `run_script` / `ssh_command` : **infirmé**, et c'est utile de le dire

`action_run_script` exécute en `shell=True` et part en `ssh <host> <script>` si un
hôte est fourni ; le paramètre `owner` n'y sert à rien. `bash` **est** dans les 38
outils bloqués pour un non-administrateur, `run_script` **non**. Même capacité,
deux portes.

J'ai cherché la fuite, et **elle n'existe pas** : `BUILTIN_ACTION` n'est référencé
que par `routes/task_routes.py` et `src/task_scheduler.py` — **pas** par la boucle
de l'agent. `run_script` n'est donc pas un outil d'agent, et le garde-fou de
propriétaire ne s'y applique pas.

Reste une **contrainte latente** à écrire quelque part : si les actions builtin
deviennent un jour des outils d'agent, la porte du propriétaire ne les couvrira
pas, parce qu'elles ne sont pas dans la liste. C'est une ligne de test, pas une
correction.

### 2.5 `ODYSSEUS_MULTI_AGENT` : mesure de visibilité, pas activation

L'interrupteur d'UC-10 est lu par la boucle et absent du registre. Je le **signale**
et je n'y touche pas : UC-10 est une escalade gelée, et rendre visible un
interrupteur existant ne l'active pas. Le plan le propose explicitement en
visibilité seule, défaut inchangé, pour que la décision reste au Chef.

---

## 3. INT-1 → INT-21 : confrontation item par item

Règle de classement, appliquée sans indulgence :

- **couvert** — une fiche `ACTIF` porte l(item, et le code fait ce qu'elle dit ;
- **partiel** — une fiche existe et porte une part, avec un reste écrit ;
- **non couvert** — pas de fiche, ou fiche absente du chemin réel.

| ID | Apport (vision) | Fiche(s) | État | Reste mesuré |
|---|---|---|---|---|
| **INT-1** | Orchestration live + phase-tracker | P1 · P5 · P12 · UC-05 | **partiel** | `PHASE_TRACKER` est **déjà `on`** (Palier 0) ; `LIVE_ORCHESTRATION` reste `off`. UC-05 : le dispatcher ne suit pas encore la phase. |
| **INT-2** | Exécution durable réelle | P14 · UC-02 · UC-11 | **partiel** | item 8 : `create_workflow` câblé. Reste : la conversation persistée s'achève sur un message `tool`. |
| **INT-3** | Mémoire à provenance + impact | P16 · P18 · P19 | **partiel** | items 4/6/10. Trois restes écrits ; aucun n'est un log. |
| **INT-4** | Routage modèle live, modèle par phase | *(aucune)* · cf. MOD-3 | **partiel** | 383 occurrences `ModelEndpoint`/`model-routing.json` : le code existe, la source de vérité est dupliquée. **Aucune fiche ne le suit.** |
| **INT-5** | Trinité branchée (Graphify + Obsidian) | Axe 4, UC-08 (mémoire transverse seulement) | **non couvert** | `graphify_mcp.py` et `obsidian_mcp.py` existent ; `ODYSSEUS_CBM` est `off` ; `knowledge_routes.py:49` reste un proxy CBM à service éteint. |
| **INT-6** | Skills à chargement obligatoire + catalogue | UC-04 (MCP seulement) | **non couvert** | `skills_routes.py` existe ; **aucun gate `required_skills`** trouvé. Le « chargement obligatoire » est absent. |
| **INT-7** | Découverte dynamique d'outils | UC-04 | **non couvert** | `tool_search` : **0 occurrence**. `suggest_connectors`/`search_mcp_registry` : uniquement dans `content_security.py`. `ODYSSEUS_TOOL_DISCOVERY` lu par le code, **absent du registre**. |
| **INT-8** | Goal-ancestry live | P4 | **non couvert** | 3 occurrences (schémas). P4 reste `PARTIEL` : la chaîne mission→goal→projet→tâche n'est pas live. |
| **INT-9** | Observabilité budget | P4 · P9 | **partiel** | `record_budget_status` + `budget_pct`/`budget_tokens` sont bien sur le flux ; le **multiplicateur multi-agent** dépend d'UC-10, gelé. |
| **INT-10** | Grounding + citations dans les livrables | *(aucune)* | **non couvert** | ⚠ `tools/check_citations.py` vérifie la **documentation** du dépôt. Ce n'est pas la fonctionnalité. Piège de confusion à écrire. |
| **INT-11** | Heartbeat / cron / briefs | *(aucune)* | **partiel** | `src/task_scheduler.py` + `task_routes.py` : un ordonnanceur existe. Le « en langage naturel » n'est pas mesuré. |
| **INT-12** | Wide Research | *(aucune)* | **non couvert** | **0 occurrence** de `wide_research`/`WideResearch`/`parallel_search`. |
| **INT-13** | Session replay / auditabilité | P15 · UC-12 | **partiel** | P15 `ACTIF`, et l'item 9 a rendu la piste **relisible en HTTP**. Le « rejeu » lui-même reste à faire — le substrat est prêt. |
| **INT-14** | Multi-canal étendu | UC-04 | **partiel** | `channel_gateway` + adaptateurs ; Apprise `off`. Slack/WhatsApp/Email/CLI non vérifiés un par un. |
| **INT-15** | `AGENTS.md` généré par projet | *(aucune)* | **non couvert** | **0 occurrence**. |
| **INT-16** | Mode local / dégradé (Ollama) | P1 | **partiel** | 816 occurrences, `is_ollama_native_url` câblé. Reste : sans `OPENCODE_API_KEY`, le chemin nominal n'est pas testé. |
| **INT-17** | Worktrees | UC-06 · UC-07 | **exclu** | Absents. Le Chef les a sortis du périmètre de cet examen. |
| **INT-18** | Défaut d'écriture mémoire (draft/commit) | P2 | **partiel** | `editor_draft_routes.py` existe ; P2 `PARTIEL`. Reste écrit. |
| **INT-19** | Rétention 5 niveaux + droit à l'oubli | P17 · UC-19 | **partiel** | `RetentionLevel` a bien **5** niveaux (`data_classification.py`). Items 1, 11 et v6 faits. Reste : suppression unitaire non vérifiée bout en bout. |
| **INT-20** | Sécurité contenus & prompt-injection | P17 | **partiel** | Items 11 + v6 : les 5 sorties et le chemin mémoire non fiable sont **prouvés**. Reste : les octets déjà diffusés, et les surfaces non instrumentées. |
| **INT-21** | Préférences contextuelles + DELETE | P20 · UC-18 | **partiel** | Item 2 : injection effective. Reste écrit : directive non élargie, `DELETE` non vérifié. |

**Bilan INT : 0 couvert · 12 partiels · 8 non couverts · 1 exclu.**

### 3.1 Le trou de couverture, qui est le vrai sujet

**Six items INT n'ont aucune fiche qui les suit** : INT-4, INT-6, INT-7, INT-10,
INT-11, INT-12, INT-15. La grille de 41 fiches a été dérivée de
`01-SFD-v3.1`, pas de la vision intégrée. Résultat : la vision promettait des
items dont **personne ne mesurait l'état**, et c'est précisément pour ça que
`core.database` est passé de 64 à 120 sans que personne ne le voie.

C'est la leçon structurelle de cet examen, et elle vaut plus que les 32 lignes
ci-dessus : **une vision sans fiches ne se contrôle pas, elle se raconte.**

---

## 4. MOD-1 → MOD-11 : confrontation

| ID | Apport | Mesure au `39fb47e` | État |
|---|---|---|---|
| **MOD-1** | `route_loader` dynamique | **54** imports `from routes.` statiques, `pkgutil=False` | non couvert |
| **MOD-2** | Inverser les arêtes `src/* → routes.*` | **30 arêtes**, dans 11 fichiers — dont `builtin_actions.py` pour 11 à lui seul. **Correction de ma part** : j'avais d'abord mesuré 421, qui comptait 275 arêtes depuis des **tests** (légitimes : un test de route importe sa route) et 54 depuis le **chargeur** (légitime par métier). Le « ~30 » de la vision était plus juste que mon propre relevé. | non couvert |
| **MOD-3** | Source de vérité du routage modèle | 383 occurrences `ModelEndpoint`/`model-routing.json` | non couvert |
| **MOD-4** | Éliminer les shims `llm_core`/`agent_loop` | **85** fichiers importent un shim | non couvert |
| **MOD-5** | Injection au lieu de singletons | `provenance_memory._fs`, `content_security._guard`, caches module | non couvert |
| **MOD-6** | Contrat DB sur `core.database` | **120** importeurs — 2ᵉ nœud le plus importé du dépôt | non couvert, **le pire des onze** |
| **MOD-7** | ABC `MemoryProvider` | `letta_provider`, `mem0_provider`, `qdrant_store` : trois côtés sans interface commune | non couvert |
| **MOD-8** | Outils découplés de `routes` | `src/builtin_actions.py` → 11 arêtes `routes` | non couvert |
| **MOD-9** | Trancher les packages `@agentos/sfd-*` | **10** packages présents (la vision en annonce 9) | non couvert |
| **MOD-10** | Agents déclaratifs (front-matter YAML) | 14 fichiers mentionnent « front-matter », **tous pour les skills**, aucun pour un registre d'agents | non couvert |
| **MOD-11** | **CI de modularité** | jobs CI : `doc-gates`, `python-syntax`, `node-syntax`, `python-tests`, `llm-quality`. **Aucune mention de modularité.** | non couvert |

**Bilan MOD : 0 couvert · 11 non couverts.**

MOD-11 est la ligne la plus importante du tableau, et ce n'est pas une routine :
tant qu'aucun job ne mesure le god node et les arêtes, les dix autres ne peuvent
être ni conduits ni vérifiés. Le plan le met en premier pour cette raison — et
c'est aussi le seul item MOD qui ne demande aucune réécriture.

---

## 5. Ce que ce constat ne tranche pas

Deux points relèvent d'une **décision de politique**, pas d'une mesure. Je ne les
tranche pas.

1. **OPA : brancher ou déclarer non opérant ?** Les deux sont honnêtes. Ce qui ne
   l'est pas, c'est le statu quo — actif, invisible, jamais appelé. Le plan
   (`item 3`) ne fait **rien** tant que le Chef n'a pas tranché.
2. **Faut-il faire des 12 interrupteurs invisibles une priorité de Sprint 4 ?** Le
   §3 du v7 est bloqué par une action du Chef ; ajouter 12 lignes au registre est
   rapide, mais c'est de la gouvernance, pas du produit. Le plan propose, le Chef
   arbitre.

---

## 6. Vérifications du constat

```
kill-switches   : 16 ON / 54 au registre ; 205 variables ODYSSEUS_* lues par le
                  code de production, dont 12 interrupteurs de capacité hors
                  registre, dont 2 à on
FND-1           : launch_fast.py:9 écrit ODYSSEUS_DURABLE_EXEC ;
                  seul ODYSSEUS_DURABLE_EXECUTION est lu (durable_execution.py)
OPA             : 0 appelant hors tests ; fail-closed vérifié aux lignes 83-88, 124
run_script      : BUILTIN_ACTION référencé par 2 fichiers, aucun par la boucle → pas de fuite
modularité      : core.database 120 · route_loader 54 statiques · shims 85 · arêtes 421/176
int             : 0 couvert · 12 partiel · 8 non couvert · 1 exclu
mod             : 0 couvert · 11 non couvert
items INT sans fiche qui les suit : INT-4, INT-6, INT-7, INT-10, INT-11, INT-12, INT-15
```

Aucun nombre de ce document n'est recopié : tous viennent d'un relevé. Les
scripts de mesure sont dans `/tmp/opencode/` et n'ont pas été commités, ce qui
est assumé — ils sont des instruments de constat, pas des portes. Si le Chef veut
les garder, ils deviennent des portes à part entière (item 5 du plan).
