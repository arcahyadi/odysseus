"""Porte de gouvernance — l'instrumentation durable des mesures du constat.

Les scripts qui ont produit le constat de `VISION-INTEGRATION.md` vivaient dans
`/tmp`. C'est-à-dire qu'ils disparaissaient au redémarrage, que personne ne
pouvait les rejouer, et que la discipline « mesurer avant de croire » reposait
sur ma mémoire — exactement ce que la 7ᵉ escalade reproche aux portes de doc.

Ce fichier est ce qu'ils deviennent : une porte, avec un code de sortie, et un
compte **écrit dans la documentation** — jamais recopié à la main, sinon le
problème revient sous une autre forme.

**Le signal le plus facile à mentir, ici, est `called`.** « Le module lit ce
switch, mais personne ne l'importe » a été écrit trois fois de travers avant
d'être juste, parce qu'un import prend quatre formes :

    from a.b.c import X          absolue
    from .c import X             relative, dans le meme paquet
    from src import trace_writer  paquet + sous-module, la plus discrete
    src/agent_loop.py            ...qui est un SHIM de archive/legacy/

Chaque forme omise faisait annoncer « jamais appelé » pour un module appelé à
chaque tour. Le compte est passé de 9 à 5. Les cinq ont été vérifiés à la main :
chacun n'est mentionné que dans lui-même et dans le registre.

**D'où le choix de l'AST plutôt que des motifs.** Un motif par entrée × tous
les fichiers faisait 24 000 recherches, 15 secondes par mesure. Une seule passe
AST par fichier, puis inversion des index : c'est plus rapide *et* plus exact,
puisque l'AST voit les quatre formes sans les deviner.

Usage :
    python tools/check_governance.py           # exit 1 si une capacité n'est pas décidée
    python tools/check_governance.py --write   # réécrire le compte dans TRACEABILITY.md
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys
from functools import lru_cache

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.killswitch_registry import read_states  # noqa: E402

LUS = re.compile(
    r"""(?:os\.environ(?:\.get)?\(\s*["']|os\.getenv\(\s*["']|environ\[\s*["'])([A-Z][A-Z0-9_]*)"""
)

# ── La liste unique des variables de configuration ───────────────────────────
#
# EXTRAITE du test de l'item 2, jamais recopiée. Deux listes divergeraient, et la
# divergence serait invisible : chaque test mesurerait la sienne et serait vert.
# Une seule définition, lue par les deux, est la seule forme qui tient.
_TEST_ITEM2 = REPO / "tests" / "test_sprint4_gouvernance_registre.py"


def _configuration_declaree() -> dict[str, str]:
    if not _TEST_ITEM2.is_file():
        raise SystemExit(f"ABSENT : {_TEST_ITEM2.relative_to(REPO)} — la definition du tri a disparu")
    arbre = ast.parse(_TEST_ITEM2.read_text(encoding="utf-8"))
    for noeud in arbre.body:
        # `CONFIGURATION: dict[str, str] = {...}` est un `AnnAssign`, pas un
        # `Assign`. N'en traiter qu'un des deux ferait échouer l'outil selon la
        # façon dont quelqu'un a saisi la déclaration — c'est-à-dire selon un
        # détail de forme, pas selon le fond.
        if isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name) and noeud.target.id == "CONFIGURATION":
            return ast.literal_eval(noeud.value)
        if isinstance(noeud, ast.Assign) and any(
            isinstance(c, ast.Name) and c.id == "CONFIGURATION" for c in noeud.targets
        ):
            return ast.literal_eval(noeud.value)
    raise SystemExit("CONFIGURATION introuvable dans le test de l'item 2")


SHIMS = {
    "archive/legacy/agent_loop.py": "src/agent_loop.py",
    "archive/legacy/llm_core.py": "src/llm_core.py",
}

# Une seule passe sur tout le dépôt, puis inversion. Le résultat est mis en cache
# parce que `mesure()` est appelé plusieurs fois — une porte qui relit 373
# fichiers à chaque appel est une porte qu'on saute (mesurée : 15 s, ramenés à 1).
# `lru_cache` plutôt qu'un `global` : le motif `global` existe déjà deux fois dans
# le dépôt, et en ajouter un troisième pour un cache serait du bruit.
@lru_cache(maxsize=1)
def _index() -> dict:
    variables: set[str] = set()
    # module importé -> fichiers qui l'importent
    absolus: dict[str, set[str]] = {}
    # (paquet, sous-module) -> fichiers
    paquet_sous: dict[tuple[str, str], set[str]] = {}
    # nom de sous-module importé en relatif -> fichiers
    relatifs: dict[str, set[str]] = {}
    for f in REPO.rglob("*.py"):
        if "venv" in f.parts or "node_modules" in f.parts:
            continue
        if f.relative_to(REPO).parts[0] == "tests":
            continue
        rel = str(f.relative_to(REPO))
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
            arbre = ast.parse(texte)
        except (OSError, SyntaxError):
            continue
        for m in LUS.finditer(texte):
            if m.group(1).startswith("ODYSSEUS_"):
                variables.add(m.group(1))
        for n in ast.walk(arbre):
            if isinstance(n, ast.Import):
                for a in n.names:
                    absolus.setdefault(a.name, set()).add(rel)
            elif isinstance(n, ast.ImportFrom):
                if n.level:
                    # `from .c import X` ou `from ..b.c import X`
                    if n.module:
                        relatifs.setdefault(n.module.split(".")[-1], set()).add(rel)
                    for a in n.names:
                        relatifs.setdefault(a.name, set()).add(rel)
                elif n.module:
                    absolus.setdefault(n.module, set()).add(rel)
                    # `from src import trace_writer` : le sous-module est l'alias
                    for a in n.names:
                        paquet_sous.setdefault((n.module, a.name), set()).add(rel)

    return {"variables": variables, "absolus": absolus, "paquet_sous": paquet_sous, "relatifs": relatifs}


def fichiers_production() -> list[pathlib.Path]:
    return [REPO / rel for rel in _index()["absolus"] or []] or [
        p
        for p in REPO.rglob("*.py")
        if "venv" not in p.parts and "node_modules" not in p.parts and p.relative_to(REPO).parts[0] != "tests"
    ]


def lues_par_la_production() -> set[str]:
    return set(_index()["variables"])


def _importateurs(module: str) -> list[str]:
    """Les fichiers qui importent vraiment ce fichier — les quatre formes."""
    idx = _index()
    chemin = pathlib.Path(module)
    nom = module.replace("/", ".").removesuffix(".py")
    base = chemin.stem
    trouve: set[str] = set()

    trouve |= idx["absolus"].get(nom, set())
    # Shims : `src/agent_loop.py` et `archive/legacy/agent_loop.py` sont le meme
    # module vu par deux chemins.
    for archive, shim in SHIMS.items():
        if module == archive:
            trouve |= idx["absolus"].get(shim.removesuffix(".py").replace("/", "."), set())
        if module == shim:
            trouve |= idx["absolus"].get(archive.removesuffix(".py").replace("/", "."), set())
    # `from src import trace_writer`
    paquet = ".".join(chemin.parts[:-1])
    if paquet:
        trouve |= idx["paquet_sous"].get((paquet, base), set())
    # `from .filesystem_tools import ...`
    trouve |= idx["relatifs"].get(base, set())

    trouve.discard(module)
    return sorted(trouve)


def mesure() -> dict[str, object]:
    registre = {s["env_var"]: s for s in read_states()}
    config = _configuration_declaree()
    lues = lues_par_la_production()

    non_classees = sorted(v for v in lues if v not in registre and v not in config)
    orphelines = sorted(v for v in config if v not in lues and v != "ODYSSEUS_THOUGHT_BUS")
    contradictoires = sorted(set(config) & set(registre))

    non_appelees = []
    for env, s in registre.items():
        src = s.get("source") or ""
        if not re.fullmatch(r"[\w./-]+\.py:\d+", src):
            continue
        if not _importateurs(src.split(":")[0]):
            non_appelees.append(env)

    return {
        "entrees_registre": len(registre),
        "variables_lues": len(lues),
        "capacites_non_classees": non_classees,
        "justifications_mortes": orphelines,
        "contradictions": contradictoires,
        "lecteurs_sans_importateur": sorted(non_appelees),
    }


RAPPORT = "docs/traceability/TRACEABILITY.md"
MARQUEUR = "<!-- gouvernance:generee -->"


def _ligne(m: dict[str, object]) -> str:
    return (
        f"| Gouvernance — capacités non classées | **{len(m['capacites_non_classees'])}** "
        f"(variables lues hors registre et hors configuration) "
        f"| Justifications de configuration mortes | **{len(m['justifications_mortes'])}** "
        f"| Contradictoires (registre ET configuration) | **{len(m['contradictions'])}** "
        f"| Lecteurs sans importateur (`called=False`) | **{len(m['lecteurs_sans_importateur'])}** "
        f"| Registre | **{m['entrees_registre']}** entrées, **{m['variables_lues']}** variables lues |"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="reecrire le compte dans TRACEABILITY.md")
    args = ap.parse_args()

    m = mesure()
    ligne = _ligne(m)
    bloque = any(m[k] for k in ("capacites_non_classees", "justifications_mortes", "contradictions"))

    if args.write:
        if bloque:
            print("refus d'ecrire : la porte est rouge, le compte publierait un etat faux.")
            for k in ("capacites_non_classees", "justifications_mortes", "contradictions"):
                if m[k]:
                    print(f"  {k} : {m[k]}")
            return 1
        chemin = REPO / RAPPORT
        texte = chemin.read_text(encoding="utf-8")
        if MARQUEUR in texte:
            avant, _, apres = texte.partition(MARQUEUR)
            debut = apres.index("\n") + 1
            fin = apres.index("\n", debut) + 1
            texte = avant + MARQUEUR + "\n" + ligne + apres[debut:fin - 1] + apres[fin:]
        else:
            texte = texte.rstrip() + f"\n\n{MARQUEUR}\n{ligne}\n"
        chemin.write_text(texte, encoding="utf-8")
        print(f"ecrit dans {RAPPORT}")
        return 0

    print(ligne)
    if bloque:
        print("\nGOUVERNANCE ROUGE :")
        for k in ("capacites_non_classees", "justifications_mortes", "contradictions"):
            if m[k]:
                print(f"  {k} : {m[k]}")
        return 1
    if m["lecteurs_sans_importateur"]:
        # Informatif, pas bloquant : c'est un etat de connaissance, pas une erreur
        # de classement. Mais il doit etre visible, sinon OPA redevient invisible —
        # ce que l'item 2 a corrige.
        print(f"\n  (informatif) {len(m['lecteurs_sans_importateur'])} lecteur(s) sans "
              "importateur : le module est lisible mais jamais appele.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
