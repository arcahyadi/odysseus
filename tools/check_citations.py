"""Vérifie que chaque citation `fichier:ligne` des docs de traçabilité existe.

Ce que cet outil NE fait PAS — à lire avant de s'en servir
-----------------------------------------------------------
**Il vérifie la documentation du dépôt, pas les livrables.** `DOC_GLOBS` couvre
`docs/traceability/*.md` et `docs/planning/*.md`. Rien d'autre n'est inspecté.

C'est écrit ici parce que le risque est réel : le nom « check_citations » décrit
exactement la fonctionnalité d'INT-10 de la vision — *grounding et citations dans
les livrables de recherche* — et qui n'existe pas dans ce dépôt. Quelqu'un peut
donc lire « les citations sont vérifiées » et conclure que le livrable d'une
recherche est sourcé. Il ne l'est pas : rien ici n'ouvre un livrable produit par
l'agent.

Deux choses distinctes, à ne pas confondre :

* **ce que l'outil vérifie** : qu'un `fichier:ligne` cité dans une fiche existe
  réellement. Une citation fausse est pire qu'une absence de citation, parce
  qu'elle donne l'apparence d'une preuve.
* **ce qu'INT-10 demanderait** : qu'une réponse cite ses sources, et que ces
  sources soient consultables. C'est une fonctionnalité, absente, et à ne pas
  confondre avec le fait qu'un outil de documentation existe.

`tests/test_sprint4_faux_amis.py` verrouille cette frontière : il échoue si
`DOC_GLOBS` s'élargit au-delà de la documentation, ou si ce fichier cesse de dire
ce qu'il ne fait pas.

Pourquoi un outil plutôt qu'un coup de main
-------------------------------------------
Les docs de traçabilité citent des `file:line` pour *prouver* un statut. Une citation
falsa est pire qu'une absence de citation : elle donne l'apparence d'une preuve. Trois
erreurs réelles ont été trouvées ainsi, chacune invisible à la relecture :

* `tool_security.py:2320` cité pour une définition dans un fichier de 230 lignes —
  2320 était en fait le *site d'appel* dans la boucle ;
* `agent_loop.py:4314-4316` cité pour `resume()`, dont le site réel est `:4560-4562`
  (dérive d'environ 245 lignes après un refactor) ;
* `agent_loop.py:4330-4339` cité pour prouver que `FILE_DOWNLOAD` n'est jamais
  appliqué, alors que l'appel est en `:4584` — la doc affirmait faux.

Un validateur qui n'a jamais échoué ne prouve rien : ce fichier est donc lui-même
auto-testé (`--self-test`), et `tests/test_sprint3_citations_resolve.py` le fait échouer
sur une citation inventée.

Ce que cet outil NE fait PAS (limite honnête, à lire avant de s'y fier)
---------------------------------------------------------------------
Il vérifie qu'une citation ** Pointe dans le vide** : un fichier qui n'existe plus, ou
un numéro de ligne au-delà de la fin du fichier. Il ne vérifie **pas** que la ligne
citée *dit* ce que la doc affirme.

Concrètement, les trois erreurs réelles citées en tête de fichier — y compris
`agent_loop.py:4314-4316` pour un site réel en `:4560`, soit 245 lignes d'écart — sont
toutes **dans les bornes** du fichier. Cet outil les aurait laissées passer. Il les a
simplement rendues visibles en obligeant à aller relire le site réel.

La défense réelle contre la dérive de citations n'est donc pas ce fichier, mais :
  * l'audit des `source` du registre de kill-switches (54 descripteurs, qui, lui, contrôle
    le *contenu* de la ligne et pas seulement son existence) ;
  * les tests comportementaux, qui prouvent le comportement et non la citation ;
  * et la relecture des docs à chaque item, qui a trouvé les trois dérives ci-dessus.
Ce Checker est un garde-fou bon marché, pas une garantie. Il est ici parce qu'un garde-fou
bon marché qui n'attrape pas une classe d'erreur vaut mieux que pas de garde-fou du tout,
à condition de ne pas survendre ce qu'il couvre.

Résolution des noms de base
---------------------------
Les docs citent majoritairement des **noms de base** (`agent_loop.py:3054`), pas des
chemins. La résolution tente d'abord `archive/legacy/`, puis le reste du dépôt, en
préférant `archive/legacy/agent_loop.py` à la shim `src/agent_loop.py` : la shim ne fait
qu'`exec` le fichier archivé, et c'est le fichier archivé qui porte les lignes réelles.

Usage
-----
    python tools/check_citations.py                  # vérifie et sort non-zéro si drift
    python tools/check_citations.py --self-test      # prouve que le détecteur détecte
    python tools/check_citations.py --write-report   # réécrit le compte dans TRACEABILITY.md
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# `fichier.ext:12` ou `fichier.ext:12-34`. Volontairement large sur les extensions :
# une citation vers un `.ts` ou un `.md` est aussi une affirmation vérifiable.
CITATION_RE = re.compile(
    r"([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|ya?ml|json|ts|tsx|js|jsx|md|cfg|txt|toml|ini|sh))"
    r":(\d+)(?:\s*[-–]\s*(\d+))?"
)

DOC_GLOBS = ("docs/traceability/*.md", "docs/planning/*.md")

# Répertoires ignorés : un `agent_loop.py` de test ou une copie de venv porterait de
# mauvaises lignes et ferait échouer la résolution au hasard.
#
# `archive` n'est PAS ignoré, et c'est volontaire : c'est là que vit le corps réel de la
# boucle (`archive/legacy/agent_loop.py`, ~4700 lignes), tandis que `src/agent_loop.py`
# n'est qu'une shim de 27 lignes qui l'`exec`. Les exclure envoyait le résolveur droit
# sur la shim — exactement l'erreur que ce Checker existe pour attraper.
IGNORED_PARTS = {"__pycache__", "venv", ".venv", "node_modules", ".git", "tests"}

# Extensions balayées pour construire l'index des noms de base.
INDEXED_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".md", ".ts", ".tsx", ".js", ".cfg", ".txt"}


def build_index() -> dict[str, list[pathlib.Path]]:
    """Index nom de base -> chemins, en privilégiant `archive/legacy/`.

    L'ordre de résolution est déterministe pour qu'un échec soit reproductible : le
    premier tri Stable fait foi, à l'exception de `archive/legacy/` qui passe devant.
    """
    index: dict[str, list[pathlib.Path]] = {}
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in INDEXED_SUFFIXES:
            continue
        rel = path.relative_to(REPO_ROOT)
        if IGNORED_PARTS & set(rel.parts[:-1]):
            continue
        index.setdefault(path.name, []).append(path)
    for name, paths in index.items():
        paths.sort(key=lambda p: (0 if p.parts[len(REPO_ROOT.parts)] == "archive" else 1, len(p.parts), str(p)))
        index[name] = paths
    return index


def resolve(basename: str, index: dict[str, list[pathlib.Path]]) -> pathlib.Path | None:
    """Résout un nom de base cité vers un fichier réel du dépôt.

    `archive/legacy/agent_loop.py` gagne contre `src/agent_loop.py` : la shim ne porte
    pas les lignes de la boucle, elle les délègue.
    """
    direct = index.get(basename)
    if direct:
        return direct[0]
    if "/" in basename:
        candidate = REPO_ROOT / basename
        if candidate.is_file():
            return candidate
    # Cite peut-être un chemin relatif depuis une racine de doc ; on tente le nom de base.
    tail = pathlib.Path(basename).name
    return (index.get(tail) or [None])[0]


def iter_citations(docs: list[pathlib.Path]):
    for doc in docs:
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in CITATION_RE.finditer(line):
                yield doc, lineno, m


def _rel(path: pathlib.Path) -> str:
    """Chemin relatif à la racine du dépôt quand c'est possible, sinon tel quel.

    Un doc hors dépôt (un test qui écrit son propre fichier) ne doit pas faire lever
    `ValueError` : le Checker doit * rapporter*, pas planter.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def check(docs: list[pathlib.Path], index: dict[str, list[pathlib.Path]]) -> tuple[int, list[tuple], set[str]]:
    total = 0
    problems: list[tuple] = []
    unresolved: set[str] = set()
    for doc, lineno, m in iter_citations(docs):
        total += 1
        basename, start, end = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        target = resolve(basename, index)
        if target is None:
            unresolved.add(basename)
            continue
        n_lines = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        if start < 1 or start > n_lines or end > n_lines or end < start:
            problems.append((_rel(doc), lineno, m.group(0), f"{_rel(target)} a {n_lines} lignes"))
    return total, problems, unresolved


def self_test(index: dict[str, list[pathlib.Path]]) -> int:
    """Prouve que le détecteur détecte. Un validateur jamais en échec ne prouve rien."""
    failures = []

    # 1) une ligne absurdement haute doit être signalée.
    biggest = max((len(p.read_text(encoding="utf-8", errors="replace").splitlines()), p) for p in index.values() for p in p[:1])
    n_lines, path = biggest
    total, problems, _ = check([path], index)
    del total
    citation_path = REPO_ROOT / "docs" / "traceability" / "_selftest_citation.md"
    citation_path.parent.mkdir(parents=True, exist_ok=True)
    citation_path.write_text(f"`{path.name}:{n_lines + 5000}`\n", encoding="utf-8")
    try:
        _, problems, _ = check([citation_path], index)
        if not problems:
            failures.append("une citation hors fichier n'a PAS ete detectee")
    finally:
        citation_path.unlink(missing_ok=True)

    # 2) un nom de base invente doit etre signale comme non resolu.
    citation_path.write_text("`fichier_qui_nexiste_pas_1234.py:12`\n", encoding="utf-8")
    try:
        _, _, unresolved = check([citation_path], index)
        if "fichier_qui_nexiste_pas_1234.py" not in unresolved:
            failures.append("un nom de base invente n'a PAS ete signale")
    finally:
        citation_path.unlink(missing_ok=True)

    for f in failures:
        print(f"AUTO-TEST ECHEC : {f}")
    if not failures:
        print("auto-test OK : le detecteur detecte une citation hors fichier et un nom invente")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true", help="prouver que le detecteur detecte")
    ap.add_argument("--write-report", action="store_true", help="ecrire le compte dans TRACEABILITY.md")
    args = ap.parse_args()

    docs = sorted({p for pattern in DOC_GLOBS for p in REPO_ROOT.glob(pattern) if p.is_file()})
    index = build_index()

    if args.self_test:
        return self_test(index)

    total, problems, unresolved = check(docs, index)
    print(f"citations verifiees : {total} ({len(docs)} docs)")
    print(f"hors fichier         : {len(problems)}")
    for doc, lineno, cit, why in problems:
        print(f"  {doc}:{lineno}  {cit}  -> {why}")
    print(f"noms non resolus     : {len(unresolved)}")
    for name in sorted(unresolved):
        print(f"  {name}")

    if args.write_report and not problems and not unresolved:
        print("(compte a reporter dans TRACEABILITY.md — valeur generee, pas recopiee)")

    return 1 if problems or unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
