# MOD-9 — Dossier des 10 paquets `@agentos/sfd-*`

> Date : 2026-09-28 · Mesuré au `2c59704` · Déclencheur : v11 §4.1
> **Aucune décision n'est prise ici.** Brancher = activation au-delà du Palier 0 ;
> archiver = retirer une partie de la SFD. Les deux appartiennent au Chef
> (règle v1 §4 : abandon d'un plugin npm sans arbitrage MOD-9).

## 1. Ce que la mesure a établi, avant toute ligne de dossier

| Fait mesuré | Comment |
|---|---|
| **10 paquets**, `v0.1.0`, **tous `private: true`** | `package.json` parsé — un paquet `private` n'est **pas publié sur npm** : aucun ne l'est, donc aucun n'a d'audience externe à casser |
| **10 fichiers `.ts`, 1 368 lignes** au total | comptage sur disque |
| **9 n'ont aucune référence résolue** | valeur ou clé JSON, import TS/JS, import Python — jamais une mention de document |
| **1 seul est référencé** : `sfd-eventbus`, via `opencode.json:5` (tableau `plugin`) | idem |
| **9 des 10 n'exportent qu'une chose** : `plugin` | lecture des exports dans les `.ts` |
| **1 seul est une vraie bibliothèque** : `sfd-visual`, 648 lignes, 11 exports hors `plugin` | idem |
| **8 des 9 non tranchés ont un équivalent Python `on` et `wired=True`** | registre des interrupteurs, croisé avec la grille |

**Le fait central :** ces paquets ne sont pas des briques en attente d'être
branchées. Ce sont des **doublons** de systèmes Python déjà vivants au Palier 0.
Brancher la plupart ne ajouterait aucune capacité — il créerait deux systèmes
pour un même travail, ce que le principe « structure > autonomie » contredit
autant que la règle « chaque chantier réversible seul » l'exige.

## 2. Le dossier, un paquet par ligne

| Paquet | Rôle (d'après son `package.json`) | ⤵ | Exporté | Privé / npm | Référence résolue | Coût de branchement | Recommandation | Raison |
|---|---|---|---|---|---|---|---|---|
| `sfd-classify` | Classification d'intention, routage d'événements | 62 | `plugin` | privé / **non publié** | **aucune** | **faible** — 1 ligne dans `opencode.json` + vérifier qu'il ne double pas `ODYSSEUS_DATA_CLASSIFICATION` (`on`, `wired`) | **archiver** | L'équivalent Python est `on` et câblé. Brancher = deux classifieurs pour un rôle. |
| `sfd-discovery` | Registre de services, sondage d'endpoints | 77 | `plugin` | privé / **non publié** | **aucune** | **moyen** — il n'existe pas d'équivalent actif : `ODYSSEUS_TOOL_DISCOVERY` est `off`, et `tool_search` fait **0 occurrence** (INT-7) | **à instruire en priorité** | Le seul paquet qui ne **duplique** rien : il couvre une promesse de la vision (INT-7) que le code Python ne tient pas. C'est le seul candidat au « brancher » qui ajoute. |
| `sfd-durable` | Exécution durable, idempotence, saga | 67 | `plugin` | privé / **non publié** | **aucune** | faible, mais **piège** | **archiver** | `ODYSSEUS_DURABLE_EXECUTION` est `on` et câblé. Le paquet porte une compensation de saga que le port Python **n'a pas** (§1 du v11) : l'écart de code est réel, mais brancher le plugin ne rendrait pas la compensation exécutable côté Python. |
| `sfd-eventbus` | Bus central, 15 familles, 62 événements | 145 | `plugin` | privé / **non publié** | **`opencode.json:5`** | **nul — déjà branché** | **arbitrage prioritaire, pas de branchement** | C'est le seul branché, et il tourne **en plus** de `ODYSSEUS_UNIFIED_TOKENS` (`on`, `wired`). Deux bus pour un rôle, l'un d'eux déjà actif. À trancher avant tout le reste : ce n'est pas un chantier, c'est un état à confirmer. |
| `sfd-heartbeat` | Santé, disponibilité, alertes | 80 | `plugin` | privé / **non publié** | **aucune** | faible | **archiver** | Les alertes de dérive existent et sont câblées (`agent_loop.py:4530`, UC-09 ACTIF). Doublon. |
| `sfd-memory` | Mémoire vectorielle avec provenance | 64 | `plugin` | privé / **non publié** | **aucune** | faible | **archiver** | `ODYSSEUS_PROVENANCE_MEMORY` est `on` et câblé, avec écriture atomique et assainissement d'injections. |
| `sfd-phase` | Cycle de vie des phases, transitions, rollback | 77 | `plugin` | privé / **non publié** | **aucune** | **piège** | **archiver** | `config/phase-lock.yaml` et `ODYSSEUS_PHASE_TRACKER` sont `on`. Le plugin ajoute un **deuxième** gestionnaire de phases à côté du phase-lock. |
| `sfd-prefs` | Préférences, résolution en couches | 71 | `plugin` | privé / **non publié** | **aucune** | faible | **archiver** | `ODYSSEUS_PREFERENCES` est `on`, et `src/preferences.py` implémente déjà la résolution par priorité. |
| `sfd-security` | Politique de contenu, détection d'injection | 77 | `plugin` | privé / **non publié** | **aucune** | faible | **archiver** | `ODYSSEUS_CONTENT_SECURITY` est `on` et câblé, avec garde de contenu. |
| `sfd-visual` | Diagrammes, rapports, maquettes (Kroki/SVG/PNG/HTML) | **648** | **12** | privé / **non publié** | **aucune** | **moyen** — 11 exports à adapter, chevauchement avec `src/output_router.py` | **à instruire** | Le seul **vrai** contenu : 648 lignes, 12 exports, un moteur de rendu que le Python n'a pas. Mais `ODYSSEUS_OUTPUT_ROUTER` est `on` : brancher exige de décider quel moteur est faitiel. |

## 3. Ce que le dossier ne tranche pas, et pourquoi

* **Aucun paquet n'est supprimé.** Le mot « archiver » signifie déplacer vers
  `archive/`, réversible, pas effacer.  : `sfd-visual` et `sfd-discovery` portent des
  choses que le Python n'a pas.
* **Le coût est une estimation, et sa base est dite** : « faible » =
  1 export, 62–80 lignes, adaptable en une ligne de configuration ;
  « moyen » = bibliothèque multi-exports, ou Logs manquants chevauchement avec un système actif. Ce n'est pas une mesure, et il ne le présente pas comme telle.
* **Rien n'est débranché** avant arbitrage. `sfd-eventbus` est dans
  `opencode.json` aujourd'hui ; le retirer serait un changement de comportement
  que personne n'a demandé.

## 4. L'arbitrage, en quatre questions

1. **Le doublon est-il un accident ou une décision ?** Sept paquets doublent un
   système `on`. Si la SFD visait le TypeScript et que le Python a pris sa
   place, l'arbitrage est « archiver ». Si l'inverse, c'est l'inverse.
2. **`sfd-eventbus` tourne-t-il réellement en double ?** C'est le seul état à
   confirmer avant toute autre décision : il est déclaré et `UNIFIED_TOKENS`
   est `on`.
3. **`sfd-discovery` et `sfd-visual` comblent-ils des trous mesurés ?** Le
   premier comble INT-7 (`tool_search` = 0 occurrence). Le second est le seul
   moteur de rendu du dépôt.
4. **Qui porte la règle « un seul système par rôle » ?** Elle n'est écrite
   nulle part. C'est elle qui décidera de 9 lignes sur 10.

## 5. Effet sur la grandeur gelée

`paquets_sfd_non_tranches` est gelé à **9**. Brancher un paquet le fait
descendre ; archiver aussi. Les deux mouvements sont des réussites du chantier,
et le seuil devra alors être **relevé à la baisse à la main**, avec la
justification — c'est le seul moyen de prouver que le chantier a avancé.
