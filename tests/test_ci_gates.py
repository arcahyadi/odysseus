"""Les portes de CI ne sont des portes que si l'on a vu qu'elles échouent.

`gen_killswitch_tables.py --check` et `check_lint_budget.py` tournent dans la
pipeline CI. Une porte jamais vue tomber est indiscernable d'un `echo` vert :
le jour où sa logique se casse — un `return` mal placé, une comparaison
inversée, un chemin de fichier faux — elle continuera de passer en silence.

Ces tests font donc tomber chaque porte, explicitement, sur des données
fabriquées pour ça. Aucun d'eux ne touche au dépôt : `verifie_sources` est une
fonction pure sur un dictionnaire, et le budget se compare à une ligne.

Le troisième test est le plus important : il vérifie que la porte lint
**échoue sur une augmentation** et pas sur le nombre absolu. Une porte qui
échouerait sur le nombre absolu serait rouge dès le premier jour — donc
ignorée — et l'ignoree est le seul résultat certain d'une porte toujours rouge.
"""

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent


def _charge(nom: str, chemin: str):
    """Charge un script de `tools/` comme module, sans l'installer."""
    spec = importlib.util.spec_from_file_location(nom, REPO / chemin)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


gkt = _charge("gen_killswitch_tables", "tools/gen_killswitch_tables.py")
budget = _charge("check_lint_budget", "tools/check_lint_budget.py")


# ─── gen_killswitch_tables : les sources du registre ────────────────────────


def test_a_real_registry_has_no_stale_source():
    """CONTRE-ÉPREUVE de sanité : le registre réel passe.

    Sans ce test, une vérification qui refuserait tout passerait le test
    d'échec ci-dessous en ne refusant jamais rien.
    """
    etats = gkt.read_states()
    assert len(etats) >= 50, f"registre anormalement petit : {len(etats)} switches"
    cassees, _ = gkt.verifie_sources({s["env_var"]: s for s in etats})
    assert not cassees, "sources perimees dans le registre reel :\n  " + "\n  ".join(cassees)


@pytest.mark.parametrize(
    ("source", "doit_echouer"),
    [
        # Vrai, et vérifié comme tel.
        ("src/killswitch_registry.py:1", False),
        # La ligne n'existe pas — la dérive muette qu'on veut voir.
        ("src/killswitch_registry.py:999999", True),
        # Le fichier n'existe pas.
        ("src/fichier_qui_nexiste_pas.py:1", True),
        # Ligne zéro : une ligne commence à 1, donc `:0` est une source fausse.
        ("src/killswitch_registry.py:0", True),
        # Forme non reconnue — ni chemin, ni sentinelle.
        ("quelque chose", True),
        # Chemin sans ligne : signalé, jamais bloqué. Ce n'est pas faux, c'est
        # plus faible, et une porte qui bloquerait ici empêcherait de corriger.
        ("src/killswitch_registry.py", False),
        # La sentinelle d'un switch non câblé n'est pas une source.
        ("(aucun lecteur dans le code)", False),
    ],
)
def test_a_stale_source_is_detected(source, doit_echouer):
    etats = {"ODYSSEUS_FICTIF": {"env_var": "ODYSSEUS_FICTIF", "source": source}}
    cassees, sans_ligne = gkt.verifie_sources(etats)
    assert bool(cassees) is doit_echouer, (
        f"source={source!r} — cassees={cassees} sans_ligne={sans_ligne}, "
        f"verdict attendu : {'echec' if doit_echouer else 'succes'}"
    )
    # Seul un chemin *nu* doit etre signale « sans ligne » : une reference avec
    # numero, comme la sentinelle, n'a rien a signaler.
    if "sans " not in source and ":" in source and not source.startswith("("):
        assert not sans_ligne, f"source={source!r} signalee a tort comme sans ligne"


def test_a_source_without_a_line_is_reported_but_not_blocking():
    """CONTRE-ÉPREUVE de gradation : un chemin nu est signalé, pas refusé.

    Le registre en compte douze aujourd'hui. Les bloquer supposerait d'abord de
    leur trouver une ligne — un travail à part, pas une raison pour rendre la
    porte rouge et la faire ignorer.
    """
    etats = {"X": {"env_var": "X", "source": "src/orchestrator/agent_dispatcher.py"}}
    cassees, sans_ligne = gkt.verifie_sources(etats)
    assert not cassees
    assert len(sans_ligne) == 1 and "agent_dispatcher" in sans_ligne[0]


# ─── check_lint_budget : la porte doit echouer sur une AUGMENTATION ────────


def _budget_dans(tmp_path, monkeypatch, valeur: str) -> pathlib.Path:
    fichier = tmp_path / "lint_baseline.txt"
    fichier.write_text(valeur, encoding="utf-8")
    monkeypatch.setattr(budget, "BASELINE", fichier)
    return fichier


def test_the_lint_gate_fails_on_an_increase(tmp_path, monkeypatch, capsys):
    _budget_dans(tmp_path, monkeypatch, "100")
    monkeypatch.setattr(budget, "compte", lambda: 109)
    monkeypatch.setattr(sys, "argv", ["check_lint_budget.py"])
    assert budget.main() == 1, "la porte a accepte un budget depasse"
    assert "DEPASS" in capsys.readouterr().out


def test_the_lint_gate_passes_on_a_decrease(tmp_path, monkeypatch, capsys):
    _budget_dans(tmp_path, monkeypatch, "100")
    monkeypatch.setattr(budget, "compte", lambda: 91)
    monkeypatch.setattr(sys, "argv", ["check_lint_budget.py"])
    assert budget.main() == 0, "la porte a refuse une amelioration"
    assert "de moins" in capsys.readouterr().out


def test_the_lint_gate_passes_exactly_at_the_budget(tmp_path, monkeypatch):
    """CONTRE-ÉPREUVE de borne : « ne pas augmenter » inclut « rester igual ».

    Une porte écrite `<` au lieu de `<=` punirait le travail exact, ce qui
    pousse a gonfler le budget d'une unite pour eviter un echec — c'est-a-dire a
     taught la porte a etre contournable.
    """
    _budget_dans(tmp_path, monkeypatch, "100")
    monkeypatch.setattr(budget, "compte", lambda: 100)
    monkeypatch.setattr(sys, "argv", ["check_lint_budget.py"])
    assert budget.main() == 0


def test_a_missing_budget_is_a_failure_not_a_pass(tmp_path, monkeypatch):
    _budget_dans(tmp_path, monkeypatch, "100")
    monkeypatch.setattr(budget, "BASELINE", tmp_path / "absent.txt")
    monkeypatch.setattr(budget, "compte", lambda: 1)
    monkeypatch.setattr(sys, "argv", ["check_lint_budget.py"])
    assert budget.main() == 1, "un budget absent a passe : la porte se desactive toute seule"
