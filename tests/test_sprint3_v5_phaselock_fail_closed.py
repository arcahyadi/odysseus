"""Sprint 3 v5 §1 — le phase-lock doit échouer **fermé**, jamais ouvert.

Le défaut
---------
`ToolRegistry._load_config` (`src/tool_registry.py`) retombait, sur **trois** échecs
différents, sur `{"phases": {"BUILD": {"blocked_tools": []}}}` : un registre où plus rien
n'est jamais bloqué. Le `logger.warning` ne couvrait que les exceptions — un fichier
simplement *absent* ne journalisait rien. Le mode dégradé était donc entièrement
silencieux, et il dégradait un contrôle de gouvernance vers le permissif.

Pire : le chemin était **relatif au CWD** et le résultat figé dans un singleton à durée
de vie de process. Le premier appel sous un mauvais CWD désactivait le phase-lock pour
toutes les requêtes suivantes. C'est cet effet-là qui faisait dépendre 3 tests UC-05 de
l'ordre d'exécution (ils passaient « par chance d'ordre »).

Pourquoi le refus passe par la valeur de retour, pas par une exception
---------------------------------------------------------------------
L'option « refuser de démarrer en levant » a été **mesurée** avant d'être écartée, et
elle est dangereuse ici : le seul appelant (`src/tool_execution.py:625`) est enveloppé
dans `except Exception: pass` — « Ne jamais bloquer le loop sur une erreur de phase-lock ».
Une exception serait donc avalée et l'outil s'exécuterait : un fail-**open**, exactement
le défaut corrigé. Le test `test_the_refusal_cannot_be_swallowed_into_a_permission`
verrouille cette propriété : le registre refuse, il ne lève pas.

Ce que ces tests ne prétend pas
-------------------------------
Ils ne testent pas le contenu de `config/phase-lock.yaml` — seulement le comportement
du registre **quand ce fichier est absent, malformé, ou cherché depuis un autre CWD**.
Le contenu lui-même est vérifié par les tests de phase-lock existants.
"""

import logging

import pytest
import yaml

from src.tool_registry import ToolRegistry

SESSION = "sess-failclosed"

# Y compris un outil typiquement en lecture : un filet de sécurité « tout sauf lecture »
# aurait laissé passer read_file, et le test ne le verrait pas. On vérifie donc que le
# refus est total, pas seulement directed contre les outils catchy.
READ_ONLY_PROBE = "read_file"


@pytest.fixture
def registry(monkeypatch):
    """Registre neuf à chaque test — le singleton est deliberately reconstruit.

    On neutralise `__repr__` : il fait du réseau (`src/tool_registry.py`, `is_available`
    → `_check_port` → `socket.create_connection`), et pytest le construit pour le message
    d'un assert en échec. Un test qui échoue légitimement se mettrait à bloquer sur un
    `getaddrinfo`.
    """
    monkeypatch.setattr(ToolRegistry, "__repr__", lambda self: "<ToolRegistry>")
    monkeypatch.setattr(ToolRegistry, "_instance", None, raising=False)
    return ToolRegistry()


def _malformed(path):
    path.write_text("phases: [unclosed\n  - x: {", encoding="utf-8")
    return str(path)


# ─── Cas 1 exigé : fichier absent ──────────────────────────────────────────


def test_an_absent_phase_lock_refuses_every_tool(registry, tmp_path):
    """PREUVE DE FIN : fichier absent ⇒ plus rien n'est autorisé, lecture comprise."""
    registry = ToolRegistry(config_path=str(tmp_path / "absent.yaml"))

    assert registry.phase_lock_loaded is False, "l'absence du fichier n'a pas été vue comme un échec"

    for tool in ("bash", "edit_file", "api_call", READ_ONLY_PROBE, "ask_user"):
        decision = registry.is_tool_allowed(tool, SESSION)
        assert decision["allowed"] is False, f"{tool} a été autorisé alors que le phase-lock est absent"


def test_the_refusal_names_the_control_that_failed(registry, tmp_path):
    """Un refus muet est un refus que personne ne peut diagnostiquer.

    Le motif doit nommer le contrôle et l'outil, sinon l'utilisateur voit « bloqué » sans
    savoir que c'est le phase-lock entier qui est tombé, ni comment le réparer.
    """
    registry = ToolRegistry(config_path=str(tmp_path / "absent.yaml"))
    reason = registry.is_tool_allowed("bash", SESSION)["reason"]

    assert "phase-lock" in reason, f"le motif ne nomme pas le contrôle : {reason!r}"
    assert "bash" in reason, f"le motif ne nomme pas l'outil refusé : {reason!r}"


# ─── Cas 2 exigé : fichier malformé ────────────────────────────────────────


def test_a_malformed_phase_lock_refuses_every_tool(registry, tmp_path):
    """PREUVE DE FIN : YAML invalide ⇒ refus total, pas de repli permissif."""
    registry = ToolRegistry(config_path=_malformed(tmp_path / "bad.yaml"))

    assert registry.phase_lock_loaded is False, "un YAML invalide a été accepté comme une configuration"
    for tool in ("bash", "edit_file", READ_ONLY_PROBE):
        assert registry.is_tool_allowed(tool, SESSION)["allowed"] is False, (
            f"{tool} a été autorisé sur un phase-lock malformé"
        )


@pytest.mark.parametrize(
    "contenu, raison",
    [
        ("default_phase: BUILD\n", "aucune phase déclarée"),
        ("- a\n- b\n", "racine liste au lieu d'un dict"),
        ("", "fichier vide"),
        ("phases: 12\n", "phases n'est pas une table"),
    ],
)
def test_a_config_without_usable_phases_is_refused(registry, tmp_path, contenu, raison):
    """Un fichier lisible mais vide de sens est un échec, pas une permission.

    `yaml.safe_load` renvoie `None` sur un fichier vide et un scalaire sur une racine
    scalaire : sans ce contrôle, `_config` devenait `None`/un int et le premier `.get()`
    appelé plus tard levait une `AttributeError` — attrapée, elle aussi, par
    `except Exception: pass` de l'appelant. Le refus doit être explicite et anticipé.
    """
    path = tmp_path / "cas.yaml"
    path.write_text(contenu, encoding="utf-8")
    registry = ToolRegistry(config_path=str(path))

    assert registry.phase_lock_loaded is False, f"config sans phase exploitable acceptée ({raison})"
    assert registry.is_tool_allowed(READ_ONLY_PROBE, SESSION)["allowed"] is False


# ─── Cas 3 exigé : CWD différent ───────────────────────────────────────────


def test_the_lock_is_found_whatever_the_working_directory(registry, tmp_path, monkeypatch):
    """PREUVE DE FIN : le phase-lock ne dépend pas du CWD du process.

    C'est la cause racine de la pollution d'ordre : le registre était construit une
    fois, sous le CWD du premier appelant, et le résultat figeait pour tout le process.
    """
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()

    assert registry.phase_lock_loaded is True, (
        f"le phase-lock n'a pas été trouvé depuis {tmp_path} : "
        f"config_path={registry._config_path}"
    )
    registry.set_phase(SESSION, "PLAN")
    assert registry.is_tool_allowed("bash", SESSION)["allowed"] is False, (
        "le verrou est chargé mais n'applique rien : le path ancré charge autre chose"
    )


def test_the_singleton_survives_a_working_directory_change(registry, tmp_path, monkeypatch):
    """Un singleton déjà construit puis un CWD changé : le verrou ne se dégrade pas.

    Sans ce test, un registre construit sous un mauvais CWD pouvait fixer un
    ``_config`` vide pour toutes les requêtes suivantes du process.
    """
    first = ToolRegistry.get_instance()
    assert first.phase_lock_loaded is True

    monkeypatch.chdir(tmp_path)
    again = ToolRegistry.get_instance()

    assert again.phase_lock_loaded is True
    again.set_phase(SESSION, "PLAN")
    assert again.is_tool_allowed("bash", SESSION)["allowed"] is False


# ─── La propriété qui rend le refus sûr ────────────────────────────────────


def test_the_refusal_cannot_be_swallowed_into_a_permission(registry, tmp_path):
    """Le registre doit REFUSER, jamais lever.

    L'appelant unique (`src/tool_execution.py:625`) est sous `except Exception: pass` :
    une exception deviendrait une permission. Ce test est la preuve de bout en bout que
    le chemin.fail-closed ne dépend pas de la bonne volonté de l'appelant.
    """
    registry = ToolRegistry(config_path=str(tmp_path / "absent.yaml"))
    try:
        decision = registry.is_tool_allowed("bash", SESSION)
    except Exception as exc:  # noqa: BLE001 — l'assertion porte sur l'absence d'exception
        pytest.fail(f"is_tool_allowed a levé {type(exc).__name__} : l'appelant l'avalerait en permission")

    assert decision["allowed"] is False


def test_a_critical_is_logged_so_the_degradation_is_visible(registry, tmp_path, caplog):
    """Le mode dégradé doit être visible. Le défaut d'origine était doublement muet.

    Avant, l'absence du fichier ne journalisait rien **et** n'empêchait aucune autorisation.
    """
    with caplog.at_level(logging.CRITICAL, logger="src.tool_registry"):
        ToolRegistry(config_path=str(tmp_path / "absent.yaml"))

    records = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    assert records, "aucun log critique : la dégradation resterait invisible"
    assert "PHASE-LOCK" in records[0].getMessage()


def test_the_indicator_can_be_read_by_a_cockpit(registry, tmp_path):
    """`phase_lock_loaded` est l'indicateur exposé : faux quand le contrôle est mort.

    Sans lui, un opérateur ne peut pas distinguer « le verrou bloque rightly » de
    « le verrou est cassé et refuse tout » — deux situations opposées qui se ressemblent
    depuis l'UI.
    """
    assert ToolRegistry().phase_lock_loaded is True
    assert ToolRegistry(config_path=str(tmp_path / "absent.yaml")).phase_lock_loaded is False


# ─── Contre-épreuve : le mode normal n'a pas été cassé ──────────────────────


def test_the_real_config_still_blocks_and_still_allows(registry):
    """Contre-épreuve : fail-closed ne veut pas dire « tout refusé en permanence ».

    Sans ce test, une régression qui refuse tout passerait quand même les cas 1-3, et le
    systeme deviendrait inutilisable. On vérifie donc les DEUX sens sur le vrai fichier :
    `bash` bloqué en PLAN, autorisé en BUILD.
    """
    registry.set_phase(SESSION, "PLAN")
    assert registry.is_tool_allowed("bash", SESSION)["allowed"] is False

    registry.set_phase(SESSION, "BUILD")
    assert registry.is_tool_allowed("bash", SESSION)["allowed"] is True, (
        "BUILD doit continuer à autoriser bash : le fail-closed a déborde sur le mode nominal"
    )


def test_the_real_config_is_actually_parsed(registry):
    """Le fichier ancré est bien le nôtre, phases comprises — pas un dict vide."""
    registry = ToolRegistry()
    assert registry.phase_lock_loaded is True
    assert set(registry._config.get("phases", {})) >= {"PLAN", "BUILD", "CLASSIFY"}
    assert registry._config_path.name == "phase-lock.yaml"
    assert registry._config_path.is_absolute(), "le chemin doit être ancré, donc absolu"


def test_the_decision_tree_index_stays_best_effort(registry, tmp_path):
    """Contre-épreuve de portée : l'index de capacités n'est pas un contrôle d'accès.

    Un index de briques vide ne rend aucun outil plus powerful — il rend un outil non
    découvert. On ne doit donc pas le confondre avec le phase-lock et bloquer le process
    pour autant. Ce test verrouille que les deux traitements restent distincts.
    """
    registry = ToolRegistry(brick_path=str(tmp_path / "absent-bricks.yaml"))

    assert registry.phase_lock_loaded is True, "l'absence du decision tree ne doit pas armer le phase-lock"
    registry.set_phase(SESSION, "PLAN")
    assert registry.is_tool_allowed("bash", SESSION)["allowed"] is False, (
        "le phase-lock doit continuer à s'appliquer même sans index de briques"
    )


def test_a_yaml_file_that_is_only_comments_is_refused(registry, tmp_path):
    """Un fichier dont tout le contenu est un commentaire se parse en ``None``.

    Sans test, ``_config`` valait ``None`` et le premier `.get()` levait une
    `AttributeError` — avalée par l'appelant, donc convertie en permission.
    """
    path = tmp_path / "commentaires.yaml"
    path.write_text("# phase-lock\n# tout est commente\n", encoding="utf-8")
    registry = ToolRegistry(config_path=str(path))

    assert registry.phase_lock_loaded is False
    assert yaml.safe_load(path.read_text(encoding="utf-8")) is None, "la preuve du test : ce YAML vaut None"
    assert registry.is_tool_allowed(READ_ONLY_PROBE, SESSION)["allowed"] is False
