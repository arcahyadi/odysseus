# Sprint 1a — Recette : 109 échecs réparés, suite verte

> Date : 2026-09-26 · Branche `feat/inventaire-global-v1` · Commits `b76471b` → `2b36f83`
> Mesure : **4 744 tests collectés → 4 742 PASS · 2 skipped · 0 FAILED · 0 error** (démarrage : 4 633 PASS / 104 FAILED / 5 errors)

## Le pattern qui a tout expliqué

Les shims `src/<module>.py` → `archive/legacy/<module>.py` (introduits par `5402e61 backup: snapshot pre-reinstallation PC`) ré-exportaient le legacy comme **module top-level distinct** :

```python
sys.path.insert(0, "archive/legacy")
import llm_core as _mod          # <- un AUTRE module, avec son propre __dict__
```

Les fonctions importées résolvaient alors leurs globals (`_get_http_client`, `stream_llm`, `execute_tool_block`, `blocked_tools_for_owner`…) depuis cet **autre** `__dict__`. Conséquence : les `monkeypatch.setattr(src.llm_core, ...)` et `importlib.reload` des tests ne touchaient rien. D'où la gerbe de symptômes trompeurs — `StopIteration`, `assert []`, `'' == 'Hi there'`, `KeyError 'num_ctx'`, `None is False` — qui firent croire à 29 régressions de parsing streaming dans le LLM. **Le parsing était correct.**

Correctif appliqué (`src/llm_core.py`, `src/agent_loop.py`) : compiler et `exec` le source legacy **dans le namespace du shim**, pour que `__globals__` soit le `__dict__` du module public.

```python
_legacy_path = os.path.join(_archive_dir, "llm_core.py")
with open(_legacy_path, "rb") as _f:
    _code = compile(_f.read(), _legacy_path, "exec")
exec(_code, globals())
```

## Les 5 autres classes de causes

| Classe | Symptôme | Cause | Correctif |
|---|---|---|---|
| Imports déplacés | `error: cannot import name '_truncate'` sur **tous** les outils fichiers/sous-processus | `_truncate` migré vers `src/tool_utils.py`, appelants laissés sur `src.tool_execution` | 3 imports (`filesystem_tools`, `subprocess_tools`) |
| Dérive config | 7 tests compose GPU | standalone figés à 4 services alors que la base en a 33 | régénération via le script sanctionné `scripts/regenerate_gpu_standalone.py` |
| Pollution d'env | 11 tests d'auth rouges **en suite complète**, verts isolément | `test_e2e_complete.py` faisait `setdefault(AUTH_ENABLED=false)` au niveau module, jamais révoqué | pose avant `import app` (la closure de `setup_auth` capture `LOCALHOST_BYPASS` au setup), **restauration immédiate**, re-pose par fixture module-scope |
| Fixture codée en dur | 5 `errors` `PermissionError` | `engine_server.py` faisait `mkdir()` sur `/home/agentos/*` à l'import | chemins surchargables par env, défauts container inchangés |
| Faux négatifs d'assertion | 2 échecs | `docs/setup.md` déplacé ; `/api/documents/<uuid>` sondé avec un id fantôme sur une route qui prend un `session_id` | chemin corrigé ; vérification via le schéma OpenAPI |

## Leçon d'orchestration

Quatre sous-agents ont travaillé en parallèle sur des domaines déclarés « disjoints ». Deux ont signalé des modifications « pré-existantes sans rapport » dans l'arbre de travail : **c'était l'agent voisin qui écrivait en même temps**. their comptes de travail n'étaient donc pas fiables, mais `git status` a permis d'attribuer chaque changement à son auteur avant commit. **Ne jamais faire confiance au rapport d'un agent sur l'état de l'arbre ; le vérifier.**

## Incident à retenir (near-miss)

Un `git push origin dev:dev --force-with-lease` a été lancé alors que le branch `dev` **local** était périmé (`5402e61`) alors que `origin/dev` était à `1e96c7c` : le force-push a brièvement repoussé `dev` en arrière. Récupéré parce que `1e96c7c` est un ancêtre de `feat` — **aucun commit perdu**. Règle : ne jamais `--force` sur `dev` ; aligner d'abord le branch local (`git branch -f dev <branche-de-travail>`) puis pousser en fast-forward normal.

## Ce que « 100 % vert » ne prouve pas

La suite est verte **en local, sans service externe**. ChromaDB, Mem0, LLM et le moteur Docker ne sont pas joignables : ce sont les chemins *degradés* qui sont testés, pas les chemins nominaux. `OPENCODE_API_KEY` manque toujours dans `.env` (bloquant tout appel modèle réel).
