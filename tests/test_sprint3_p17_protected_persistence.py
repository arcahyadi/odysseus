"""Sprint 3 — item 1 : P17 « Ne jamais stocker le sensible ».

Preuve de fin (re-dérivée, voir `docs/planning/SPRINT-3-PLAN.md` §2 ligne 25) :
un message dont le contenu classe `PROTECTED` ne doit se retrouver dans
**aucun** artefact durable sous `data/`, et le blocage doit être *visible* dans
le flux (règle 2 : un `except` ou un `if` qui n'émet rien ne peut pas devenir
un test).

Pourquoi la preuve a été re-dérivée
-----------------------------------
Le plan retenait `data/classification_index.json` comme preuve. Cet index ne peut
pas la porter : `DataClassified` (`src/data_classification.py:44-50`) ne stocke
que `key`, `level` et des horodatages — **jamais le contenu**. Un « le message
n'apparaît pas dans l'index » y serait donc vrai par construction et ne prouverait
rien. Ce qui écrit réellement la charge utile, c'est M6.2
(`archive/legacy/agent_loop.py:4300`) : `update_profile("User said: …")` dépose
le texte brut dans `data/memory-fs/profile.md`. La preuve porte donc sur les
artefacts mémoire.

Le texte de ce test est choisi pour être classé `PROTECTED` par
`data_classification` (mot « diagnostic ») tout en échappant aux règles
d'omission déjà présentes dans `provenance_memory` (déclencheurs
« diagnostics », « maladie grave » — absents). Ainsi le seul garde-fou possible
est bien la classification, pas une règle préexistante.
"""

import asyncio
import json

import pytest

import src.agent_loop as al
from src.data_classification import DataClassificationEngine, RetentionLevel

PROTECTED_TURN = "Mon diagnostic médical est positif, concluez sur mon cas."
PROTECTED_MARKER = "diagnostic médical"

# Un tour normal, classé PUBLIC : sert de contre-épreuve. Si la porte est réelle,
# elle doit laisser passer ce texte.
PUBLIC_TURN = "Bonjour, écris un petit script pour lister les fichiers."


def _collect(gen):
    async def _run():
        return [c async for c in gen]

    return asyncio.run(_run())


def _delta(text):
    return "data: " + json.dumps({"delta": text}) + "\n\n"


def _events(chunks):
    out = []
    for chunk in chunks:
        if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
            try:
                out.append(json.loads(chunk[6:]))
            except Exception:
                pass
    return out


def _run_turn(monkeypatch, tmp_path, user_text):
    """Un tour réel de `stream_agent_loop`, stub LLM, CWD isolé."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_stream(_c, _messages, **kw):
        # The stub answers the request it was given, the way a real model does.
        # That matters for P19: a fact the answer never used must NOT be
        # remembered, so a stub that ignored the request would make every
        # "a PUBLIC turn is still remembered" counter-evidence fail — for the
        # wrong reason (P19 working correctly, not the P17 gate being broken).
        yield _delta("Voici comment " + user_text[:60] + " se traite, étape par étape.")
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    return _collect(
        al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": user_text}],
            max_rounds=1,
            # Sans outils pertinents le tour part par le « direct low-signal
            # path » (agent_loop.py:2278-2351) qui RETOURNE avant tout le bloc
            # M6. Le geste n'y est pas observable : il faut passer la porte.
            relevant_tools={"bash"},
        )
    )


def _data_files(tmp_path):
    return {p: p.read_text(encoding="utf-8") for p in (tmp_path / "data").rglob("*") if p.is_file()}


def test_protected_turn_leaves_no_trace_of_its_payload(monkeypatch, tmp_path):
    """P17 — la preuve de fin : rien du texte PROTECTED sous `data/`."""
    _run_turn(monkeypatch, tmp_path, PROTECTED_TURN)

    offenders = {str(p.relative_to(tmp_path)): txt for p, txt in _data_files(tmp_path).items() if PROTECTED_MARKER in txt}

    assert offenders == {}, f"charge utile PROTECTED persistee : {offenders}"


def test_protected_turn_is_not_recorded_as_a_stated_fact(monkeypatch, tmp_path):
    """P17 — le cas reel constate : `- [stated] User said: <texte sensible>`."""
    _run_turn(monkeypatch, tmp_path, PROTECTED_TURN)

    profile = tmp_path / "data" / "memory-fs" / "profile.md"
    if profile.exists():
        assert PROTECTED_MARKER not in profile.read_text(encoding="utf-8")


def test_protected_turn_emits_a_visible_block_signal(monkeypatch, tmp_path):
    """P17 — le blocage doit être visible, pas silencieux (regle 2)."""
    events = _events(_run_turn(monkeypatch, tmp_path, PROTECTED_TURN))

    blocked = [e for e in events if e.get("type") == "memory_blocked"]
    assert blocked, f"aucun signal de blocage dans le flux : {sorted({e.get('type') for e in events})}"
    assert blocked[0]["level"] == "protected"


def test_public_turn_is_still_persisted(monkeypatch, tmp_path):
    """Contre-épreuve : la porte discrimine, elle n'est pas « tout échouer »."""
    _run_turn(monkeypatch, tmp_path, PUBLIC_TURN)

    profile = tmp_path / "data" / "memory-fs" / "profile.md"
    assert profile.exists(), "un tour PUBLIC doit toujours etre memorise"
    assert "User said" in profile.read_text(encoding="utf-8")


def test_no_block_signal_when_the_message_is_public(monkeypatch, tmp_path):
    events = _events(_run_turn(monkeypatch, tmp_path, PUBLIC_TURN))
    assert not [e for e in events if e.get("type") == "memory_blocked"]


def test_an_impactful_protected_fact_is_still_not_stored(monkeypatch, tmp_path):
    """Régression croisée P17 × P19 (Sprint 3 items 1 et 4).

    Wiring P19 (item 4) added a second durable write — the impact store — that
    did not consult the classification verdict. A PROTECTED message that the
    agent *did* use therefore scored high impact and got written to
    `topics/agent-impact.md`, silently undoing the P17 gate. "Impactful" is not
    a retention exemption: P17 outranks P19.
    """
    _run_turn(monkeypatch, tmp_path, PROTECTED_TURN)

    offenders = {str(p.relative_to(tmp_path)): txt for p, txt in _data_files(tmp_path).items() if PROTECTED_MARKER in txt}
    assert offenders == {}, f"un fait PROTECTED a fui par le store d'impact : {offenders}"


def test_gate_is_off_when_the_kill_switch_is_off(monkeypatch, tmp_path):
    """Palier 0 reste respecté : switch off => aucun blocage, aucune écriture mémoire."""
    monkeypatch.setenv("ODYSSEUS_DATA_CLASSIFICATION", "off")
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "off")

    events = _events(_run_turn(monkeypatch, tmp_path, PROTECTED_TURN))

    assert not [e for e in events if e.get("type") == "memory_blocked"]
    assert not (tmp_path / "data" / "memory-fs" / "profile.md").exists()


# ─── Le garde-fou de module, testé directement ─────────────────────────────


def test_should_persist_is_false_for_protected_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = DataClassificationEngine()

    assert engine.classify("k1", PROTECTED_TURN) is RetentionLevel.PROTECTED
    assert engine.should_persist("k2", PROTECTED_TURN) is False
    assert engine.should_persist("k3", PUBLIC_TURN) is True


@pytest.mark.parametrize("trigger", ["santé", "casier", "addiction", "mineur", "thérapie"])
def test_every_protected_pattern_is_gated(tmp_path, monkeypatch, trigger):
    monkeypatch.chdir(tmp_path)
    engine = DataClassificationEngine()
    assert engine.classify("k", f"une question sur {trigger}") is RetentionLevel.PROTECTED
    assert engine.should_persist("k", f"une question sur {trigger}") is False


def test_engine_survives_a_missing_data_dir(tmp_path, monkeypatch):
    """Règle 2 : un module de gouvernance qui lève quand `data/` manque est un
    module de gouvernance que le `except` global du loop désactive en silence."""
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "data").exists()

    engine = DataClassificationEngine()
    assert engine.classify("k", PROTECTED_TURN) is RetentionLevel.PROTECTED
    assert (tmp_path / "data" / "classification_index.json").exists()


def test_classification_index_holds_no_payload(tmp_path, monkeypatch):
    """Pourquoi la preuve du plan a été re-dérivée : l'index ne porte que la
    décision (clé, niveau, horodatages), jamais le contenu. C'est ce qui rend
    « le message n'apparaît pas dans l'index » vrai par construction, donc
    inutilisable comme preuve."""
    monkeypatch.chdir(tmp_path)
    DataClassificationEngine().classify("msg:s:1", PROTECTED_TURN)

    raw = (tmp_path / "data" / "classification_index.json").read_text(encoding="utf-8")
    record = json.loads(raw)[0]

    assert PROTECTED_MARKER not in raw
    assert set(record) == {"key", "level", "created_at", "expires_at", "session_id"}
    assert record["level"] == "protected"
