"""Sprint 3 v4 §1.1 — `CLASSIFY` doit être la phase du round 1.

Le défaut
---------
`archive/legacy/agent_loop.py:3040` appelle `_canonical_loop.advance()` **au début**
de chaque round, avant `resolve_current_phase` (`:3049`). Le round 1 avance donc
`CLASSIFY → KNOW` avant que quiconque ne regarde la phase, et `CANONICAL_SEQUENCE[0]`
n'est **jamais** la phase courante. C'est une donnée présente, jamais atteinte.

Pourquoi le test passe par le flux, pas par la fonction
-------------------------------------------------------
`resolve_current_phase` s'appelle en trois lignes et se teste donc trivially — et un
tel test ne prouverait rien du tout sur le comportement réel. La phase résolue est
publiée dans le flux par `run_status` (`agent_loop.py:3090`), qui est ce que voit
l'utilisateur. C'est cet observable-là que le test attaque : un tour réel, un switch
réel, les événements SSE réellement émis.

Le harness fait **vraiment** plusieurs rounds : le stub émet un `tool_calls` natif
pendant les premiers tours, parce que la boucle ne continue que si des outils ont été
appelés. Un stub qui renvoie du texte ferait Sortir la boucle au round 1 et les
tests multi-rounds ne prouveraient **rien** (c'était le défaut du premier jet).

Ce que le test ne prétend pas
-----------------------------
Le bogue n'est atteignable qu'avec `ODYSSEUS_LIVE_ORCHESTRATION=on`, dont le défaut
**code est `off`** (`killswitch_registry.py:27`). Le test le force donc explicitement :
il décrit le comportement de cette configuration, pas celui par défaut. La contre-épreuve
`test_the_default_path_is_unaffected_by_this_fix` vérifie que rien ne bouge quand le
switch est `off`.
"""

import asyncio
import json

import src.agent_loop as al
from src.orchestrator.loop import CANONICAL_SEQUENCE, CanonicalLoop
from src.orchestrator.phases import Phase
from src.progressive_disclosure import _TOOL_CATEGORY_MAP, get_progressive_disclosure
from src.tool_security import blocked_tools_for_owner

SUBSTANTIAL = "bonjour, explique-moi la différence entre ces deux approches"

# Outils proposés au tour réel. Deux contraintes, toutes deux vérifiées en exécution
# plutôt que supposées :
#   * aucun ne doit être bloqué en amont par la porte propriétaire (38 outils), sinon
#     on mesurerait cette porte-là au lieu de la phase ;
#   * au moins un doit être connu de `_TOOL_CATEGORY_MAP`, sinon le filtre de
#     divulgation n'a rien à retirer et la contre-épreuve « BUILD ne retire rien »
#     devient triviale.
OFFERED = {
    "list_sessions",
    "list_models",
    "web_search",
    "ask_user",
    "create_document",
    "update_plan",
}
assert not (OFFERED & blocked_tools_for_owner(None)), "un outil du jeu est bloqué en amont"
assert OFFERED & set(_TOOL_CATEGORY_MAP), "aucun outil du jeu n'est connu du filtre"


def _run_turn(monkeypatch, tmp_path, *, live_orchestration, max_rounds=4, tool_rounds=2):
    """Un tour réel, sur plusieurs rounds. On ne garde que ce que le flux publie."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_LIVE_ORCHESTRATION", "on" if live_orchestration else "off")
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", "on")

    phases: list[str] = []
    tools_sent: list[set[str]] = []

    async def _fake_stream(_candidates, _messages, **kw):
        schemas = kw.get("tools") or []
        tools_sent.append(
            {(s.get("function") or {}).get("name") for s in schemas if s.get("function")}
        )
        if len(tools_sent) <= tool_rounds:
            # Un tool call natif : c'est ce qui fait tenir la boucle plusieurs rounds.
            yield "data: " + json.dumps(
                {
                    "type": "tool_calls",
                    "calls": [{"id": f"c{len(tools_sent)}", "name": "list_sessions", "arguments": "{}"}],
                }
            ) + "\n\n"
        else:
            yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    async def _drain():
        async for chunk in al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": SUBSTANTIAL}],
            max_rounds=max_rounds,
            relevant_tools=set(OFFERED),
        ):
            if not chunk.startswith("data: "):
                continue
            try:
                ev = json.loads(chunk[6:].strip())
            except ValueError:
                continue
            if ev.get("type") == "run_status" and ev.get("phase") is not None:
                phases.append(ev["phase"])

    asyncio.run(_drain())
    return phases, tools_sent


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_the_first_round_really_is_the_first_sequence_phase(monkeypatch, tmp_path):
    """`CANONICAL_SEQUENCE[0]` doit être la phase du round 1, observée dans le flux.

    C'est la preuve de fin du v4 §1.1. Elle échoue sur le code d'aujourd'hui : le flux
    annonce `KNOW` au round 1.
    """
    phases, _ = _run_turn(monkeypatch, tmp_path, live_orchestration=True)

    assert len(phases) >= 2, f"le tour n'a fait qu'un round : le test ne prouve rien ({phases})"
    assert phases[0] == CANONICAL_SEQUENCE[0].value, (
        f"le round 1 annonce {phases[0]!r} au lieu de {CANONICAL_SEQUENCE[0].value!r} : "
        f"la premiere phase de la sequence est sautee (phases vues : {phases})"
    )


def test_the_sequence_is_walked_without_skipping_a_phase(monkeypatch, tmp_path):
    """Contre-épreuve : corriger ne doit faire sauter **aucune** phase.

    Un correctif qui décale tout d'un cran ferait perdre `BUILD` — la seule phase où la
    divulgation ne retire rien. La property vérifiée est donc « la suite observée est
    un préfixe de la séquence canonique », pas seulement « round 1 = CLASSIFY » : un
    préfixe, par construction, ne saute rien sur la longueur qu'il couvre.

    La property est bornée à ce que le harness parcourt réellement. Le stub répète le
    même outil, donc le **loop-breaker** (`agent_loop.py`, « repeating the same tool
    calls without new progress ») arrête la marche avant `MEMORY_OBSERVE`. C'est une
    protection réelle, pas un défaut : ce test ne la contourne pas, il exige simplement
    que la portion effectivement parcourue soit un préfixe et qu'elle soit assez longue
    pour qu'un tour unique ne puisse pas satisfaire l'assertion.
    """
    phases, _ = _run_turn(
        monkeypatch,
        tmp_path,
        live_orchestration=True,
        max_rounds=len(CANONICAL_SEQUENCE),
        tool_rounds=len(CANONICAL_SEQUENCE) - 1,
    )
    assert len(phases) >= 5, f"marche trop courte pour prouver quoi que ce soit : {phases}"

    canonical = [p.value for p in CANONICAL_SEQUENCE]
    assert phases == canonical[: len(phases)], (
        f"la suite annoncee {phases} n'est pas un prefixe de la sequence canonique {canonical}"
    )


def test_build_is_still_reached_and_still_sees_the_full_tool_surface(monkeypatch, tmp_path):
    """Contre-épreuve : `BUILD` reste atteinte, et c'est toujours le niveau `full`.

    C'est la property qui protège le chemin le plus fréquent : un correctif de
    « la phase manquante est revenue » qui rognerait `BUILD` casserait tout le monde.
    """
    phases, tools_sent = _run_turn(
        monkeypatch,
        tmp_path,
        live_orchestration=True,
        max_rounds=5,
        tool_rounds=3,
    )

    assert "BUILD" in phases, f"BUILD atteinte sur les phases {phases}"
    build_round = phases.index("BUILD")
    assert build_round < len(tools_sent), "aucun appel LLM au round BUILD"

    disclosure = get_progressive_disclosure()
    level = disclosure.resolve_level(Phase.BUILD)
    assert level.value == "full", f"BUILD n'est plus en niveau full ({level.value})"
    allowed = disclosure.get_allowed_tools(level)
    removed = [t for t in tools_sent[build_round] if t in _TOOL_CATEGORY_MAP and t not in allowed]
    assert not removed, f"BUILD a retiré des outils alors que le niveau est full : {removed}"


# ─── Contre-épreuves ───────────────────────────────────────────────────────


def test_the_default_path_is_unaffected_by_this_fix(monkeypatch, tmp_path):
    """`LIVE_ORCHESTRATION` est `off` par défaut : le chemin courant ne doit pas bouger.

    Le défaut code du switch est `off` (`killswitch_registry.py:27`), donc la boucle
    canonique ne tourne pas et la phase vient de `infer_phase`. Ce test verrouille le
    fait que le correctif ne touche pas ce chemin.
    """
    phases, _ = _run_turn(monkeypatch, tmp_path, live_orchestration=False)

    assert phases, "aucun run_status avec phase"
    assert "CLASSIFY" not in phases, (
        f"CLASSIFY est apparue sur le chemin par defaut {phases} : le switch est supposé off"
    )


def test_the_canonical_loop_object_itself_is_correct():
    """Contre-épreuve de localisation : `CanonicalLoop` n'a rien de cassé.

    `CanonicalLoop.current` vaut bien `CANONICAL_SEQUENCE[0]` à la construction. Le
    défaut n'est pas dans la boucle canonique mais dans **l'ordre des appels** de
    `stream_agent_loop`, qui avance avant de lire. Ce test empêche qu'on « corrige » la
    mauvaise classe : si ce test échoue, `CanonicalLoop` est en cause.
    """
    canonical = CanonicalLoop("test-session")
    assert canonical.current is CANONICAL_SEQUENCE[0]
    assert canonical.current is Phase.CLASSIFY


def test_advance_order_is_the_whole_story():
    """Property pure, sans la boucle : le contraste des deux ordres, asserté.

    Ordre d'aujourd'hui (corrigé) : on lit, puis on avance ⇒ `CLASSIFY`.
    Ordre fautif (historique) : on avance, puis on lit ⇒ `KNOW`.

    Les deux branches sont assertées dans le **même** test. Paramétrer en deux cas
    séparés aurait produit un test voué à l'échec pour le cas fautif — c'est-à-dire une
    démonstration, pas une propriété. Ici le test ne peut pas échouer : il encode la
    cause, et il échouerait seulement si l'ordre des deux appels cessait d'être la
    variable déterminante. Aucun coût de stub LLM.
    """
    def _read_then_advance():
        canonical = CanonicalLoop("test-session")
        read = canonical.current
        canonical.advance()
        return read

    def _advance_then_read():
        canonical = CanonicalLoop("test-session")
        canonical.advance()
        return canonical.current

    assert _read_then_advance() is Phase.CLASSIFY, "lire avant d'avancer doit donner CLASSIFY"
    assert _advance_then_read() is Phase.KNOW, "avancer avant de lire doit donner KNOW"
