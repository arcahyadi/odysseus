"""Sprint 3 v5 §2.1 — la fenêtre de pré-installation bride l'admin, et c'est voulu.

Décision arbitrée
-----------------
Un owner littéral ``"admin"`` reste bridé tant que l'auth n'est pas réellement configurée.
C'est le comportement sûr : avant la fin du setup, une simple chaîne ne doit pas
obtenir `bash`/`python`. Le docstring de `owner_is_admin_or_single_user`
(`src/tool_security.py:203-207`) le pose déjà en defense-in-depth.

Ce fichier verrouille ce comportement pour qu'une régression future soit attrapée. Ce
n'est pas une décision de politique nouvelle : c'est un test sur une politique déjà
arbitrée, donc il n'a pas de quoi être escaladé.

Pourquoi ce test existe malgré tout
------------------------------------
Une mesure antérieure avait conclu que ``blocked_tools_for_owner`` était insensible à
l'owner — mêmes 38 outils pour ``None``, un utilisateur et ``"admin"``. C'était FAUX, et
la cause était instructive : l'environnement de mesure avait ``is_configured == False``,
donc **tout le monde** était bridé, ``"admin"`` compris. Le faux ticket est parti de là.

Ce test fixe les trois états distincts pour que la prochaine personne qui mesure ne
confonde plus « bridé parce que non-admin » et « bridé parce que pré-installation ».
"""

import importlib

import pytest

from src.tool_security import blocked_tools_for_owner, owner_is_admin_or_single_user

HIGH_RISK = ("bash", "python", "edit_file", "write_file", "api_call", "serve_model")


@pytest.fixture
def auth_state(monkeypatch):
    """Force l'état d'auth et garantit qu'on n'est PAS en mono-utilisateur.

    `AUTH_ENABLED=false` est le mode mono-utilisateur : l'opérateur a explicitement
    désactivé l'auth, donc le propriétaire de la machine a tous les droits. Il ne faut
    pas le confondre avec la fenêtre de pré-installation, où l'auth est *activée* mais
    aucun admin n'existe. On épingle donc `AUTH_ENABLED` à autre chose que `false` dans
    tous les tests de ce fichier.
    """
    monkeypatch.setenv("AUTH_ENABLED", "true")
    return monkeypatch


def _set_configured(monkeypatch, configured: bool, admins=("admin",)):
    """Patche le **site de liaison** `core.auth.AuthManager`, pas la classe.

    C'est la seule forme qui ne dépend pas de l'ordre d'exécution, et ce n'est pas un
    détail. `tests/test_auth_regressions.py::_ensure_stub` remplace
    `sys.modules["core.auth"]` par un module `types.ModuleType` pour toute la durée de la
    session. La production fait `from core.auth import AuthManager` **au moment de
    l'appel**, donc elle voit ce stub ; patcher l'objet classe réellement importé ne
    changeait donc rien, et mes deux tests « admin configuré » échouaient en suite
    complète alors qu'ils passaient isolément.

    `importlib.import_module` est relu ici au moment du patch : c'est exactement
    l'objet que la fonction de production va résoudre, stub compris.
    """
    admins = set(admins)

    class _Auth:
        is_configured = configured

        def is_admin(self, owner):
            return owner in admins

    core_auth = importlib.import_module("core.auth")
    monkeypatch.setattr(core_auth, "AuthManager", _Auth, raising=False)


# ─── L'état arbitré : pré-installation ⇒ admin bridé ───────────────────────


def test_a_literal_admin_stays_brutalised_while_auth_is_unconfigured(auth_state):
    """`owner="admin"` n'obtient rien tant qu'aucun admin réel n'existe.

    C'est l'état qu'un environnement de dev frais produit par défaut, et c'est celui qui a fait
    naître le faux ticket : sans ce test, la prochaine mesure peut redevenir « bridé
    pour tout le monde » et être lue comme un bug de permissions.
    """
    _set_configured(auth_state, False)

    assert owner_is_admin_or_single_user("admin") is False, (
        "une chaîne littérale ne doit pas valoir admin avant la fin du setup"
    )
    blocked = blocked_tools_for_owner("admin")
    assert blocked, "la fenêtre de pré-installation doit brider, pas autoriser"
    for tool in HIGH_RISK:
        assert tool in blocked, f"{tool} doit être bridé en pré-installation"


def test_the_pre_setup_window_blocks_exactly_like_any_other_non_admin(auth_state):
    """En pré-installation, `"admin"` et un utilisateur quelconque sont traités pareil.

    C'est la propriété qui rend l'état lisible : il n'existe pas de troisième cas
    « à moitié admin ». Un owner absent et un owner admin obtiennent le même ensemble.
    """
    _set_configured(auth_state, False)

    assert blocked_tools_for_owner("admin") == blocked_tools_for_owner("user-x") == blocked_tools_for_owner(None)


# ─── Contre-épreuves : les deux autres états ne sont pas concernés ─────────


def test_a_configured_admin_is_not_brutalised(auth_state):
    """Contre-épreuve : une fois l'auth configurée, l'admin passe.

    Sans ce test, un fail-closed excessif (tout refusé en permanence) satisferait le test
    précédent et rendrait le système inutilisable.
    """
    _set_configured(auth_state, True, admins=("admin",))

    assert owner_is_admin_or_single_user("admin") is True
    assert blocked_tools_for_owner("admin") == set(), "l'admin configuré doit avoir la surface complète"


def test_a_configured_non_admin_is_still_brutalised(auth_state):
    """Contre-épreuve du bon côté : l'auth configurée ne doit rien relâcher au hasard."""
    _set_configured(auth_state, True, admins=("admin",))

    blocked = blocked_tools_for_owner("user-x")
    assert blocked, "un non-admin doit rester bridé, même auth configurée"
    for tool in HIGH_RISK:
        assert tool in blocked, f"{tool} doit rester bridé pour un non-admin"


def test_single_user_mode_is_not_the_pre_setup_window(auth_state, monkeypatch):
    """`AUTH_ENABLED=false` ouvre tout : c'est mono-utilisateur, pas pré-installation.

    La confusion entre les deux est exactement ce qui a produit le faux ticket, donc elle
    est testée explicitement dans les deux sens.
    """
    _set_configured(auth_state, False)
    monkeypatch.setenv("AUTH_ENABLED", "false")

    assert owner_is_admin_or_single_user("user-x") is True, (
        "en mono-utilisateur, le propriétaire de la machine n'est pas bridé"
    )
    assert blocked_tools_for_owner("user-x") == set()


def test_the_three_states_are_really_three(auth_state):
    """Propriété de non-régression : les trois états donnent trois résultats distincts.

    Si deux de ces trois lignes devenaient identiques, la porte aurait perdu sa
        structure — et c'est cette structure, pas une valeur ponctuelle, qui protège.
    """
    _set_configured(auth_state, False)
    pre_setup = len(blocked_tools_for_owner("admin"))

    _set_configured(auth_state, True, admins=("admin",))
    configured_admin = len(blocked_tools_for_owner("admin"))

    _set_configured(auth_state, True, admins=("someone-else",))
    configured_other = len(blocked_tools_for_owner("admin"))

    assert pre_setup == configured_other, "pré-installation et non-admin doivent coïncider"
    assert configured_admin == 0, "l'admin configuré ne doit pas être bridé"
    assert pre_setup > configured_admin, (
        "bridé et non bridé doivent rester deux résultats distincts, sinon la porte est inerte"
    )
