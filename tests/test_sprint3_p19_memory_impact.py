"""Sprint 3 — item 4 : P19 « La mémoire s'applique seulement si elle change la réponse ».

Preuve de fin du plan (`SPRINT-3-PLAN.md` §2 ligne 28) : **un `score > 0` sur un
tour réel**, et `should_store` relié à un store.

État initial mesuré : `hypothetical_response=""` (`agent_loop.py:4487`) faisait
court-circuiter `evaluate_impact` à `0.0` (`memory_impact.py:51-52`), donc
`should_store` était **toujours** `False` — et le résultat n'était que loggé.

La contre-épreuve est aussi importante que la preuve : un tour où le fait
n'apparaît pas dans la réponse doit rester à `0.0`. Sans cela, un `score > 0`
constant prouverait seulement qu'on a branché un calcul, pas un filtre.
"""

import asyncio
import contextlib
import json

import pytest

import src.agent_loop as al
import src.provenance_memory as pm
from src.memory_impact import DEFAULT_IMPACT_THRESHOLD, MemoryImpactVerifier, store_impacted_fact

# Le fait EST présent dans la réponse : l'agent s'en est servi.
FACT_USED = "Le projet s'appelle Mercury et il utilise PostgreSQL."
RESPONSE_USING_FACT = (
    "Mercury est un projet qui utilise PostgreSQL comme base de donnees. "
    "Voici comment le configurer correctement pour la production."
)

# Le fait est totalmente absent de la réponse : il n'a rien changé, donc rien
# à retenir. C'est le cas que la version « constante » de P19 ne détectait pas.
FACT_UNUSED = "Le mot de passe du compte est hunter2."
RESPONSE_IGNORING_FACT = (
    "Voici comment fonctionne le systeme de fichiers memoire du projet, "
    "avec ses fichiers de profil et ses entrees datees."
)


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
            with contextlib.suppress(ValueError):
                out.append(json.loads(chunk[6:]))
    return out


def _run_turn(monkeypatch, tmp_path, user_text, response_text):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_stream(_c, _messages, **kw):
        yield _delta(response_text)
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    return _events(
        _collect(
            al.stream_agent_loop(
                "https://api.openai.com/v1",
                "gpt-test",
                [{"role": "user", "content": user_text}],
                max_rounds=1,
                relevant_tools={"bash"},
            )
        )
    )


def _memory_files(tmp_path):
    root = tmp_path / "data" / "memory-fs"
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8") for p in root.rglob("*.md")} if root.exists() else {}


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_score_is_positive_on_a_real_turn(monkeypatch, tmp_path):
    """P19 — la preuve de fin du plan : score > 0 sur un tour réel."""
    events = _run_turn(monkeypatch, tmp_path, FACT_USED, RESPONSE_USING_FACT)

    impacts = [e for e in events if e.get("type") == "memory_impact"]
    assert impacts, f"aucun evenement memory_impact : {sorted({e.get('type') for e in events})}"
    assert impacts[0]["score"] > 0.0


def test_should_store_reaches_a_real_store(monkeypatch, tmp_path):
    """`should_store` doit avoir un consommateur, pas seulement une valeur."""
    _run_turn(monkeypatch, tmp_path, FACT_USED, RESPONSE_USING_FACT)

    stored = _memory_files(tmp_path)
    assert stored, "should_store=True n'a rien ecrit dans un store"
    assert any("Mercury" in txt for txt in stored.values()), f"le fait decide n'est pas dans {list(stored)}"


def test_a_fact_the_response_ignores_is_not_stored(monkeypatch, tmp_path):
    """Contre-épreuve — sans elle, un score > 0 constant ne prouverait rien."""
    events = _run_turn(monkeypatch, tmp_path, FACT_UNUSED, RESPONSE_IGNORING_FACT)

    impacts = [e for e in events if e.get("type") == "memory_impact"]
    assert impacts, "aucun evenement memory_impact"
    assert impacts[0]["score"] == 0.0
    assert impacts[0]["should_store"] is False
    assert not any("hunter2" in txt for txt in _memory_files(tmp_path).values())


def test_the_discriminator_is_the_response_not_the_fact(monkeypatch, tmp_path):
    """Un fait identique, deux réponses différentes ⇒ deux verdicts différents.

    C'est LA discrimination de P19 : si le score ne dépendait que du fait, le
    filtre ne filtrerait rien. La réponse « utilisée » contient réellement le
    fait ; la réponse « ignorée » n'en parle pas.
    """
    response_using_the_fact = (
        "Le mot de passe du compte est bien hunter2, je l'ai lu dans la configuration. "
        "Pensez a le changer avant la mise en production."
    )

    _run_turn(monkeypatch, tmp_path, FACT_UNUSED, response_using_the_fact)
    used = list(_memory_files(tmp_path).values())

    other = tmp_path / "other"
    other.mkdir()
    _run_turn(monkeypatch, other, FACT_UNUSED, RESPONSE_IGNORING_FACT)
    ignored = list(_memory_files(other).values())

    assert any("hunter2" in t for t in used), "le fait utilise aurait du etre retenu"
    assert not any("hunter2" in t for t in ignored), "le fait ignore n aurait pas du etre retenu"


def test_nothing_is_stored_when_the_kill_switch_is_off(monkeypatch, tmp_path):
    monkeypatch.setenv("ODYSSEUS_MEMORY_IMPACT", "off")

    events = _run_turn(monkeypatch, tmp_path, FACT_USED, RESPONSE_USING_FACT)

    assert not [e for e in events if e.get("type") == "memory_impact"]


# ─── Le module, testé directement ──────────────────────────────────────────


def test_empty_hypothetical_still_short_circuits_to_zero():
    """On garde la sémantique du module : un comparatif vide = aucun impact.
    Ce qui a changé, c'est que la boucle ne fournit plus de comparatif vide."""
    v = MemoryImpactVerifier()
    assert v.evaluate_impact("f", "une reponse", "") == 0.0


def test_impact_is_high_when_the_fact_shaped_the_answer():
    v = MemoryImpactVerifier()
    score = v.evaluate_impact(FACT_USED, RESPONSE_USING_FACT, RESPONSE_IGNORING_FACT)
    assert score > DEFAULT_IMPACT_THRESHOLD
    assert v.verify(FACT_USED, RESPONSE_USING_FACT, RESPONSE_IGNORING_FACT).should_store is True


def test_impact_is_zero_when_both_answers_match():
    v = MemoryImpactVerifier()
    assert v.evaluate_impact("f", "meme reponse", "meme reponse") == 0.0


@pytest.mark.parametrize("text", ["", "   ", "\n\n"])
def test_blank_responses_never_claim_impact(text):
    v = MemoryImpactVerifier()
    assert v.evaluate_impact("f", text, text) == 0.0


def test_should_store_respects_the_threshold():
    v = MemoryImpactVerifier(threshold=0.99)
    assert v.should_store("f", 0.98) is False
    assert v.should_store("f", 1.0) is True


def test_the_stored_entry_is_tagged_as_inferred(tmp_path, monkeypatch):
    """P19 s'appuie sur P16 : un fait retenu doit être taggé, pas écrit en vrac.

    `store_impacted_fact` returns the MemoryFS `(ok, message)` contract, not a
    path — the assertion is therefore on the file, which is the observable the
    contract is meant to protect.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pm, "_fs", None, raising=False)

    ok, _msg = store_impacted_fact(FACT_USED, "observed", 0.42)
    assert ok

    written = list((tmp_path / "data" / "memory-fs").rglob("*.md"))
    assert written
    body = "\n".join(p.read_text(encoding="utf-8") for p in written)
    assert "[observed]" in body
    assert FACT_USED in body
