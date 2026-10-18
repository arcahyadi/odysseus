"""§1.1 du v9 — l'exécution distante de scripts : une capacité, un interrupteur.

Une capacité d'exécution de code à distance qui existe sans interrupteur est le
genre de trou que ce chantier existe pour fermer. Le v9 tranche : interrupteur
explicite, **par défaut `off`** — pas « refléter le comportement actuel », parce
que le comportement actuel *est* le problème.

**Avant de couper quoi que ce soit, la mesure exigée** (v9 §1.1 point 2) : un
chemin de code réel utilise-t-il l'exécution distante aujourd'hui ? Trois
maillons, il faut que les trois soient ouverts.

* la capacité sait-elle exécuter à distance — `ssh <host> <script>` : oui ;
* qui appelle l'action, et d'où vient `host` — **personne ne passe `host`** ;
  le seul point d'entrée de l'action est la route de tâches, dont les actions
  d'exécution sont **admin-only** (`task_routes.py`, `_ADMIN_ONLY_ACTIONS`,
  « review CRIT-C ») ;
* un appelant externe peut-il choisir la cible — non, sauf en fixed
  `ODYSSEUS_SCRIPT_HOST`, qui est une décision d'opérateur.

**Un seul maillon ouvert : aucune exposition aujourd'hui.** Donc couper n'écôte
rien — et c'est un résultat mesuré, pas une supposition. Si le dernier maillon
s'ouvrait, il faudrait le rapporter avant de couper, pas après.

Ce que ces tests prouvent :

* la branche SSH est **refusée** par défaut, avec un motif lisible ;
* elle **fonctionne** quand l'interrupteur est explicitement mis — le switch est
  une porte, pas une suppression, donc le capacité n'est pas perdue ;
* la branche **locale** n'est pas touchée : couper l'exécution distante ne doit
  pas casser l'exécution locale, qui est une autre capacité et a sa propre garde ;
* l'interrupteur est **effectivement lu** (mutation) et **enregistré** avec un
  défaut qui correspond au code.
"""

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.builtin_actions as ba  # noqa: E402
from src.killswitch_registry import read_states  # noqa: E402

ENV = "ODYSSEUS_REMOTE_SSH"


@pytest.fixture(autouse=True)
def racine_donnees(tmp_path, monkeypatch):
    """Les tests ne doivent rien laisser sur le disque reel.

    `setenv` ne prend pas de `raising` — c'est `delenv` qui en a un. L'ecriture
    avec l'argumentwrong echouait sur une TypeError, donc le test ne
    mesurait rien du tout.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    yield


def test_une_capacite_sans_interrupteur_a_desormais_une_porte():
    """PREUVE 1 : l'interrupteur existe, au registre, et par defaut eteint.

    Le defaut suit la decision v9 : `off`, PAS « refléter le comportement
    actuel ». La distinction n'est pas de forme : une capacité d'exécution à
    distance n'a pas de comportement à préserver, elle a une exposition à fermer.
    """
    entrees = {s["env_var"]: s for s in read_states()}
    assert ENV in entrees, (
        f"{ENV} n'est pas au registre : une capacite d'execution distante sans "
        "interrupteur reste un trou, meme si le code lit une variable."
    )
    assert str(entrees[ENV]["default"]).lower() in {"off", "0", "false", "no"}, (
        f"{ENV} est a {entrees[ENV]['default']!r}. Le defaut doit etre eteint : c'est une "
        "capacite d'execution de code a distance, pas une preference."
    )
    assert entrees[ENV]["wired"] is not False, (
        f"{ENV} est marque wired=False alors que le code le lit : l'inverse de la verite, "
        "et l'item 2 du Sprint 4 a deja refuse cette confusion pour OPA."
    )


def test_le_code_agit_effectivement_sur_l_interrupteur():
    """PREUVE 2 : l'interrupteur est lu, pas declare.

    C'est la mutation M1 de l'item 2 : un interrupteur au registre dont personne
    ne lit n'est qu'une ligne de plus. On lit donc le CODE, parce que l'ordre de
    verite commence par lui.
    """
    source = (REPO / "src/builtin_actions.py").read_text(encoding="utf-8", errors="replace")

    # La constante doit porter EXACTEMENT le nom du registre. Une divergence
    # donnerait un interrupteur au tableau et une porte au code, chacun ignorant
    # l'autre — c'est-à-dire aucune porte. On verifie donc la valeur, pas la
    # presence d'une chaine.
    assert ba.REMOTE_SSH_ENV == ENV, (
        f"le code lit {ba.REMOTE_SSH_ENV!r} et le registre declare {ENV!r}. "
        "L'interrupteur du tableau et la porte du code ne se parlent pas."
    )

    # Et il doit etre lu DANS la fonction concernee, pas ailleurs dans le fichier.
    i = source.find("async def action_run_script")
    assert i != -1, "action_run_script introuvable"
    corps = source[i : i + 2000]
    assert "REMOTE_SSH_ENV" in corps, (
        "la porte est hors de action_run_script : la branche ssh n'est pas couverte."
    )
    lit = [ligne.strip() for ligne in corps.splitlines() if "REMOTE_SSH_ENV" in ligne]
    assert any('os.getenv(REMOTE_SSH_ENV, "off")' in ligne for ligne in lit), (
        "la porte ne lit pas la variable avec un defaut explicite : un defaut implicite "
        f"pourrait valoir « actif » et la porte serait une illusion. Ce qui est lu : {lit}"
    )


@pytest.mark.asyncio
async def test_la_branche_ssh_est_refusee_par_defaut(monkeypatch):
    """PREUVE 3 : par defaut, la branche distante est fermee et elle le dit.

    Un refus muet est le pire des deux : l'appelant croit avoir obtenu une
    execution, et rien ne le prouve. Le motif est donc rendu, avec l'interrupteur
    nomme, pour que l'appel puisse dire *pourquoi*.
    """
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setenv("ODYSSEUS_SCRIPT_HOST", "serveur-de-prod.example")

    sortie, ok = await ba.action_run_script(owner="admin", script="echo bonjour")

    assert not ok, "l'execution distante a reussi sans que l'interrupteur soit mis"
    assert ENV in sortie or "distant" in sortie.lower(), (
        f"le refus ne nomme ni l'interrupteur ni la distance : {sortie!r}. "
        "Un appelant ne peut pas rapporter une cause qu'il n'a pas."
    )


@pytest.mark.asyncio
async def test_la_branche_locale_n_est_pas_touchee(monkeypatch):
    """PREUVE 4 : couper l'execution distante ne casse pas l'execution locale.

    Ce sont deux capacites differentes, avec des gardes differentes. Si le meme
    interrupteur fermait les deux, on aurait coupe de l'execution locale
    pendant qu'on croyait ne couper que de la distance.
    """
    monkeypatch.delenv(ENV, raising=False)
    appel = {"n": 0}

    async def _faux(*args, **kwargs):
        appel["n"] += 1
        return "local", True

    monkeypatch.setattr(ba, "_run_subprocess", _faux)

    sortie, ok = await ba.action_run_script(owner="admin", script="echo bonjour")

    assert ok, f"l'execution LOCALE a ete refusee par l'interrupteur distant : {sortie!r}"
    assert appel["n"] == 1, f"le sous-processus local n'a pas ete appele ({appel['n']})"


@pytest.mark.asyncio
async def test_la_capacite_nest_pas_supprimee_mais_ouverte_explicitement(monkeypatch):
    """PREUVE 5 : le switch est une PORTE, pas une suppression.

    Une capacité qu'on efface au lieu de la doree n'est plus gouvernable : le
    jour ou on la veut, il faut la reecrire. Une porte s'ouvre avec une variable.
    Ce test le prouve en ouvrant reellement la porte.
    """
    monkeypatch.setenv(ENV, "on")
    monkeypatch.setenv("ODYSSEUS_SCRIPT_HOST", "cible-de-test.example")
    argv: list = []

    async def _faux(argv_liste, *args, **kwargs):
        argv.extend(argv_liste)
        return "distante", True

    monkeypatch.setattr(ba, "_run_subprocess", _faux)

    sortie, ok = await ba.action_run_script(owner="admin", script="echo bonjour")

    assert ok, f"la porte refusee alors que {ENV}=on : {sortie!r}"
    assert argv and argv[0] == "ssh", f"la commande construite n'est pas un ssh : {argv!r}"
    assert "cible-de-test.example" in argv, f"la cible n'est pas celle demandee : {argv!r}"


def test_personne_ne_passe_de_cible_a_l_action():
    """CONTRE-ÉPREUVE de la mesure prealable : le troisieme maillon est ferme.

    Le v9 impose de verifier l'usage reel **avant** de couper. Ce test est cette
    verification, et elle est faite mecaniquement plutot que par relecture : si
    quelqu'un ajoute un `host=` a un appel, il tombe ici — donc la prochaine
    revision de la decision partira d'un fait, pas d'un souvenir.
    """
    prod = [
        p
        for p in REPO.rglob("*.py")
        if "venv" not in p.parts
        and "node_modules" not in p.parts
        and p.relative_to(REPO).parts[0] != "tests"
    ]
    coupables = []
    for p in prod:
        t = p.read_text(encoding="utf-8", errors="replace")
        for nom in ("run_script", "ssh_command"):
            for i, ligne in enumerate(t.split("\n"), 1):
                if f'"{nom}"' not in ligne and f"'{nom}'" not in ligne:
                    continue
                fenetre = "\n".join(t.split("\n")[i - 1 : i + 6])
                if re.search(r"\bhost\s*[:=]", fenetre):
                    coupables.append(f"{p.relative_to(REPO)}:{i} ({nom})")
    assert not coupables, (
        f"un appelant passe desormais une cible a une action d'execution : {coupables}. "
        "L'execution distante n'est plus dormante : elle est UTILISEE. Il faut le "
        "rapporter au Chef avant de la couper, pas la couper en silence."
    )


def test_les_actions_d_execution_restent_admin_only():
    """CONTRE-ÉPREUVE de la seconde porte : l'admin-only existe toujours.

    Fermer l'exécution distante ne dispense pas de la garde de propriétaire sur
    l'exécution locale. Les deux portes sont indépendantes, et ce test verrouille
    la seconde pendant qu'on installe la première.
    """
    tr = (REPO / "routes/task_routes.py").read_text(encoding="utf-8", errors="replace")
    assert "_ADMIN_ONLY_ACTIONS" in tr, (
        "la liste des actions reservees aux administrateurs a disparu de task_routes.py : "
        "l'execution locale serait de nouveau accessible a un non-administrateur."
    )
    for nom in ("run_script", "run_local", "ssh_command"):
        assert f'"{nom}"' in tr, f"{nom} n'est plus dans la liste admin-only"
