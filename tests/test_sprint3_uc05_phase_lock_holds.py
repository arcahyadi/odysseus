"""Sprint 3 — item 5 : UC-05 « la phase posée par l'API tient jusqu'à ce qu'on la change ».

Preuve de fin du plan (`SPRINT-3-PLAN.md` §2 ligne 29) : `on_round_start` ne
doit **pas** écraser une phase posée explicitement par l'API.

Pourquoi cette preuve est comportementale et pas structurelle
-----------------------------------------------------------
La phase n'est pas cosmétique : `config/phase-lock.yaml:5-13` fait de
`RESEARCH` un verrou d'écriture et d'exécution (`write_file`, `edit_file`,
`bash` bloqués), lu par `ToolRegistry.is_tool_allowed`
(`src/tool_registry.py:156-159`). Un client qui pose `phase=RESEARCH` via
`POST /api/phase/set` (`routes/phase_routes.py:27`) achète un vrai verrou.

Or `PhaseTracker.on_round_start` (`src/orchestrator/phase_tracker.py:55-64`) le
réécrit **inconditionnellement** à chaque début de round, avec `infer_phase()` =
BUILD sauf `plan_mode`. Le tracker est `on` par défaut (Palier 0). Le verrou
donc tient… jusqu'au round suivant, où il disparaît sans trace.

Le test vérifie donc l'effet, pas l'appel : après un round, `bash` est-il encore
bloqué ?
"""

import pytest

from src.orchestrator import phase_tracker as _pt
from src.orchestrator.phase_tracker import PhaseTracker
from src.tool_registry import ToolRegistry


@pytest.fixture
def registry(monkeypatch):
    """Le vrai singleton, remis à zéro : le verrou se prouve sur `is_tool_allowed`.

    `ToolRegistry.__repr__` (`src/tool_registry.py:261-263`) fait **du réseau** :
    `get_all_available` → `is_available` → `_check_port` → `socket.create_connection`.
    Or pytest réprenne l'objet pour construire le message d'un `assert` en échec, donc
    un test qui échoue *légitimement* se met à bloquer sur un `getaddrinfo`. On neutralise
    donc le `__repr__` le temps du test.

    Ce défaut d'affichage est **hors périmètre du Sprint 3** et rapporté comme tel : un
    `repr` qui bloque sur le réseau est un piège de latence en production (un `log %r`
    ou un débogueur suffit à figer un thread). Il n'est pas masqué ici — seul le chemin
    d'affichage est court-circuité, le comportement de `is_tool_allowed` est intact.
    """
    monkeypatch.setattr(ToolRegistry, "__repr__", lambda self: "<ToolRegistry>")
    _pt._TRACKER_LAST_WRITE.clear()
    reg = ToolRegistry.get_instance()
    with reg._session_lock:
        reg._session_phases.clear()
    yield reg
    with reg._session_lock:
        reg._session_phases.clear()
    _pt._TRACKER_LAST_WRITE.clear()


def _bash_is_blocked(reg, session_id):
    return not reg.is_tool_allowed("bash", session_id)["allowed"]


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_an_api_set_phase_survives_the_round_start(registry, monkeypatch):
    """UC-05 — la preuve de fin du plan."""
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    session = "sess-uc05"

    # Ce que fait POST /api/phase/set.
    registry.set_phase(session, "RESEARCH")
    assert _bash_is_blocked(registry, session), "pré-condition : le verrou est armé"

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1)

    assert _bash_is_blocked(registry, session), "le round start a désarmé un verrou posé par l'API"


def test_every_restricting_phase_survives_a_round_start(registry, monkeypatch):
    """Toutes les phases restrictives, pas seulement RESEARCH."""
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")

    for phase in ("RESEARCH", "INNOVATE", "PLAN", "VERIFY"):
        session = f"sess-{phase}"
        registry.set_phase(session, phase)
        before = _bash_is_blocked(registry, session)

        PhaseTracker(session, registry=registry, enabled=True).on_round_start(1)

        assert _bash_is_blocked(registry, session) == before, f"{phase} : verrou modifié au round start"


# ─── Contre-épreuves ───────────────────────────────────────────────────────


def test_an_unset_session_still_gets_the_inferred_phase(registry, monkeypatch):
    """Contre-épreuve : sans phase explicite, le tracker doit rester utile.

    C'est ce qui distingue « ne pas écraser un choix » de « ne plus rien faire ».
    """
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    session = "sess-fresh"

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1)

    assert registry.get_phase(session) == "BUILD"


def test_plan_mode_still_tightens_the_lock(registry, monkeypatch):
    """`plan_mode` est un resserrement volontaire : il doit rester appliqué.

    PLAN bloque `bash` (`config/phase-lock.yaml:32-34`) ; si le tracker
    abandonnait cette reinforcement, le mode plan ne serait plus qu'un libellé.
    """
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    session = "sess-plan"

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1, plan_mode=True)

    assert registry.get_phase(session) == "PLAN"
    assert _bash_is_blocked(registry, session)


def test_the_tracker_never_loosens_a_lock(registry, monkeypatch):
    """Propriété générale, indépendante des valeurs : le tracker ne peut que
    resserrer. Une phase restrictive posée par l'API n'est jamais remplacée par
    une phase plus permissive."""
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")

    restrictive = {"RESEARCH", "INNOVATE", "PLAN", "VERIFY"}
    for phase in restrictive:
        session = f"loose-{phase}"
        registry.set_phase(session, phase)
        PhaseTracker(session, registry=registry, enabled=True).on_round_start(1)

        assert registry.get_phase(session) == phase, f"{phase} a été relâchée en BUILD"


def test_kill_switch_off_never_touches_the_registry(registry, monkeypatch):
    """Palier 0 : switch off => le tracker n'écrit rien du tout.

    `enabled` n'est **pas** passé ici : le constructeur le lit depuis l'environnement
    (`phase_tracker.py:31-32`). Forcer `enabled=True` court-circuiterait le switch et
    testerait autre chose.
    """
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "off")
    session = "sess-off"

    PhaseTracker(session, registry=registry).on_round_start(1)

    assert registry.get_phase(session) == "BUILD", "une session vierge doit rester sur le défaut"
    assert session not in registry._session_phases, "le tracker a écrit alors qu'il est off"


# ─── Le partage entre streams ─────────────────────────────────────────────
#
# Un `PhaseTracker` est reconstruit à chaque stream (`agent_loop.py:2845`) alors que le
# registre survit. Sans état partagé, la règle « n'écrase que ce que j'ai écrit » serait
# vraie au round 1 et fausse au round suivant du nouveau tracker — et une phase PLAN
# laissée par un stream `plan_mode` resterait verrouillée sur tous les streams suivants.
# Un verrou qui ne se relâche jamais est aussi grave qu'un verrou qui ne se pose jamais.


def test_a_new_tracker_can_relax_a_phase_it_itself_wrote(registry, monkeypatch):
    """Stream suivant, `plan_mode` terminé : le tracker doit pouvoir revenir de PLAN à BUILD."""
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    session = "sess-2streams"

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1, plan_mode=True)
    assert registry.get_phase(session) == "PLAN", "le stream 1 ne.plan_mode a pas serré"

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1, plan_mode=False)

    assert registry.get_phase(session) == "BUILD", "un verrou posé par le tracker est resté collé"


def test_a_new_tracker_still_respects_a_lock_set_in_between(registry, monkeypatch):
    """Stream suivant, mais l'API a parlé entre les deux : le verrou tient toujours."""
    monkeypatch.setenv("ODYSSEUS_PHASE_TRACKER", "on")
    session = "sess-2streams-api"

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1, plan_mode=True)
    registry.set_phase(session, "RESEARCH")  # l'API reprend la main

    PhaseTracker(session, registry=registry, enabled=True).on_round_start(1, plan_mode=False)

    assert registry.get_phase(session) == "RESEARCH", "le nouveau tracker a écrasé un choix de l'API"
    assert _bash_is_blocked(registry, session), "bash a été déverrouillé"
