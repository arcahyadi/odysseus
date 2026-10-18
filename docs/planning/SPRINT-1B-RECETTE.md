# Sprint 1b — Recette : le score a baissé, donc la mesure est juste

> Date : 2026-09-26 · Branche `feat/inventaire-global-v1` · Commits `8c2fc89` → `f034da5` (15 commits)
> Mesure : **4 794 tests collectés → 4 792 PASS · 2 skipped · 0 FAILED · 0 error** (entrée : 4 742 PASS)
> Lint : **3 707** diagnostics contre une base mesurée de **3 708** (extrait `git archive HEAD~2` dans un répertoire temporaire) — soit **−1**.

## Ce que le sprint a fait

FND-4 option C, **Palier 0** : les 14 kill-switchs P0 basculés de `off` à `on`. Puis l'honnêteté du cockpit, puis la re-dérivation des 41 statuts depuis le code.

| | Avant | Après |
|---|---:|---:|
| DORMANT | 5 | **1** |
| ACTIF | 12 | **10** |
| PARTIEL | 22 | **28** |
| Couverture | ~62 % | **~60 %** |
| Activation (live) | ~29 % | **~24 %** |

## Le résultat principal est une baisse

Le Palier 0 devait faire monter le score. Il l'a fait baisser. C'est le sujet du sprint, pas un échec.

Le motif est unique et il explique les 28 PARTIEL : **le module est allumé, et son résultat est jeté.**

| Principe | Switch | Ce que le code fait du résultat |
|---|---|---|
| P17 | `DATA_CLASSIFICATION=on` | classe et persiste, puis la branche `PROTECTED` ne fait que `logger.info` — le message est stocké quand même |
| P20 | `PREFERENCES=on` | résout `language`/`tone`/`format`, puis les logge — jamais injectés au prompt |
| P22 | `OUTPUT_ROUTER=on` | `route()` est **pur** (aucun effet de bord), la décision est loggée, aucun fichier écrit |
| P19 | `MEMORY_IMPACT=on` | appelé avec `hypothetical_response=""` ⇒ court-circuit à `0.0` ⇒ `should_store` toujours `False` |
| P16 | `PROVENANCE_MEMORY=on` | `add_observed` renvoie `(False, "Domain file does not exist")` : `topics/agent-output.md` n'est jamais créé ⇒ no-op garanti |
| P5 | `PROGRESSIVE_DISCLOSURE=on` | calcule un résumé puis le logge ; `allowed_tools` n'entre dans aucun schéma d'outil |

Le switch passing de `off` à `on` ne prouve donc **rien** sur le module. Il prouve seulement qu'un `if` est devenu vrai.

## Trois découvertes qui n'étaient pas prévues

### 1. Une suite verte a exécuté un `git reset --hard` réel

`AUTOEVAL` passé à `on` par défaut, plus un test qui fournit `verifier_reasons` : la dérive est classée `HIGH`, la décision `REVERT` est prise, et l'action est exécutée pour de vrai. **14 basculements de kill-switch non commités ont été effacés.**

> **Règle permanente : toujours commiter avant de lancer la suite.** Le commit `8c2fc89` ne portait volontairement que les basculements, précisément parce que le commit « immédiat » était devenu nécessaire.

D'où le correctif suivant (`ed1eea5`, puis `f0cf0f6` pour le chemin **live**) : la décision et l'action sont séparées. AUTOEVAL peut **décider** un revert — c'est tracé et retourné — mais seul `ODYSSEUS_AUTOEVAL_ALLOW_RESET` (**OFF**) autorise le `reset`. Un vrai reset détruit le travail non commité de l'arbre courant, dans un dépôt où l'agent tourne.

Le chemin live avait un trou réel et atteignable : écriture par le harnais de test → dérive `HIGH` → revert → arbre de travail du serveur wiped.

### 2. Un bloc mort depuis toujours, et `ruff` le signalait depuis toujours

Le bloc M6.8 (divulgation progressive) appelait `get_disclosure_summary(phase)` avec un **nom libre non défini**. Le `NameError` était absorbé par un `except` générique qui loggait en `debug` — donc invisible. **Le bloc n'avait jamais été exécuté une seule fois.**

Deux raisons que personne n'ait rien vu :
- le module n'avait **aucun test** (28 ont été ajoutés) ;
- `ruff` signalait `F821 Undefined name 'phase'` depuis le début, dans une base de 3 708 diagnostics où une ligne de plus passait inaperçue.

> C'est le triplet qui laisse un défaut installer : un module sans test, une erreur masquée par un `except` générique, et un linter dont la sortie n'est pas lue parce que la base est trop haute pour être regardée.

### 3. Le registre des kill-switchs mentait sur **la colonne des lecteurs**

En regénérant la table de traçabilité depuis le registre, la colonne « Lecteur » a montré ce que rien ne vérifrait : **24 descripteurs sur 54 pointaient vers un fichier sans rapport avec leur switch.** Deux fichiers seulement servaient de source pour 24 switchs différents — `checkpoint_tracker.py:39` (10 fois) et `memory_impact.py:23` (14 fois). C'est du copier-coller.

Les tests d'audit vérifiaient `wired` (« un lecteur existe-t-il ? ») et `default` (« le code va-t-il appliquer cette valeur ? »). **Personne ne vérifiait `source`** (« le fichier cité est-il le bon ? ») — troisième question, non posée.

## Le pattern d'orchestration

**Une valeur documentée à la main n'a aucune raison d'être encore vraie.** Les défauts de kill-switch étaient recopiés dans la documentation ; le Palier 0 les a rendu faux **en une ligne de code**, et il a fallu les rattraper un par un.

La réponse n'est pas « faire plus attention » : c'est de **générer**. `tools/gen_killswitch_tables.py` lit `read_states()` à chaque exécution et réécrit les tables. La cartographie module SFD → switch reste déclarée (c'est un choix d'édition), les **valeurs** ne sont plus écrites. `--check` sort en 1 : le contrôle devient un job de CI, ce qui était le point 2 du §8 de `TRACEABILITY.md`, écrit comme un souhait depuis des mois.

C'est aussi ce qui a fait apparaître la découverte n° 3 : **on ne constate un mensonge qu'en générant la valeur depuis la source.**

## Near-misses à retenir

| Piège | Conséquence | Règle |
|---|---|---|
| Un test fournit `verifier_reasons` alors qu'`AUTOEVAL` est `on` | `git reset --hard` réel, 14 flips non commités perdus | commiter avant la suite ; l'action destructive exige un second switch |
| Éditer le registre par un regex à span `\{\s*"name":.*?"env_var": "X",.*?\n    \},` avec `re.S` | le span chevauche plusieurs blocs ⇒ `.replace('"default": "on"', …)` a basculé **6 P0 à `off`** et en a raté 2 autres | splitter sur le délimiteur de ligne `    {` … `    },` et itérer avec `enumerate`, **jamais** `.index()` |
| `s.index("[", start)` pour localiser le corps de `_SWITCHES` | `[` = celui de l'annotation `list[dict[str, Any]]`, pas celui de la liste ⇒ fichier tronqué (`NameError: name '_SWITCHES' is not defined`) | utiliser la chaîne d'en-tête complète et décaler de `len(HEADER) - 1` |
| Croire le `except Exception` qui avale les erreurs « défensif » | il a rendu mort un bloc que tout le monde croyait actif | un `except` générique sur un chemin dont on attend un effet est un bug déguisé |

## Leçon de mesure

**« Codé » n'est pas « actif », et « activé » n'est pas « agissant ».** Trois niveaux, et le projet en maîtrisait un seul :

1. le module existe ;
2. le switch est `on` ;
3. le résultat du module change quelque chose.

Le Palier 0 a fait monter le projet du niveau 1 au niveau 2. La mesure honnête montre qu'on est encore loin du niveau 3 — sur 28 exigences. Ce n'est pas un constat \$ sur le code : c'est un inventaire de câblage, et chaque ligne a un geste unique et bien délimité (`02-PRINCIPES-UC.md` §5).

Les 2 ACTIF perdus sont de la même nature : **UC-01** attend une `OPENCODE_API_KEY` absente de `.env` (le projet utilise OpenCode Zen) — le flux nominal est inatteignable en l'état ; **UC-05** est écrasé parce que `on_round_start` réimpose `BUILD` sur la phase posée par l'API.

## Ce que « 100 % vert » ne prouve toujours pas

inchangé, et rappelé : ChromaDB, Mem0, les appels LLM et le moteur Docker sont injoignables. Les chemins **dégradés** sont testés, les chemins **nominaux** non. `OPENCODE_API_KEY` manque toujours. Le vert est **local**.

S'y ajoute le fait que les tests ne prouvent que ce qu'on a pensé à écrire. Le bloc M6.8 avait zéro test et était mort ; 28 tests et une garde statique ont été ajoutés, dont une qui interdit à nouveau qu'un nom libre soit passé à `get_disclosure_summary` — **même si la configuration de lint était relâchée**.

## Suite

Le backlog de câblage n'est pas un chantier à inventer sur-le-champ : il est écrit, principe par principe, dans `02-PRINCIPES-UC.md` §5. Il conditionne toute montée de la colonne *Activation* ; activer de nouveaux switchs n'en fera plus monter aucune.
