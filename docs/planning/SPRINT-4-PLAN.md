# Sprint 4 — Plan : la vision se contrôle (gouvernance et mesure)

> Date : 2026-09-27 · Branche `feat/inventaire-global-v1` · Né de `CONSTAT-VISION-INTEGRATION.md`
> Déclencheur : examen de `../VISION-INTEGRATION.md` contre les 41 fiches de
> `../traceability/02-PRINCIPES-UC.md` au commit `39fb47e`
> Baseline : **6/22 P ACTIF · 7/19 UC ACTIF** — 5 002 PASS · lint 3708/3708

## 1. Le constat, en une phrase

**Le Palier 0 a allumé 16 modules ; la vision en compte 21 qui n'ont aucune fiche
qui les suit, et le tableau censé dire ce qui est actif ne le peut plus.**

Le Sprint 3 a rendu des contrôles **exercés**. Le même travail reste à faire sur un
objet que personne n'a mesuré : **laTruth de ce qui est allumé**. Le tableau des
kill-switchs couvre 54 entrées, le code en lit 205 variables `ODYSSEUS_*`, dont
**12 interrupteurs de capacité absents du registre, dont 2 actifs par défaut**.
Et la modularité n'a pas stagné : `core.database` est passé de 64 à **120**
importeurs sans que personne ne le voie.

| Niveau | Maîtrisé | Preuve |
|---|---|---|
| 1 — le module existe | ✅ 41/41 fiches | `02-PRINCIPES-UC.md` |
| 2 — le switch est `on` et **visible** | ⚠️ **16/28** | 12 interrupteurs hors registre, 2 à `on` |
| 3 — le résultat agit | ✅ 13/41 `ACTIF` | §4 du même document |
| 4 — la vision est **suivie** | ❌ **7 items sans fiche** | `CONSTAT-VISION-INTEGRATION.md` §3.1 |

## 2. Périmètre — 7 items, un geste chacun

Aucun item n'est une réécriture. Aucun n'active un kill-switch au-delà du
Palier 0. Aucun ne touche P8, P12, UC-10, `AUTOEVAL_ALLOW_RESET`, ni UC-06/07.

| # | Objet | Le problème est… | Geste | Preuve de fin (comportementale) |
|---|---|---|---|---|
| 1 | **FND-1** | **3** variables que rien ne lit, pas une : `ODYSSEUS_DURABLE_EXEC`, `ODYSSEUS_THOUGHT_BUS`, `MCP_CONNECT_TIMEOUT` | renommer la première (nom réel `_EXECUTION`), **supprimer** les deux autres (aucun nom réel n'existe) | un test échoue pour **toute** variable du lanceur sans lecteur, donc pour la forme du défaut — 7 mutations |
| 2 | **Registre** | **11** capacités (la 12ᵉ a perdu son lecteur à l'item 1) ; 2 à `on` | les inscrire (défauts **inchangés**), et distinguer les 29 variables de configuration qui n'ont pas leur place dans un registre d'interrupteurs | `GET`/tableau : `ODYSSEUS_OPA` et `ODYSSEUS_OTEL` y figurent avec leur défaut ; un test échoue si une variable lue par un fichier de production et **nommée comme un interrupteur** est absente |
| 3 | **OPA** | même chose, **exécuté via l'item 2** selon la décision v8 | coupé par défaut **dans le CODE** — la moitié de `wired=False` refusée, car `wired` signifie « un lecteur existe » et il en existe un | un test échoue si le code le remet à `on` ; un autre échoue si le registre et le code divergent |
| 4 | **MOD-11** | rien ne mesurait : `core.database` est passé de 64 à 120 sans qu'une porte le voie | un job `modularity` : god node ≤ seuil, arêtes `src/*→routes.*` ≤ seuil, et `pkgutil` dans `route_loader` | le job **échoue** quand on ajoute une arête `src→routes` ; et il passe sur l'état actuel (donc les seuils sont calibrés, pas arbitraires) |
| 5 | **Instrumentation** | les relevés du constat vivent dans `/tmp`, donc personne ne peut les rejouer | une porte `tools/check_governance.py` : compte les interrupteurs lus-hors-registre, les arêtes, les god nodes, et **écrit le compte dans `TRACEABILITY.md`** | la porte **échoue** si un interrupteur nommé est ajouté hors registre ; et le compte est **généré**, jamais recopié |
| 6 | **INT-10** | `tools/check_citations.py` vérifie la **doc** du dépôt — et peut être lu comme la fonctionnalité « grounding » d'INT-10, qui n'existe pas | une ligne dans la fiche et dans le constat : ce que l'outil vérifie, et ce qu'il ne vérifie pas | une assertion sur le contenu de l'outil : il doit produire `0` citation hors `docs/` — donc **il ne peut pas** prétendre vérifier les livrables |
| 7 | **Garde de propriété** | `run_script`/`ssh_command` ont la capacité de `bash` sans être dans la liste bloquée — **inoffensif aujourd'hui** (ce ne sont pas des outils d'agent) | un test qui **échoue** si une action builtin devient un outil d'agent sans être dans `NON_ADMIN_BLOCKED_TOOLS` | le test passe aujourd'hui ; il tombe si `BUILTIN_ACTION` apparaît dans la boucle. Une contrainte écrite, pas une correction |

## 3. Ce que ce plan ne fait pas, et pourquoi

| Ce qui n'est pas fait | Raison |
|---|---|
| Activer `LIVE_ORCHESTRATION` (INT-1) | Au-delà du Palier 0 — interdit par le feu vert, et UC-05 a un reste ouvert |
| Exécuter INT-5, INT-6, INT-7, INT-8, INT-12, INT-15 | Non couverts, mais ce sont des **fonctionnalités**, pas du câblage. Elles méritent leur propre plan, validé après ce constat |
| Traiter UC-06/UC-07 (worktrees) | Sortis du périmètre par le Chef |
| Toucher P8, P12, UC-10, `AUTOEVAL_ALLOW_RESET` | Escalades gelées. L'item 2 rend `ODYSSEUS_MULTI_AGENT` **visible**, défaut inchangé : rendre visible n'est pas activer, et la décision reste au Chef |
| Démarrer MOD-1 → MOD-10 | MOD-11 d'abord (item 4) : sans mesure, ces dix chantiers ne sont pas conduisables. MOD-6 (`core.database`, 120 importeurs) est le pire, et vient en dernier |
| Publier la CI `doc-gates` | Bloqué par la portée OAuth — rappelé dans chaque rapport |

## 4. Le lien entre ce plan et le précédent

Le Sprint 3 a fait passer le niveau 3 de 10 à 13. Ce plan n'attend **aucun**
changement de ce chiffre : les sept items sont de la gouvernance et de la mesure,
par construction ils ne promeuvent aucun principe. Le plan le dit d'entrée plutôt
que de laisser croire à une courbe.

Ce qu'ils produisent, en revanche, est mesurable : **12 interrupteurs visibles au
lieu de 0**, **une CI qui empêche la dégradation de la modularité au lieu de la
constater six mois plus tard**, et **7 items de la vision qui cessent d'être des
promesses non mesurées** — en les inscrivant dans la grille, même en `non couvert`.

## 5. Vérifications avant clôture du plan

```
tableau registre   : 12 → 28 entrées, 2 défauts `on` redeclarés
FND-1              : le nom écrit par le lanceur est celui qui est lu
CI                 : job `modularity` présent, rouge sur arête ajoutée, vert aujourd'hui
porte gouvernance : échoue sur un interrupteur nommé ajouté hors registre
suite              : ≥ 5 002, 0 échec
lint               : ≤ 3 708
citations          : 0 hors fichier
gen_killswitch     : vert, colonnes `source` vérifiées
```

Tant que l'item 3 n'est pas tranché, il reste **bloqué** et ne compte pas dans la
clôture du sprint. C'est volontaire : un plan où rien n'est bloqué est un plan qui
promet ce qu'il ne peut pas tenir.
