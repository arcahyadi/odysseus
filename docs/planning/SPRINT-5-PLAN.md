# Sprint 5 — Plan : les dix chantiers MOD, dans l'ordre où ils se débloquent

> Date : 2026-09-28 · Branche `feat/inventaire-global-v1` · Né de `CONSTAT-VISION-INTEGRATION.md` §4
> Déclencheur : feu vert v9 §3.2 — « produire un plan borné avant d'écrire du code »
> **Aucun code n'a été écrit pour ce plan.** Il est soumis, il n'est pas entamé.

## 0. Confirmations demandées par le v11 (statut explicite, règle v6 §5)

| Correction du v10 | Statut au `2c59704` | Vérifiable par |
|---|---|---|
| `paquets_sfd_non_tranches` = **9**, pas 10 | **FAIT** | `tools/check_modularity.py` : 9 paquets sans référence résolue, 1 branché (`opencode.json:5`) |
| MOD-4 = **36 fichiers / 78 points d'import** | **FAIT** | seuil `imports_de_shim` = 78, par AST, hors tests et hors `archive/` |
| **MOD-11bis retiré** | **FAIT** | l'item est rayé du tableau §2 ; `packages/` contient 13 `.ts` et 0 `.py` |
| **MOD-7 reformulé** | **FAIT** | `fournisseurs_hors_interface` = 0 : `MemoryProvider` est déjà une ABC, 2 fournisseurs l'implémentent |
| Seuils de modularité **3 → 8** | **FAIT** | `tools/check_modularity.py --explain` : 8 grandeurs, toutes à leur valeur mesurée |

**Item proposé, non lancé** (v11 §2 — les 32 fiches booléennes) :

| # | Geste | Preuve de fin comportementale | Dépend de | Statut |
|---|---|---|---|---|
| **P1** | Résoudre les **32 fiches booléennes** de `sfd_audit.py` : pour chacune, localiser le module réel par résolution structurelle, **vérifier l'affirmation elle-même**, puis nommer la preuve **ou** passer la fiche à `False` avec sa raison. Un passage à `False` est un résultat valide, pas un échec. | **0 booléen sans preuve nommée ou sans statut `False` motivé** — et `verifier()` ne rapporte plus aucun `SANS_PREUVE`. | après §1 du v11 et après l'arbitrage MOD-9 | **PROPOSÉ — pas lancé** |

Le v11 est explicite : ce chantier passe **après** le dossier MOD-9. Il est
écrit ici pour qu'il ne se perde pas, pas pour commencer.

## 1. Ce que MOD-11 a changé

Dix chantiers de modularité étaient listés depuis le v1 sans qu'aucun ne soit
mesuré. Le Sprint 4 item 4 a posé trois seuils **au niveau actuel** :

| Seuil | Avant | Après | Chantier |
|---|---:|---:|---|
| god node `core.database` | 120 | 120 | MOD-6 |
| arêtes `src/* → routes.*` | 30 | 30 | MOD-2 |
| imports statiques de `route_loader` | 54 | 54 | MOD-1 |

**Résultat du point demandé par le v10 avant de commencer (fait) : les trois
seuils ne suffisaient pas.** Ils couvrent quatre chantiers (MOD-1, MOD-2, MOD-6,
MOD-8) ; **six chantiers agissaient sur une grandeur que rien ne surveille** —
donc six chantiers pouvaient dériver en silence, ce qui est exactement ce que le
point devait empêcher. Cinq seuils ont donc été ajoutés, à la valeur mesurée :

| Seuil ajouté | Valeur | Chantier |
|---|---:|---|
| `paquets_sfd_non_tranches` | 9 | MOD-9 |
| `globals_dans_src` | 46 | MOD-5 |
| `fournisseurs_hors_interface` | 0 | MOD-7 |
| `modules_resolution_modele` | 12 | MOD-3 |
| `imports_de_shim` | 78 | MOD-4 |

Les dix chantiers sont désormais couverts. Un seuil posé **au-dessus** de la
mesure exige une justification écrite, sinon il n'est pas une porte.

Trois conséquences, dont une contre-intuitive :

1. **La porte gèle, elle ne juge pas.** Elle interdit la hausse. Faire
   *descendre* un seuil est le signe que le chantier a avancé — et c'est le seul
   moyen de le prouver.
2. **Chaque chantier a désormais une grandeur.** Avant, « réduire le couplage »
   n'était pas une affirmation vérifiable. Maintenant `core.database` a 120
   importeurs nommés, et demain 104.
3. **L'ordre n'est pas libre.** On ne peut pas inverser une arête avant d'avoir
   déplacé ce qu'elle transporte. Le tableau ci-dessous est cet ordre, et il
   est déduit des dépendances réelles, pas d'un classement par effort.

## 2. L'ordre, déduit des dépendances

`core.database` (212 importeurs en production) est le noeud dont tout le reste
dépend. `src.constants` (86) et `src.auth_helpers` (69) viennent ensuite, puis
`src.llm_core` (67) — le shim du Sprint 3, toujours emprunté.

| Ordre | Chantier | Ce qu'il déplace | Grandeur qui doit baisser | Dépend de |
|---:|---|---|---|---|
| 1 | **MOD-9** · statuer les 10 paquets `@agentos/sfd-*` | brancher ou archiver ; arbitrer le doublon du bus Python/TS | paquets **non tranchés** / 10 — **aujourd'hui 9** | rien |
| 2 | **MOD-11bis** ~~appliquer la porte à `packages/`~~ **retiré** — la porte y gèlerait un zéro | rien | `packages/` contient **13 fichiers `.ts` et 0 `.py`** : une porte d'arêtes Python y mesurerait 0, sur 0. Un seuil à 0 qui surveille du vide est pire que pas de seuil : il a l'air de couvrir. La couverture réelle passe par `paquets_sfd_non_tranches`, qui voit les TypeScript | MOD-11 |
| 3 | **MOD-5** · `AppContext` au lieu des singletons globaux | les 3 singletons : `_fs`, `_guard`, caches | occurrences de `global` dans `src/` | rien |
| 4 | **MOD-7** · étendre l'ABC `MemoryProvider` | les chemins mémoire qui ne l'implémentent pas | `fournisseurs_hors_interface` — **aujourd'hui 0** : la classe `MemoryProvider` existe déjà, 2 fournisseurs l'implémentent. Le chantier n'est donc pas « créer une interface » mais « rendre toute non-conformance rouge » | rien |
| 5 | **MOD-6** · contrat DB sur `core.database` | 120 importeurs → façade | `core_database_importeurs` | MOD-5 |
| 6 | **MOD-3** · source unique du routage modèle | dédoublonner `ModelEndpoint` | `modules_resolution_modele` — **aujourd'hui 12** | rien |
| 7 | **MOD-8** · outils découplés de `routes` | auto-enregistrement déclaratif | arêtes `src/* → routes.*` | MOD-5 |
| 8 | **MOD-2** · inverser les arêtes restantes | `src/*` → `services/*` | `aretes_src_vers_routes` | MOD-5, MOD-7, MOD-8 |
| 9 | **MOD-1** · `route_loader` dynamique | 54 imports → `pkgutil` | `route_loader_imports_statiques` | MOD-8 |
| 10 | **MOD-4** · supprimer les shims | migrer 85 importeurs de `llm_core`/`agent_loop` | fichiers important un shim | MOD-2, MOD-6 |

**Pourquoi MOD-9 en premier, alors que c'est le plus petit ?** Parce que c'est le
seul qui ne dépend de rien et qui **retire du monde** au lieu d'y ajouter :
10 paquets TypeScript non tranchés sont 10 systèmes de parallèle possibles. Le
statut « ni branchés ni archivés » est le pire des deux : ils ne sont ni dead
code qu'on peut effacer, ni fonctionnalités qui servent.

**Pourquoi MOD-4 en dernier ?** **36 fichiers** importent un shim, pour **78 points d'import** (64 `llm_core`, 14 `agent_loop`, hors tests et hors `archive/` qui *est* le shim). Les supprimer
avant d'avoir déplacé le métier (`MOD-2`) et la base (`MOD-6`) serait un
refactor de 85 points de rupture simultanés — exactement le genre de chantier
qui échoue silencieusement et se rattrape en réintroduisant le shim.

## 3. Ce que chaque item devra prouver

Aucun item n'est « refactoriser X ». Chacun est un **geste borné** avec une
preuve de fin **comportementale** — un observable qui change, pas un log.

| # | Geste | Preuve de fin (comportementale) |
|---|---|---|
| 1 | statuer les 10 paquets | `tools/check_governance.py` ne trouve plus de paquet `sfd-*` sans statut ; le compte est **écrit**, pas recopié |
| 2 | appliquer la porte à `packages/` | ajouter un `.py` dans `packages/sfd-*/src/` **fait bouger** le compte de la porte — donc la teste avant qu'elle n'existe |
| 3 | `AppContext` | les 3 singletons disparaissent **du code** ; un test échoue si un `global` de service revient |
| 4 | ABC `MemoryProvider` | les 3 fournisseurs s'enregistrent via l'interface ; un test échoue si un quatrième ne le fait pas |
| 5 | façade DB | `core_database_importeurs` passe sous 120 **et** la suite est verte — les deux, pas l'un ou l'autre |
| 6 | source unique du routage | un changement d'endpoint prend effet par **un** endroit ; un test échoue s'il en faut deux |
| 7 | auto-enregistrement | ajouter un outil n'exige plus d'édition de l'orchestrateur ; `aretes_src_vers_routes` baisse |
| 8 | inversion des arêtes | `aretes_src_vers_routes` passe sous 30, sans qu'aucun `src/` n'importe `routes/` par une voie nouvelle |
| 9 | `route_loader` dynamique | ajouter un fichier de route **n'exige aucune édition** de `route_loader` — la preuve est l'ajout d'un fichier |
| 10 | suppression des shims | `fichiers important un shim` passe sous 85, idéalement à 0 ; `src/llm_core.py` n'est plus qu'un point d'entrée |

## 3 bis. MOD-9 — le dossier est prêt, la décision ne l'est pas

`docs/planning/MOD-9-DOSSIER.md` : dix paquets, dix lignes, avec rôle, référence résolue, coût et recommandation motivée. **Rien n'est exécuté** — brancher est une activation au-delà du Palier 0, archiver est un retrait de la SFD, et les deux sont des décisions de maintainership.

Le fait qui domine le dossier : **8 des 9 paquets non tranchés doublent un système Python `on` et `wired=True`**, et le seul paquet déjà branché (`sfd-eventbus`) tourne **en plus** de `ODYSSEUS_UNIFIED_TOKENS`. Brancher la plupart n'ajouterait donc aucune capacité : cela créerait deux systèmes pour un rôle.

En attendant l'arbitrage, les items **MOD-5, MOD-3, MOD-8, MOD-2, MOD-1 et MOD-4** restent conduisibles : aucun ne dépend de MOD-9. C'est par là que la suite s'enchaîne, conformément au v11 §4.3.

## 4. Ce que ce plan ne fait pas

* **Aucun item n'est commencé dans ce document.** Le v9 demande de soumettre le
  plan avant d'écrire du code : c'est fait, c'est à lui de dire d'y aller.
* **Aucune baisse de seuil n'est programmée.** Les seuils bougent quand le
  chantier a avancé, pas quand le plan l'a prévu. Un seuil baissé d'avance serait
  un seuil que la porte ne vérifie plus.
* **Aucun arbitrage de politique.** MOD-9 demande de statuer des paquets : c'est
  une décision de maintainership, pas de code. Le plan prépare la mesure, il ne
  décide pas.
* **Rien de tout cela ne touche P8, P12, UC-10, `AUTOEVAL_ALLOW_RESET`, ni les
  kill-switches** au-delà du Palier 0. Un refactor de modularité n'active rien.

## 5. Le préalable honnête

MOD-1 à MOD-10 représentent **des dizaines de commits** et un risque de
régression réel sur un dépôt de 5 000 tests. Deux des dix chantiers touchent des
chemins d'authentification (`core.database` est derrière `auth_helpers`), et
`MOD-4` touche 36 fichiers et 78 points d'import. Le plan annonçait 85 fichiers :
c'était un compte, pas une résolution, et il était faux dans le sens rassurant —
le chantier est plus petit qu'annoncé mais pas moins risqué, puisque chaque point
d'import est une rupture distincte.

La séquence proposée ne cherche pas à les faire vite. Elle cherche à ce que
**chaque chantier soit réversible seul** : si l'item 7 casse quelque chose, les
six précédents restent acquis et le rollback est local. C'est la seule propriété
qui rend une telle liste de dix chantiers tenable — et elle se vérifie à chaque
item, parce qu'un chantier non réversible ne peut pas être suivi d'un autre.

**Recommandation : commencer par l'item 1 (MOD-9), qui est le seul sans
dépendance, sans risque d'exécution, et qui retire du monde plutôt que d'y
ajouter.** Les neuf autres supposent qu'il reste du budget et de l'attention.
