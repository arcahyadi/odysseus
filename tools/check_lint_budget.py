"""Porte de budget lint : échoue seulement en cas d'AUGMENTATION.

`ruff check .` échoue aujourd'hui avec 3708 signalements, tous préexistants et
répartis sur un code que personne ne veut réécrire (`PLC0415` : 2659 imports
volontairement paresseux, `PLW0603`, etc.). Une porte `ruff check .` en CI
serait donc rouge dès le premier jour, et une porte rouge dès le premier jour
n'est pas une porte : c'est un bruit que l'on finit par ignorer.

Ce que cette porte mesure est la seule chose qui compte pour une suite de
travaux : **le nombre de signalements ne doit pas augmenter**. On peut en
supprimer autant qu'on veut, et chaque suppression est comptée comme un gain.

Usage :
    python tools/check_lint_budget.py             # exit 1 si le budget est dépassé
    python tools/check_lint_budget.py --update   # réécrit tools/lint_baseline.txt
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BASELINE = REPO / "tools" / "lint_baseline.txt"
MOTIF = re.compile(r"^\S+:\d+:\d+:")


def compte() -> int:
    py = str(REPO / "venv/bin/python")
    if not pathlib.Path(py).is_file():
        py = sys.executable
    p = subprocess.run(
        [py, "-m", "ruff", "check", "--output-format", "concise", "."],
        capture_output=True,
        text=True,
        cwd=REPO,
        # `ruff` sort en 1 quand il trouve des signalements — c'est le cas
        # normal ici, pas une panne. On lit donc son code de retour sans le
        # traiter comme une erreur, et c'est le *contenu* qui decide.
        check=False,
    )
    return sum(1 for ligne in p.stdout.splitlines() if MOTIF.match(ligne))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true", help="réécrire le budget courant")
    args = ap.parse_args()

    courant = compte()
    if args.update:
        BASELINE.write_text(f"{courant}\n", encoding="utf-8")
        print(f"budget ecrit : {courant}")
        return 0

    if not BASELINE.is_file():
        # `relative_to` lèverait sur un chemin hors du dépôt — ce que fait un
        # test qui veut la porte sans toucher au vrai budget. Le message doit
        # rester lisible dans les deux cas, sinon la porte tombe sur une erreur
        # de chemin au lieu de dire ce qu'elle a à dire.
        try:
            cible = BASELINE.relative_to(REPO)
        except ValueError:
            cible = BASELINE
        print(f"ABSENT : {cible} — lancez --update")
        return 1

    budget = int(BASELINE.read_text(encoding="utf-8").strip())
    if courant > budget:
        print(f"BUDGET DEPASSÉ : {courant} signalements, budget {budget} (+{courant - budget})")
        print("Soit vous corrigez, soit vous assumez et lancez :")
        print("    python tools/check_lint_budget.py --update")
        return 1

    gagne = budget - courant
    print(f"lint : {courant} / budget {budget}" + (f" ({gagne} de moins)" if gagne else " — au plus juste"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
