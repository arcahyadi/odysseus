"""Sprint 3 — correctif du classifieur : M6 doit être atteignable depuis la route principale.

Ce que la mesure a montré (et qui ne figurait dans aucun document)
------------------------------------------------------------------
`_classify_agent_request` (`archive/legacy/agent_loop.py:1037`) calcule

    low_signal = not continuation and not domains

où `domains` vient d'une liste **fermée** de mots-clés, presque tous **anglais**
(`:982-1035`). Un tour qui n'y correspond pas est donc classé *low-signal* —
c'est-à-dire traité comme une conversation sans objet. Mesuré :

    « écris un script pour lister les fichiers du projet »  → low_signal=True
    « ajoute une fonction de tri à src/parser.py »        → low_signal=True
    « explique-moi la différence entre ces deux approches » → low_signal=True

Le défaut n'est pas une liste trop courte, c'est le **sens du défaut** : en
l'absence de mot-clé reconnu, la réponse par défaut est « rien à faire ».

Conséquence mesurée de bout en bout
-----------------------------------
`_direct_low_signal` (`:2257-2265`) teste `not relevant_tools` — l'**argument de
l'appelant**, jamais la récupération interne, qui a lieu plus bas. Or
`routes/chat_routes.py:1388`, la route de chat principale, ne passe pas
`relevant_tools`. La voie directe émet `metrics` puis `return` (`:2354`) : tout
ce qui suit est sauté — M6.1 à M6.9, la porte P17, l'impact P19, le routage P22,
les préférences P20, la provenance P16. Un tour réel donnait **0 événement M6**.

Les items 1 à 6 du Sprint 3 étaient donc correctement câblés, testés et
mutation-vérifiés — et invisibles depuis le chemin que les gens empruntent. Seul
`src/task_scheduler.py:1692` compose `relevant_tools` et atteint M6.

Ce que la preuve vérifie
------------------------
Pas « le classifieur classe mieux » — un detail d'implémentation. Le critère est
**la fin de la chaîne** : une demande substantielle, envoyée par la route
principale (donc *sans* `relevant_tools`, comme le fait `chat_routes.py:1388`),
doit atteindre M6.
"""

import asyncio
import contextlib
import json

import pytest

import src.agent_loop as al

# Un tour réel, substantiel, substantiel en français ET sans mot-clé anglais :
# c'est exactement ce qui passait par la voie directe.
SUBSTANTIAL_FR = "écris un script pour lister les fichiers du projet"
SUBSTANTIAL_FR2 = "explique-moi la différence entre ces deux approches"
SUBSTANTIAL_EN = "write a script that lists the project files"

# Les événements M6 : leur présence prouve que le bloc a été atteint.
M6_EVENTS = {"memory_blocked", "output_routed", "memory_impact", "agent_dispatch"}

LONG_REPLY = (
    "Voici la marche a suivre, detaillee et complete pour cette demande : "
    "d'abord verifier l'arborescence, puis lire le fichier de configuration, "
    "ensuite adapter la commande en consequence avant de l'executer."
)


def _collect(gen):
    async def _run():
        return [c async for c in gen]

    return asyncio.run(_run())


def _events(chunks):
    out = []
    for chunk in chunks:
        if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
            with contextlib.suppress(Exception):
                out.append(json.loads(chunk[6:]))
    return out


def _as_chat_route_calls(monkeypatch, tmp_path, user_text, reply=LONG_REPLY):
    """Un tour appelé COMME `routes/chat_routes.py:1388` : sans `relevant_tools`.

    C'est le point. Les tests des items 1 à 6 passaient tous
    `relevant_tools={"bash"}` pour franchir la porte — c'est-à-dire qu'ils
    testaient un chemin que la route principale n'emprunte pas.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_stream(_c, _messages, **kw):
        yield "data: " + json.dumps({"delta": reply}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    for switch in (
        "ODYSSEUS_PROVENANCE_MEMORY",
        "ODYSSEUS_DATA_CLASSIFICATION",
        "ODYSSEUS_MEMORY_IMPACT",
        "ODYSSEUS_OUTPUT_ROUTER",
        "ODYSSEUS_PREFERENCES",
        "ODYSSEUS_PHASE_TRACKER",
    ):
        monkeypatch.setenv(switch, "on")

    return _events(
        _collect(
            al.stream_agent_loop(
                "https://api.openai.com/v1",
                "gpt-test",
                [{"role": "user", "content": user_text}],
                max_rounds=1,
                # aucun relevant_tools : c'est ce que fait chat_routes.py:1388
            )
        )
    )


# ─── La preuve de fin ──────────────────────────────────────────────────────


@pytest.mark.parametrize("user_text", [SUBSTANTIAL_FR, SUBSTANTIAL_FR2, SUBSTANTIAL_EN])
def test_a_substantive_request_reaches_m6_from_the_chat_route(monkeypatch, tmp_path, user_text):
    """La preuve de fin du correctif : la route principale atteint M6."""
    events = _as_chat_route_calls(monkeypatch, tmp_path, user_text)

    metrics = [e for e in events if e.get("type") == "metrics"]
    went_direct = bool(metrics) and metrics[0].get("data", {}).get("direct_low_signal")
    assert not went_direct, f"la voie directe a encore pris le dessus pour {user_text!r}"

    reached = {e.get("type") for e in events} & M6_EVENTS
    assert reached, f"aucun événement M6 pour {user_text!r} : les types vus sont {[e.get('type') for e in events]}"


# ─── Contre-épreuves : la voie directe doit SURVIVRE ───────────────────────
#
# Le correctif ne doit pas envoyer les salutations dans une boucle agent complete.
# Sinon on paie une boucle, une récupération d'outils et un LLM pour « bonjour ».


@pytest.mark.parametrize("smalltalk", ["Bonjour", "merci !", "ça va ?", "hey", "yo"])
def test_smalltalk_still_takes_the_direct_path(monkeypatch, tmp_path, smalltalk):
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_stream(_c, _messages, **kw):
        yield "data: " + json.dumps({"delta": "Salut ! Comment puis-je t'aider ?"}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    events = _events(
        _collect(
            al.stream_agent_loop(
                "https://api.openai.com/v1",
                "gpt-test",
                [{"role": "user", "content": smalltalk}],
                max_rounds=1,
            )
        )
    )

    metrics = [e for e in events if e.get("type") == "metrics"]
    assert metrics and metrics[0].get("data", {}).get("direct_low_signal"), (
        f"{smalltalk!r} ne passe plus par la voie directe : une boucle agent complete pour une salutation"
    )


def test_punctuation_only_is_still_low_signal():
    assert al._classify_agent_request([{"role": "user", "content": "???"}], "???")["low_signal"] is True
    assert al._classify_agent_request([{"role": "user", "content": ""}], "")["low_signal"] is True


def test_an_explicit_continuation_is_still_a_continuation():
    intent = al._classify_agent_request([{"role": "user", "content": "ok"}], "ok")
    assert intent["continuation"] is True
    assert intent["low_signal"] is False


# ─── Le classifieur, au niveau unite ───────────────────────────────────────
#
# La preuve de fin est la boucle ; ces tests la rendent lisible et empêchent une
# régression silencieuse du vocabulaire.


@pytest.mark.parametrize(
    "text",
    [
        "écris un script pour lister les fichiers du projet",
        "ajoute une fonction de tri à src/parser.py",
        "explique-moi la différence entre ces deux approches",
        "pourquoi ce test échoue-t-il sur CI ?",
        "recherche dans le dépôt toutes les occurrences de get_memory_fs",
        "répare le bug dans la boucle de retry",
    ],
)
def test_a_substantive_request_is_not_low_signal(text):
    assert al._classify_agent_request([{"role": "user", "content": text}], text)["low_signal"] is False


def test_domain_detection_is_untouched():
    """Le correctif porte sur `low_signal`, pas sur le routage d'outils.

    Une requête à domaine doit continuer de produire EXACTEMENT le même
    `domains` : sinon on auraitperturbé la sélection d'outils en croyant
    réparer l'atteignabilité.
    """
    intent = al._classify_agent_request(
        [{"role": "user", "content": "search the web for the latest vllm release"}],
        "search the web for the latest vllm release",
    )
    assert "web" in intent["domains"]
    assert "cookbook" in intent["domains"], "le routage par mot-clé a été altéré"


def test_a_short_unknown_token_is_still_low_signal():
    """Contre-épreuve de la contre-preuve : un mot unique sans verbe d'action
    reste du bavardage, pas une demande."""
    assert al._classify_agent_request([{"role": "user", "content": "hmm"}], "hmm")["low_signal"] is True
