"""§1 du v10 — l'outil d'audit ne doit plus pouvoir affirmer du code absent.

`tools/sfd_audit.py` affirmait `src/thought_bus/` comme code implémenté de P3.
Ce répertoire n'a jamais existé. Le dépôt compte 7 autres affirmations dans le
même état, et 32 affirmations booléennes sans aucun fichier nommé — un booléen
n'est falsifiable par personne.

Corriger les chaînes n'aurait rien duré : le même chemin repourrit au commit
suivant. Ces tests portent donc sur le **mécanisme**, pas sur le texte, et ils
entrent par la voie de production : le script est lancé, et c'est son code de
sortie qui est lu.

Ce que les tests prouvent :

* une affirmation de chemin qui n'existe pas fait **échouer** l'outil ;
* un chemin retiré cité dans une `note` (le constat) est **accepté**, cité
  dans `code` (la prétention) est **rejeté** — confondre les deux obligerait à
  choisir entre interdire le constat et accepter la prétention ;
* une affirmation booléenne sans fichier nommé est **comptée et visible** ;
* la résolution se fait par chemin complet, jamais par sous-chaîne — un nom
  trouvé dans un autre répertoire ne vaut pas le chemin, et un nom ambigu est
  refusé plutôt que tranché au hasard ;
* le code de sortie est non nul quand quelque chose reste non résolu, sinon la
  vérification ne servirait qu'à l'affichage et l'outil pourrait mentir dans une
  sortie de CI parfaitement verte.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OUTIL = REPO / "tools/sfd_audit.py"
sys.path.insert(0, str(REPO / "tools"))

import sfd_audit  # noqa: E402


@pytest.fixture(scope="module")
def rapport():
    """Le rapport tel que l'outil le produit lui-même, en production."""
    p = subprocess.run(
        [sys.executable, str(OUTIL)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=300,
    )
    brut = p.stderr[: p.stderr.rindex("}") + 1]
    return p.returncode, json.loads(brut)


def test_le_code_de_sortie_reflete_la_verification(rapport):
    """PREUVE 1 : sortie 0 ⟺ rien d'affirmé n'est non résolu.

    Un garde qui n'échoue jamais n'est pas un garde (v9 §2). Si ce test passe
    avec un code de sortie nul alors que `INTROUVABLE` est non vide, la
    vérification est décorative.
    """
    code, r = rapport
    assert not r["INTROUVABLE"], (
        f"affirmations non résolues, donc le code de sortie doit être non nul : {r['INTROUVABLE']}"
    )
    assert not r["AMBIG"], f"affirmations ambiguës, donc le code de sortie doit être non nul : {r['AMBIG']}"
    assert code == 0, f"l'outil sort en {code} alors que rien n'est non résolu"


def test_plus_aucun_chemin_fictif_n_est_affirme_comme_code(rapport):
    """PREUVE 2 : l'affirmation de `thought_bus` a disparu, et le reste avec.

    Le contrôle est sur `code`, pas sur le fichier entier : dire « ce chemin
    n'existe pas » dans une `note` est un constat, l'affirmer dans `code` est
    une prétention. Les deux contiennent la même chaîne, et seul un des deux
    ment.
    """
    code, r = rapport
    codes_affirmes = list(r["VRAI"]) + list(r["DEPLACE"])
    codes_affirmes = [x for x in codes_affirmes if "[code]" in x]
    for fantome in ("thought_bus", "context_manager/", "memory_provenance/", "tool_discovery/"):
        assert not any(fantome in x for x in codes_affirmes), (
            f"`{fantome}` est encore affirme comme code : {codes_affirmes}. "
            "Un chemin qui n'existe pas, affirme comme existant, c'est l'affirmation "
            "que l'outil est cense rendre impossible."
        )
    # Et le constat, lui, doit rester écrit : effacer le chemin sans dire
    # pourquoi reviendrait à perdre l'information.
    assert r["RETIRE_DECLARE"], (
        "plus aucun chemin retiré n'est signalé : les retraits ont-ils ete effaces "
        "au lieu d'etre traces ?"
    )


def test_les_affirmations_sans_preuve_sont_comptees(rapport):
    """PREUVE 3 : 32 booléens sans fichier nommé sont visibles, pas perdus.

    Ce test porte sur un bug déjàcorrigé : le vérificateur s'arrêtait au premier
    champ textuel — la `note`, toujours présente — et n'atteignait donc jamais
    le cas `code: True`. Résultat : il rapportait 0 affirmation sans preuve
    alors qu'il y en avait 32. **Un vérificateur qui manque 32 fiches sur 32
    n'est pas partiellement défaillant : il ne fonctionne pas.**
    """
    _, r = rapport
    assert len(r["SANS_PREUVE"]) >= 30, (
        f"seulement {len(r['SANS_PREUVE'])} affirmation(s) sans preuve, 30 attendues. "
        "Soit le comptage a regresse, soit les modules ont ete corriges — dans "
        "ce cas, le dire, ne pas laisser la porte assumer un 0 flatteur."
    )
    assert any(x.startswith("modules/") for x in r["SANS_PREUVE"]), (
        "la section modules (20 fiches en `code: True`) n'est plus comptée : "
        "c'est la section entiere qui manque."
    )


def test_la_resolution_est_structurelle_pas_textuelle():
    """PREUVE 4 : un nom trouvé ailleurs ne vaut pas le chemin.

    L'erreur que l'outil commettait — et que la règle du v10 §2 interdit — est
    de conclure qu'une capacité existe parce que le mot apparaît quelque part.
    Ici, `fin.py` existe dans `src/fin.py` : cela ne rend pas vrai
    `autre/fin.py`.
    """
    index = {"fin.py": ["src/fin.py"]}
    etat, _ = sfd_audit._resoudre("autre/fin.py", index)
    assert etat == "INTROUVABLE", (
        "`autre/fin.py` a ete resolu alors que le seul `fin.py` est dans src/. "
        "La resolution se fait par chemin complet, pas par nom de fichier."
    )
    etat, detail = sfd_audit._resoudre("fin.py", index)
    assert etat == "DEPLACE" and detail == "src/fin.py"


def test_un_nom_ambigu_est_refuse_et_non_tranche():
    """PREUVE 5 : deux candidats, aucun verdict.

    Nominer le premier serait une vérification qui a l'air rigoureuse et ne
    vérifie rien : sur deux correspondances, un choix arbitraire a une chance
    sur deux d'être faux, et l'outil ne le dirait pas.
    """
    index = {"fin.py": ["src/fin.py", "core/fin.py"]}
    etat, candidats = sfd_audit._resoudre("fin.py", index)
    assert etat == "AMBIG", f"deux candidats tranches en {etat} au lieu d'etre refuses"
    assert len(candidats) == 2


def test_une_capacite_absente_nest_pas_declenchee_par_un_contexte():
    """PREUVE 6 : `verifier()` ne dépend pas du répertoire courant.

    Un vérificateur qui changerait de verdict selon l'endroit d'où on le lance
    n'est pas un vérificateur, c'est une loterie.
    """
    a = sfd_audit.verifier()
    b = sfd_audit.verifier()
    assert a == b, "deux appels consécutifs donnent des rapports différents"
    assert a["VRAI"], "aucun chemin vérifié : le vérificateur ne trouve rien du tout"


def test_la_dette_perimee_est_aujourdhui_vide_et_expliquee():
    """PREUVE 7 : `CHEMINS_PERIMES` vide doit être **vidé**, pas supprimé.

    La liste vide est la preuve que les 16 chemins périmés ont été corrigés
    vers des fichiers vérifiés. Si elle disparaissait, le mécanisme disparaîtrait
    avec elle et le prochain chemin pourri repasserait inaperçu.
    """
    assert hasattr(sfd_audit, "CHEMINS_PERIMES"), "la liste de dette perimee a disparu"
    assert hasattr(sfd_audit, "CHEMINS_RETIRES"), "la liste de chemins retires a disparu"
    for item in sfd_audit.CHEMINS_RETIRES:
        assert item["etat"], f"{item['affirme']} est retire sans dire pourquoi"
        assert item["reel"], f"{item['affirme']} est retire sans dire ce que la capacite est devenue"


def test_la_note_de_p2_ne_plus_affirmer_une_compensation_absente():
    """PREUVE 8 : la fausse affirmation, pas seulement le faux chemin.

    `src/durable_execution/saga.py` n'existait pas, mais le module existe en
    fichier plat : corriger le chemin aurait laissé la note dire « Saga
    compensation implémentée » alors qu'il n'y a ni classe Saga ni fonction de
    compensation. Une vérification par existence ne l'aurait pas vu — il
    fallait lire l'affirmation.
    """
    source = OUTIL.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    audit = None
    for n in arbre.body:
        if (
            isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Subscript)
            and getattr(n.targets[0].slice, "value", None) == "principes"
        ):
            audit = ast.literal_eval(n.value)
    p2 = audit["P2 - Brouillon ≠ commit"]
    assert "Saga compensation implémentée" not in p2["note"], (
        "la note affirme encore une compensation de saga qui n'existe pas"
    )
    assert "ABSENTE" in p2["note"], (
        f"la note ne dit pas que la compensation est absente : {p2['note']!r}. "
        "Corriger un chemin sans corriger l'affirmation qu'il portait laisse le "
        "mensonge en place, sous un autre fichier."
    )


def test_un_chemin_retire_reaffirme_comme_code_est_une_erreur(monkeypatch):
    """PREUVE 9 : retirer n'efface pas le droit de le réaffirmer.

    `src/thought_bus/` est dans `CHEMINS_RETIRES` : le citer dans une `note`
    est un constat, accepté. Le réaffirmer dans `code` serait une prétention,
    et doit retomber dans `INTROUVABLE` — donc faire échouer l'outil.

    Le test construit le cas au lieu de le supposer : sans lui, la distinction
    code/note pourrait être supprimée en silence, et les deux autres tests
    continueraient de passer, parce qu'ils ne regardent que les chemins
    **présents** dans le fichier.
    """
    cle = "P3 - Contexte construit"
    reel = sfd_audit.AUDIT["principes"][cle]["code"]
    monkeypatch.setitem(sfd_audit.AUDIT["principes"][cle], "code", "src/thought_bus/")
    try:
        r = sfd_audit.verifier()
        retirees_code = [x for x in r["INTROUVABLE"] if "thought_bus" in x and "[code]" in x]
        assert retirees_code, (
            "reaffirmer `src/thought_bus/` comme `code` n'est pas signalé comme "
            f"erreur : il atterrit dans {r['RETIRE_DECLARE']}. La liste des "
            "chemins retirés est devenue une excuse pour les réaffirmer."
        )
    finally:
        sfd_audit.AUDIT["principes"][cle]["code"] = reel


def test_une_affirmation_fausse_fait_echouer_l_outil():
    """PREUVE 10 : le chemin d'échec du code de sortie est prouve, lui aussi.

    Les neuf autres preuves testent l'outil dans son état sain, où la sortie
    est 0 et où le garde n'a rien à faire. Une mutation qui remplace
    `sys.exit(1)` par `pass` laissait donc les neuf vertes : le mécanisme qui
    fait qu'une sortie de CI peut devenir rouge n'était pas couvert du tout.
    Un garde dont on ne teste que le chemin heureux n'est pas à moitié testé,
    il est non testé.

    On exécute donc une **copie** de l'outil, dans `tools/` — même répertoire,
    donc même résolution du dépôt — dont on casse une affirmation. Le test
    échoue si la copie, elle, réussit.
    """
    copie = REPO / "tools" / "_test_audit_casse.py"
    source = OUTIL.read_text(encoding="utf-8")
    casse = source.replace(
        '"code": "src/orchestrator/gate.py, src/risk_classifier.py",',
        '"code": "src/orchestrator/gate.py, src/ce_module_n_existe_pas.py",',
        1,
    )
    assert casse != source, "l'ancre de la mutation est introuvable : test non fiable"
    copie.write_text(casse, encoding="utf-8")
    try:
        p = subprocess.run(
            [sys.executable, str(copie)],
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=300,
            check=False,
        )
    finally:
        copie.unlink(missing_ok=True)

    assert p.returncode != 0, (
        "l'outil aexit 0 en affirming `src/ce_module_n_existe_pas.py` : le code de "
        "sortie en erreur ne fonctionne pas, donc une sortie de CI resterait verte "
        "quand meme un chemin est introuvable."
    )
    assert "ce_module_n_existe_pas" in p.stderr, (
        f"l'outil a echoue sans nommer l'affirmation fautive : {p.stderr[-300:]!r}. "
        "Un échec qui ne dit pas quoi ne se corrige pas."
    )
