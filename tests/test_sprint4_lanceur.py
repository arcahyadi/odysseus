"""Item 1 du Sprint 4 — un lanceur qui pose une variable que personne ne lit ne
fait rien.

Le constat avait trouvé `ODYSSEUS_DURABLE_EXEC` dans `launch_fast.py:9`, écrit
alors que le seul nom lu est `ODYSSEUS_DURABLE_EXECUTION`. Corriger cette ligne
seule aurait reproduit exactement la faute que l'item corrige :、 traiter un
symptôme en laissant sa cause, qui est « le lanceur écrit des noms qui ne
correspondent plus au code ». La mesure en a trouvé **deux autres** dans les
six lignes voisines.

Ce test porte sur la **forme** du défaut, pas sur un nom : toute variable que le
lanceur écrit doit avoir au moins un lecteur dans le code de production. C'est
ce qui le fera échouer la prochaine fois, quel que soit le nom.

Deux choix méritent d'être expliqués :

* **Analyse statique, pas exécution.** Exécuter le lanceur poserait les variables
  dans l'environnement du process ET monkey-patcherait `MCPManager` pour tout le
  reste de la session de tests. C'est exactement la fuite d'état global qui a
  déjà fait échouer `test_trace_writer_run_id` selon l'ordre de collecte. On lit
  donc le fichier sans l'exécuter — et on perd l.coroutines d'import, pas la
  garantie.

* **Le test ne vérifie pas que la valeur est `on`.** Il vérifie que le nom existe
  quelque part. Une valeur fausse sur un nom juste est un autre défaut, avec un
  autre test ; ici, le défaut mesuré est un nom qui ne mène nulle part.
"""

import ast
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
LANCEUR = REPO / "launch_fast.py"
TEST = pathlib.Path(__file__).name

# Le lecteur de reference : c'est lui qui donne le nom vrai de l'execution
# durable. On le cherche dans le code, on ne le suppose pas.
LECTEUR_DURABLE = REPO / "src/durable_execution.py"


def _variables_posees() -> dict[str, str]:
    """Les couples (variable, valeur) que le lanceur ecrit, sans l'executer."""
    arbre = ast.parse(LANCEUR.read_text(encoding="utf-8"))
    trouvees: dict[str, str] = {}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        cible = noeud.targets[0]
        if not isinstance(cible, ast.Subscript):
            continue
        conteneur = cible.value
        if not (isinstance(conteneur, ast.Attribute) and conteneur.attr == "environ"):
            continue
        cle = cible.slice
        if not (isinstance(cle, ast.Constant) and isinstance(cle.value, str)):
            continue
        valeur = noeud.value
        if isinstance(valeur, ast.Constant):
            trouvees[cle.value] = valeur.value if isinstance(valeur.value, str) else ""
    return trouvees


def _lecteurs(production: list[pathlib.Path]) -> set[str]:
    """Les variables d'environnement lues par le code de production."""
    motif = re.compile(
        r"""(?:os\.environ(?:\.get)?\(\s*["']|os\.getenv\(\s*["']|environ\[\s*["'])([A-Z][A-Z0-9_]*)"""
    )
    lues: set[str] = set()
    for p in production:
        texte = p.read_text(encoding="utf-8", errors="replace")
        lues.update(motif.findall(texte))
    return lues


@pytest.fixture(scope="module")
def production() -> list[pathlib.Path]:
    """Le code de production, tests et lanceur exclus.

    Le lanceur est exclu parce qu'il ecrit sans lire : le compter comme lecteur
    ferait dire « vivant » a une variable qu'il ne fait que repasser. Les tests
    sont exclus parce qu'un test qui pose une variable ne la fait pas vivre.
    """
    return [
        p
        for p in REPO.rglob("*.py")
        if "venv" not in p.parts
        and "node_modules" not in p.parts
        and p.relative_to(REPO).parts[0] != "tests"
        and p.name != LANCEUR.name
    ]


def test_le_lanceur_pose_des_variables_qui_existent_deja(production):
    """PREUVE : toute variable du lanceur a un lecteur dans le code.

    Le message nomme les variables mortes, parce qu'un test qui dit « ça ne va
    pas » sans dire quoi est un test qu'on corrige au hasard.
    """
    posees = _variables_posees()
    assert posees, f"aucune variable trouvee dans {LANCEUR.name} : le test mesure rien"

    lues = _lecteurs(production)
    mortes = {nom: val for nom, val in posees.items() if nom not in lues}

    assert not mortes, (
        f"{LANCEUR.name} ecrit {len(mortes)} variable(s) que rien ne lit : {sorted(mortes)} "
        f"(valeurs : {mortes}). Un lanceur qui ecrit un nom sans lecteur n'active rien ; "
        "et le jour ou le defaut de la variable change, la ligne continuera d'ecrire un "
        "nom mort en silence. Corriger : soit le nom reel existe et il faut renommer, "
        "soit aucun nom reel n'existe et il faut supprimer la ligne — surtout pas inventer "
        "un interrupteur pour de la decoration."
    )


def test_le_lanceur_et_le_module_d_execution_durable_parlent_le_meme_nom(production):
    """CONTRE-ÉPREUVE ciblée : les deux bouts du câble portent le même nom.

    Le test précédent dit « la variable a un lecteur somewhere ». Celui-ci dit
    « le lecteur et le lanceur se parlent ». Il attraperait le cas que le premier
    laisse passer : le lanceur renommerait sa variable vers un *autre* nom qui a
    lui aussi un lecteur, mais pas le bon.
    """
    posees = _variables_posees()

    lus_par_le_module = set(re.findall(r"""(?:os\.environ(?:\.get)?\(\s*["']|os\.getenv\(\s*["'])([A-Z][A-Z0-9_]*)""", LECTEUR_DURABLE.read_text(encoding="utf-8")))

    nom_du_lanceur = next((n for n in posees if "DURABLE" in n), None)
    assert nom_du_lanceur is not None, (
        f"le lanceur ne pose plus aucune variable d'execution durable : "
        f"{sorted(posees)}. soit c'est volontaire, soit il faut le dire ici."
    )

    # Les variantes historiques doivent disparaitre du lanceur.
    assert nom_du_lanceur in lus_par_le_module, (
        f"le lanceur ecrit {nom_du_lanceur!r} mais {LECTEUR_DURABLE.name} ne lit que "
        f"{sorted(lus_par_le_module)}. Le nom pose et le nom lu different : "
        "l'activation du lanceur est un no-op."
    )


def test_le_lanceur_active_bien_l_execution_durable():
    """CONTRE-ÉPREUVE de valeur : le bon nom avec la mauvaise valeur est un défaut.

    Ce test existait pas, et une mutation l'a montré : mettre `ODYSSEUS_DURABLE_EXECUTION`
    à `"off"` laissait les trois autres verts. J'avais ecrit dans le module que
    « une valeur fausse sur un nom juste est un autre défaut, avec un autre test ».
    C'etait un renvoi, pas une decision — et la mutation a montre que le trou
    etait reel.

    pourquoi la valeur compte alors que le defaut du switch est deja `on` : la
    ligne du lanceur est justement l'intention explicite. Elle est aujourd'hui
    redondante, donc invisible. Le jour ou un palier FND-4 fait basculer le
    defaut a `off`, c'est cette ligne qui doit tenir l'activation — et une ligne
    qui ecrit `off` a la coupee avant, sans bruit.
    """
    posees = _variables_posees()
    nom = next((n for n in posees if "DURABLE" in n), None)
    assert nom is not None, f"le lanceur ne pose plus de variable d'execution durable : {sorted(posees)}"

    assert posees[nom] == "on", (
        f"le lanceur pose {nom}={posees[nom]!r}. Ce lanceur sert a demarrer vite et avec "
        "tout allume : une variable d'execution durable a `off` desactive ce que le switch "
        "laisse actif par defaut. Si cette desactivation est voulue, elle doit etre ecrite "
        "ailleurs et dites ici — sinon c'est un no-op qui ressemble a un choix."
    )


def test_le_lanceur_ne_pretend_pas_regler_par_variable_ce_quil_regle_par_patch(production):
    """CONTRE-ÉPREUVE de residu : pas de variable pour un mécanisme absent.

    `MCP_CONNECT_TIMEOUT` etait pose a « 2 » pour accelerer le lanceur, alors que
    la vitesse vient du monkey-patch de `MCPManager` (lignes 15-36 du lanceur) et
    qu'aucun code ne lit cette variable. La garder et lui donner un nom « reel »
    creerait un second cable mort, cette fois avec un nom plausible — donc plus
    difficile a voir.
    """
    posees = _variables_posees()
    mon_patch = "connect_all_enabled" in LANCEUR.read_text(encoding="utf-8")

    suspectes = [n for n in posees if n.startswith("MCP_")]
    for nom in suspectes:
        assert nom not in _lecteurs(production), (
            f"{nom} est posee par le lanceur ET lue — le test de cacographie a donc change "
            "d'avis. Ne pas le supprimer sur la base de l'ancien constat : le relire."
        )

    if mon_patch:
        # Le mecanisme reel etant le patch, une variable de timeout ne peut etre
        # que du residu. On l'assert explicitement plutot que de le laisser au
        # hasard du nettoyage.
        assert not suspectes, (
            f"le lanceur regle la vitesse MCP par monkey-patch ET par variable {suspectes} : "
            "la variable ne sert a rien et pretend le contraire. Supprimez-la, ou retirez "
            "le patch — mais pas les deux."
        )
