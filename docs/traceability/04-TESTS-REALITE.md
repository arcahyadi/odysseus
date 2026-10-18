# 04 — TESTS : Réalité fonctionnelle

> **🟢 MESURE 2026-09-26 (Sprint 3 item 8) — 4 887 PASS.**
> - **Suite réelle : 4 887 PASS · 2 skipped · 0 FAILED · 0 errors**, lint `ruff` à **3 707** (base connue 3 708).
> - +11 tests : la preuve P5/P21 (`tests/test_sprint3_p5_p21_disclosure_restricts.py`), **4 mutations** vérifiées.
> - Les ci-dessous sont les **mesures historiques** des sprints précédents, conservées telles quelles : un Palier 0 n'est pas un état courant.

> **🟢 MISE À JOUR 2026-09-26 (Sprint 1b) — SUITE VERTE AVEC LE PALIER 0 ACTIVÉ.**
> - **Suite réelle : 4 794 tests collectés → 4 792 PASS · 2 skipped · 0 FAILED · 0 errors (100 % vert).**
> - +18 tests vs Sprint 1a. Ce ne sont pas des tests de couverture ajoutés à la chaîne : ce sont des **tests de garde** sur des propriétés de sécurité et d'honnêteté (détail en fin de document).
>
> **🟢 MISE À JOUR 2026-09-26 (Sprint 1a) — SUITE COMPLÈTEMENT VERTE.**
> - Suite réelle : 4 744 tests collectés → 4 742 PASS · 2 skipped · 0 FAILED · 0 errors (100 % vert).
> - Point de départ mesuré le 2026-09-25 : 4 633 PASS · 104 FAILED · 5 errors. **109 échecs réparés en 8 commits atomiques** (`b76471b` → `2b36f83`).
> - Les 5 `errors` n'étaient pas une fixture cassée : `engine_server.py` codait `/home/agentos/*` en dur et faisait `mkdir()` à l'import → `PermissionError` sur hôte de dev. Chemins désormais surchargeables par env (`AGENTOS_DATA_DIR` / `AGENTOS_WORKSPACE_DIR` / `AGENTOS_VAULT_DIR`), défauts container inchangés. **Ces 5 tests n'avaient jamais été réellement exercés** — ils le sont désormais.
> - **Cause racine dominante des 104 échecs : les shims `src/*.py` → `archive/legacy/*.py`.** En ré-exportant le legacy comme module top-level *distinct*, les fonctions résolvaient leurs globals depuis l'autre `__dict__` : `monkeypatch` et `importlib.reload` des tests devenaient inopérants (`StopIteration`, `[]`, `''`, `KeyError`). Corrigé par `exec` du source legacy dans le namespace du shim (`src/llm_core.py`, `src/agent_loop.py`).
> - Autres classes réparées : imports `_truncate` déplacés vers `src/tool_utils.py` sans mettre à jour les appelants (tous les outils fichiers/sous-processus échouaient) ; compose GPU figés en version « minimale » ; pollution `AUTH_ENABLED` du module e2e (11 tests d'auth faussement rouges en suite complète) ; 2 assertions faussement négatives.
> - `ruff check .` : **3 692 erreurs** (dette de lint pré-existante, inchangée — les correctifs Sprint 1a n'en ajoutent aucune).
>
> **Ce que « 100 % vert » ne dit pas** : la suite est verte *en local, sans service externe*. ChromaDB, Mem0, LLM et le moteur Docker ne sont pas joignables → les chemins degradés sont testés, pas les chemins nominaux. La couverture fonctionnelle réelle reste inférieure à 100 % (cf. `04-OBJECTIFS-COUVERTURE.md`).


---

> Mesure **non destructive** de ce qui tourne réellement dans l'environnement local.
> Aucune correction, aucun install, aucune modification. Toutes les commandes ont un `timeout`.
>
> - Date : 2026-09-25
> - Branche : `feat/inventaire-global-v1`
> - Dernier commit : `5402e61 backup: snapshot pre-reinstallation PC (WIP fige, hook bypass)`
> - Machine : Linux, workdir `/home/tayk0oo/Projets/odysseusAgentOS`

---

## Palier 0 activé : ce que la suite ne dit pas

Le Palier 0 (FND-4 option C) a basculé 14 kill-switchs de `off` à `on` **par défaut dans le code**. Trois choses ont été apprises en le faisant ; les trois sont désormais verrouillées par des tests.

**1. Une suite verte ne prouve pas qu'un chemin est atteint — elle peut même le détruire.**
`ODYSSEUS_AUTOEVAL` à `on` a suffi à déclencher un **vrai `git reset --hard HEAD`** depuis un test de la suite. Le chemin : le test fournit des `verifier_reasons` → `apply_autoeval` décide `REVERT` → `_git_reset` s'exécute dans l'arbre de travail du dépôt. **14 flip de kill-switchs non commités ont été effacés** avant d'être détectés. Règle appliquée depuis : *commiter avant de lancer la suite, toujours*.

**2. Décider et agir sont deux choses différentes.**
Correction : `ODYSSEUS_AUTOEVAL_ALLOW_RESET`, second switch **OFF par défaut**, est requis pour qu'une décision soit exécutée. La décision reste prise, tracée et retournée ; seule l'action est retenue. Le trou a d'abord été fermé sur `langgraph_loop.py` et `autoeval_loop.py`, **puis sur le chemin live** `archive/legacy/agent_loop.py` — qui filait encore le vrai runner sur le seul `autoeval_enabled()`. Chaîne réelle et atteignable : écriture d'un fichier harness → drift Observer `HIGH` → revert → effacement de l'arbre du serveur.

**3. Un test qui ne teste rien coûte plus cher qu'un test manquant.**
Ces 18 tests protègent des propriétés, pas des fonctions :
- aucun processus `git` lancé sans opt-in explicite ;
- un switch `wired=True` a réellement un lecteur dans le code ;
- un switch `wired=False` n'en a pas (le drapeau ne peut pas pourrir) ;
- le `default` affiché par le cockpit est bien celui que le code appliquera ;
- aucun switch non câblé ne peut se présenter actif.

Ce dernier point a révélé **9 switches sans aucun lecteur** (DEEPEVAL, SUPABASE, VAULTWARDEN, PLAYWRIGHT, BROWSER_HARNESS, ZEN_FROM_ENDPOINT, INPROCESS_DISCORD, INPROCESS_TELEGRAM, CHANNEL_AGENT_REPLY) qui annonçaient `on` — de la configuration inerte présentée comme active — et **16 descripteurs** dont le `default` contredisait le lecteur réel. Le cockpit est une condition préalable du Palier 0 : il ne pouvait pas mentir.

**Ce que l'activation n'a pas résolu** : les 14 switchs sont câblés, mais plusieurs modules ne sont encore appelés que pour `logger.info(...)` leur résultat, ou avec une entrée vide qui rend un calcul constant. Un switch `on` ne rend pas un module actif. Le détail principe par principe est dans `02-PRINCIPES-UC.md`.

---

## 0. Verdict en une ligne

**Le projet ne tourne PAS localement en l'état.** L'environnement a été réinitialisé (venv absent, **zéro dépendance applicative installée**, ni `pytest` ni `ruff`). Le code et la suite de tests existent et sont syntaxiquement valides (0 erreur), mais **rien ne peut être collecté ni exécuté** sans réinstallation des dépendances. Le commit le confirme : « snapshot pre-reinstallation PC ».

---

## 1. Environnement Python

### Commandes exactes

```bash
ls -d .venv venv 2>/dev/null
which python3
python3 --version
python3 -c "import fastapi, sqlalchemy, redis, pydantic" 2>&1
```

### Sorties

```
$ ls -d .venv venv 2>/dev/null
(rien — aucun venv)

$ which python3
/usr/bin/python3

$ python3 --version
Python 3.14.7

$ python3 -c "import fastapi, sqlalchemy, redis, pydantic"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import fastapi, sqlalchemy, redis, pydantic
ModuleNotFoundError: No module named 'fastapi'
```

### Constats

| Élément | État |
|---|---|
| `.venv` / `venv` | **absent** (aucun `pyvenv.cfg` trouvé) |
| `python3` par défaut | `/usr/bin/python3` = **Python 3.14.7** |
| `python3.12` | présent = **Python 3.12.14** |
| `uv` / `pipx` | absents |
| `pip` | présent (géré système, paquets OS uniquement) |

Test d'import module par module :

```
MISS fastapi
MISS sqlalchemy
MISS redis
MISS pydantic
MISS uvicorn
MISS litellm
MISS pytest
MISS pytest_asyncio
OK   yaml      (PyYAML 6.0.3)
MISS httpx
```

Seuls `PyYAML` et `numpy` (2.4.6) sont présents dans le Python système — ce sont des paquets OS/distro, **pas** l'environnement du projet. Note : `redis` n'est d'ailleurs **pas déclaré** dans `requirements.txt` ; l'import testé est purement indicatif.

Incohérence de version : le projet cible `py311` (`ruff.toml: target-version = "py311"`, docs « Python 3.11+ »), la CI principale tourne en **3.11**, le workflow e2e en **3.14**. Le Python par défaut ici (3.14.7) est en tête de ces cibles, sans venv dédié.

---

## 2. Lint — `ruff check .`

### Commande exacte

```bash
ruff check . 2>&1 | tail -30
```

### Sortie

```
/bin/bash: ligne 1: ruff: commande introuvable
EXIT=127
```

**`ruff` n'est pas installé** (ni binaire, ni dans `node_modules/.bin`). Aucun rapport de lint ne peut être produit. La CI l'installe explicitement (`pip install ruff`), donc l'échec est purement environnemental, pas un défaut de config (`ruff.toml` existe et est complet).

Statut : **NON MESURABLE localement**.

---

## 3. Collecte pytest — `--collect-only`

### Commande exacte

```bash
timeout 180 python3 -m pytest --collect-only -q 2>&1 | tail -40
```

### Sortie

```
/usr/bin/python3: No module named pytest
EXIT=1
```

**`pytest` n'est pas installé** (il est pourtant déclaré dans `requirements.txt` ligne 48, avec `pytest-asyncio` ligne 49). Impossible de compter les tests réellement collectés, ni de détecter les erreurs de collecte / imports cassés.

Statut : **NON MESURABLE localement** (0 test collecté).

---

## 4. Échantillon borné — `-k "memory or killswitch or router or security"`

### Commande exacte

```bash
timeout 240 python3 -m pytest tests/ -q -k "memory or killswitch or router or security" 2>&1 | tail -60
```

### Sortie

```
/usr/bin/python3: No module named pytest
EXIT=1
```

Échec avant même la découverte des fichiers : pas de moteur pytest. Aucun pass / fail / erreur d'import ne peut être distingué.

Statut : **NON MESURABLE localement**.

---

## 5. Dépendances manquantes & commande d'installation (non exécutée)

### Ce qui manque précisément

- **Moteur de test** : `pytest`, `pytest-asyncio` (→ présent dans `requirements.txt`).
- **Runtime applicatif** : `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `pydantic-settings`, `litellm`, `httpx`, `python-dotenv`, etc. (section 1 de `requirements.txt`).
- **Lint** : `ruff` (hors `requirements.txt`, installé séparément par la CI).
- Aucun venv isolé n'existe.

### Commande qui *serait* nécessaire (⚠️ NON exécutée ici)

```bash
cd /home/tayk0oo/Projets/odysseusAgentOS
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install ruff                      # lint (hors requirements.txt)
python -m pytest -q --collect-only    # vérifier la collecte
```

C'est exactement la procédure documentée dans `CONTRIBUTING.md:37` et `docs/operations/setup.md:43`.
Pour le lint seul : `ruff check .`.
Optionnel selon les features : `pip install -r requirements-optional.txt` (voir `docs/operations/setup.md:245`).
Alternative documentée : `uv pip install -r requirements.txt` (`docs/operations/setup.md:361`), mais `uv` n'est pas installé ici.

> Aucune de ces commandes n'a été lancée : contrainte « n'installe rien ».

---

## 6. Ce qui EST mesurable sans dépendances : inventaire statique de la suite

Mesure faite en lecture seule via `ast.parse` + `tests/_taxonomy.py` (module **pur stdlib**, aucune dépendance applicative). Le script a été écrit dans `/tmp/opencode/measure_tests.py` — **hors du dépôt**.

### Volumétrie brute

| Métrique | Valeur |
|---|---|
| Fichiers `test_*.py` | **693** |
| Fichiers de test tous types (`.py` + `.js/.mjs/.ts`) | **701** |
| Fonctions `test_*` (comptage AST) | **4 151** |
| Classes `Test*` | 185 |
| Erreurs de **syntaxe** Python | **0** |
| Fichiers JS/TS de test | 8 |

### Répartition par catégorie (taxonomie `area_*` / `sub_*`)

| Catégorie | Fichiers | Fonctions `test_*` |
|---|---:|---:|
| `security` (auth, owner-scope, SSRF, XSS, confinement) | 82 | 510 |
| `services` (llm, cookbook, memory, email, calendar…) | 166 | 925 |
| `routes` (comportement HTTP / API) | 27 | 283 |
| `unit` (parsers/utilitaires) | 38 | 100 |
| `js` (Node-backed) | 55 | 163 |
| `cli` | 29 | 44 |
| `helpers` (self-tests helpers) | 1 | 26 |
| `uncategorized` (fallback conservateur) | 303 | 2 100 |
| **TOTAL** | **701** | **4 151** |

Répartition détaillée des sous-dossiers : `tests/` (racine), `cli/`, `fixtures/`, `helpers/`, `load/`, `prompts/`, `streaming/`, `tools/`.

**Lecture** : `uncategorized` est massif (303 fichiers) **par conception** — la taxonomie ne classe que par tokens de nom de fichier explicites et préfère le fallback au risque d'erreur (`_taxonomy.py`). Cela ne reflète **pas** un défaut de la suite.

### Robustesse à l'absence de deps (important)

`tests/conftest.py` **stubbe automatiquement** (`MagicMock`) les dépendances lourdes absentes avant la collecte : `sqlalchemy*`, `fastapi*`, `starlette*`, `pydantic`, `httpx`, `bcrypt`, `pyotp`. Il force aussi `DATABASE_URL=sqlite:///:memory:` pour éviter l'échec d'ouverture de `./data/app.db` (le dossier `data/` n'existe pas ici).

Conséquence : **avec `pytest` seul** (mais sans le reste), une partie de la collecte serait probablement possible. **Mais** les tests `routes`/`security` qui reposent sur le vrai FastAPI/SQLAlchemy seraient exécutés contre des `MagicMock` — donc **non significatifs**. Ce mécanisme a été conçu pour la robustesse de collecte, pas pour valider le comportement.

---

## 7. VERDICT

### Le projet tourne-t-il localement ?

**Non.** Environnement réinitialisé : aucun venv, aucune dépendance applicative, ni `pytest` ni `ruff`. Le serveur (`uvicorn app:app`) ne peut pas démarrer, et la suite ne peut pas être collectée. Le commit HEAD (`backup: snapshot pre-reinstallation PC`) explique directement cet état.

### Que peut-on tester réellement aujourd'hui ?

- **Rien au niveau moteur de test** (0 test collecté, 0 test exécuté).
- Seulement de l'**analyse statique** : inventaire, répartition, validité syntaxique (0 erreur sur 693 fichiers `.py`).
- Le code existe et est **syntaxiquement sain**, mais sa validité comportementale est **non prouvée** dans cet environnement.

### Que manque-t-il ?

1. Un **venv** (`python3.12 -m venv venv`).
2. `pip install -r requirements.txt` (apporte `pytest`, `pytest-asyncio`, `fastapi`, `sqlalchemy`, `pydantic`, `litellm`, `httpx`…).
3. `pip install ruff` pour le lint.
4. Idéalement un dossier `data/` (la CI fait `mkdir -p data`) — déjà contourné par conftest en mémoire, mais requis pour l'app réelle.

### Compatibilité CI vs local

| | CI (`ci.yml`) | E2E (`e2e.yml`) | Local (ici) |
|---|---|---|---|
| Python | 3.11 | 3.14 | 3.14.7 par défaut, 3.12.14 dispo, **aucun venv** |
| Deps | `pip install -r requirements.txt` | `requirements.txt` + `ruff` | **aucune** |
| Lint | non dans `ci.yml` (ruff dans e2e) | `pip install ruff` | `ruff` absent |
| Pytest | `python -m pytest -q` (`continue-on-error: true`) | oui | **impossible** |
| `data/` | `mkdir -p data` | oui | absent |

Points notables pour l'analyse :

- Le job `python-tests` de la CI est **informationnel** (`continue-on-error: true`, commentaire : « known flaky / environment-dependent failures »). Un rouge pytest en CI n'est donc pas bloquant aujourd'hui.
- Le job `python-syntax` (compileall, sans deps) est le seul filet vert garanti même sans dépendances — cohérent avec notre constat : **0 erreur de syntaxe**.
- L'écart **CI 3.11 vs e2e/local 3.14** est un risque réel de compatibilité (versions de libs, comportements asyncio) à garder à l'œil.

**Conclusion** : l'échec local est **100 % environnemental**, pas un échec intrinsèque du code. Pour mesurer la réalité fonctionnelle (pass/fail/collecte), il faut d'abord reconstruire le venv avec la commande de la section 5, puis relancer les commandes des sections 2–4.
