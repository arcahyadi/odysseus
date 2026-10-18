"""Sprint 3 — item 8 : P5 + P21, la divulgation progressive doit restreindre
réellement les schémas d'outils envoyés au modèle.

Le calcul existait et n'était consommé nulle part
--------------------------------------------------
M6.8 (P5 « divulgation progressive », P21 « surface d'outils ») calcule un
`allowed_tools` et ne fait que le **loguer** : `get_allowed_tools` n'était appelé par
aucun site de la boucle. Un principe qui calcule une liste de restrictions et la
journalise n'est pas un contrôle, c'est un rapport.

Et le corriger dans M6.8 n'aurait rien changé : ce bloc est vers la ligne 4600, alors
que les schémas sont envoyés au modèle vers la ligne 3212. Le filtre doit agir **là où
la liste est construite**, une fois par round.

Le piège mesuré avant de coder
------------------------------
`_TOOL_CATEGORY_MAP` ne connaît que **37 des 68** schémas natifs. Filtrer strictement
par l'allowlist aurait donc **supprimé 31 outils dans toutes les phases, BUILD
comprise** — `web_search`, `ask_user`, toute la surface e-mail, la gestion des
sessions. Un filtre de « moins d'outils » qui casse tout le monde pour restreindre un
cas de niche.

Le filtre ne retire donc que ce que la carte connaît **et** refuse. Un outil inconnu
de la carte est *inconnu ici*, pas interdit : il passe. Mesuré sur les 68 schémas :

    CLASSIFY / AUTOEVAL / MEMORY_OBSERVE  level=minimal   retire 26, garde 31
    KNOW / PLAN                           level=standard  retire 23, garde 31
    BUILD / QUALITY                       level=full      retire  0, garde 31

`full` ne retire rien : le chemin courant est intact.

Ce que la boucle offre vraiment — 33 schémas
------------------------------------------
`blocked_tools_for_owner` (`tool_security.py:226`) retire **38** outils *avant* la
divulgation, dont `bash`, `edit_file`, `glob`, `grep`, `api_call`. Sur les 33 restants,
la divulgation retire 11 (minimal) / 10 (standard) / 0 (full).

Les jeux de ce fichier sont donc choisis parmi ces 33, et `_assert_sets_are_reachable`
échoue explicitement si l'un d'eux passe dans le lot bloqué : sinon le test mesurerait
la porte propriétaire au lieu de la divulgation.

*Remarque hors périmètre, constatée en mesurant* : `blocked_tools_for_owner` renvoie
les mêmes 38 outils pour `None`, pour un utilisateur et pour `"admin"`. La fonction
dépend donc du rôle, pas de l'owner. Signalé au Chef, non corrigé ici.

Pourquoi `plan_mode` ne prouverait rien
--------------------------------------
`plan_mode_disabled_tools()` (`tool_security.py:153`) est une **liste de refus** — tout
outil mutateur — et filtre déjà les schémas. Un test en `plan_mode` passerait sans le
correctif, et ne prouverait pas que la divulgation fait quoi que ce soit. Le seul
levier vers une phase restrictive **sans** `plan_mode` est la boucle canonique
(`ODYSSEUS_LIVE_ORCHESTRATION=on`).

Pourquoi la phase est KNOW, et non CLASSIFY
-------------------------------------------
`agent_loop.py:3039` appelle `_canonical_loop.advance()` **au début de chaque round,
avant** `resolve_current_phase` (`:3048`). Le round 1 avance donc `CLASSIFY → KNOW` et
la phase courante est `KNOW` (niveau `standard`).

Conséquence : **`CLASSIFY` n'est jamais atteinte** dans la boucle réelle — round 1 =
KNOW, round 2 = PLAN, … round 7 = MEMORY_OBSERVE. Le premier élément de
`CANONICAL_SEQUENCE` est du code mort. C'est un défaut de la même famille que ceux que
ce sprint traque (une donnée présente, jamais atteinte) ; il est **constaté et
signalé**, pas corrigé ici : décaler la séquence changerait toute l'orchestration
canonique et sort du périmètre de l'item 8. `test_the_first_sequence_phase_is_dead`
verrouille le comportement observé pour que le défaut soit visible plutôt que latent.

Pourquoi le jeu d'outils est passé explicitement
-----------------------------------------------
Sans `relevant_tools`, la boucle interroge le ToolIndex, qui **replie sur
`ALWAYS_AVAILABLE` (3 outils) quand ChromaDB est injoignable** — l'ensemble observé
dépendrait alors de l'environnement, et la preuve ne prouverait rien sur une machine
joignable. On passe donc un jeu connu, ce qui prend la branche RAG déterministe et rend
la preuve indépendante de l'environnement.
"""

import asyncio
import json

import pytest

import src.agent_loop as al
from src.orchestrator.loop import CANONICAL_SEQUENCE, CanonicalLoop
from src.orchestrator.phases import Phase
from src.progressive_disclosure import _TOOL_CATEGORY_MAP, get_progressive_disclosure
from src.tool_security import blocked_tools_for_owner

# Refusés par le niveau `standard`, donc par la phase réelle du round 1 (KNOW).
# Mesuré sur les 33 schémas que la boucle offre après la porte propriétaire.
OUT_OF_PHASE = (
    "create_document",
    "edit_document",
    "update_document",
    "suggest_document",
    "manage_notes",
    "trigger_research",
    "edit_image",
    "pipeline",
    "chat_with_model",
    "ask_teacher",
)

# Conservés au niveau `standard` : consultation.
IN_PHASE = (
    "list_sessions",
    "list_models",
    "list_served_models",
    "list_downloads",
    "list_cached_models",
    "list_cookbook_servers",
    "list_serve_presets",
)

# Autorisé à `standard`, refusé à `minimal`. Sert à prouver que le *niveau* discrimine,
# et pas seulement qu'un filtre binaire existe.
REFUSED_ONLY_AT_MINIMAL = "update_plan"

# Inconnus de `_TOOL_CATEGORY_MAP`. Ne doivent JAMAIS disparaître, quelle que soit la
# phase : c'est la contre-épreuve de la contre-preuve.
UNKNOWN_TO_MAP = (
    "web_search",
    "web_fetch",
    "ask_user",
    "render_diagram",
    "ui_control",
    "search_hf_models",
)

# Le jeu d'outils offert au modèle, avant filtrage.
OFFERED = set(OUT_OF_PHASE) | set(IN_PHASE) | set(UNKNOWN_TO_MAP) | {REFUSED_ONLY_AT_MINIMAL}

SUBSTANTIAL = "bonjour, explique-moi la différence entre ces deux approches"


def _assert_sets_are_reachable():
    """Le test ne doit mesurer QUE la divulgation.

    `blocked_tools_for_owner` retire 38 outils avant même que la divulgation ne parle.
    Si l'un de nos outils passait dans ce lot, un retrait pourrait être attribué à la
    mauvaise porte, ou une régression masquée. Le test échoue donc explicitement si les
    jeux deviennent inatteignables.
    """
    blocked = blocked_tools_for_owner(None)
    unreachable = sorted(OFFERED & blocked)
    assert not unreachable, (
        f"ces outils sont filtres en amont par le proprietaire, "
        f"le test ne mesurerait plus la divulgation : {unreachable}"
    )

    level = get_progressive_disclosure().resolve_level(Phase.KNOW)
    allowed = get_progressive_disclosure().get_allowed_tools(level)
    wrongly_kept = [t for t in OUT_OF_PHASE if t in allowed]
    assert not wrongly_kept, (
        f"ces outils ne sont plus refuses au niveau {level.value} : "
        f"ce test ne teste plus rien. {wrongly_kept}"
    )
    wrongly_dropped = [t for t in IN_PHASE if t not in allowed]
    assert not wrongly_dropped, (
        f"ces outils ne sont plus autorises au niveau {level.value} : "
        f"ce test ne teste plus rien. {wrongly_dropped}"
    )


def _sent_tool_names(monkeypatch, tmp_path, live_orchestration, disclosure=None):
    """Tour réel, et on note les schémas effectivement passés au modèle."""
    _assert_sets_are_reachable()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_LIVE_ORCHESTRATION", "on" if live_orchestration else "off")
    if disclosure is None:
        monkeypatch.delenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", raising=False)
    else:
        monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", disclosure)

    seen: list[set[str]] = []

    async def _fake_stream(_candidates, _messages, **kw):
        schemas = kw.get("tools") or []
        seen.append({(s.get("function") or {}).get("name") for s in schemas if s.get("function")})
        yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    asyncio.run(
        _drain(
            al.stream_agent_loop(
                "https://api.openai.com/v1",
                "gpt-test",
                [{"role": "user", "content": SUBSTANTIAL}],
                max_rounds=1,
                relevant_tools=set(OFFERED),
            )
        )
    )
    return seen


async def _drain(gen):
    async for _ in gen:
        pass


def _assert_a_call_happened(seen):
    assert seen, "aucun appel LLM observe : la preuve ne prouve rien"
    assert seen[0], "aucun outil envoye au modele : rien a filtrer, la preuve est vide"
    return seen[0]


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_the_model_is_not_offered_out_of_phase_tools(monkeypatch, tmp_path):
    """P5 + P21 — le modèle ne reçoit plus les outils hors de sa phase.

    Round 1 de la boucle canonique, sans `plan_mode` : rien d'autre ne peut expliquer
    le retrait, puisque `plan_mode_disabled_tools()` n'est pas appelé.
    """
    sent = _assert_a_call_happened(_sent_tool_names(monkeypatch, tmp_path, live_orchestration=True))

    leaked = [t for t in OUT_OF_PHASE if t in sent]
    assert not leaked, f"outils hors phase envoyes au modele : {leaked}"

    missing = [t for t in IN_PHASE if t not in sent]
    assert not missing, f"la divulgation a retire des outils de consultation : {missing}"


# ─── Contre-épreuves ───────────────────────────────────────────────────────


def test_the_common_path_loses_nothing(monkeypatch, tmp_path):
    """Sans boucle canonique la phase est BUILD : `full`, donc **retrait nul**.

    C'est la contre-épreuve qui protège le chemin le plus fréquent. Un filtre de
    « moins d'outils » qui rognerait BUILD casserait tout le monde pour restreindre un
    cas de niche.
    """
    sent = _assert_a_call_happened(_sent_tool_names(monkeypatch, tmp_path, live_orchestration=False))

    missing = sorted(OFFERED - sent)
    assert not missing, f"BUILD a perdu des outils alors que le niveau est full : {missing}"


def test_tools_unknown_to_the_map_never_disappear(monkeypatch, tmp_path):
    """Le piège mesuré : la carte connaît 37 schémas sur 68.

    Un filtre strict par allowlist aurait supprimé 31 outils — `web_search`,
    `ask_user`, toute la surface e-mail — **dans toutes les phases**. Ce test verrouille
    la borne : un outil inconnu de la carte passe toujours.
    """
    for t in UNKNOWN_TO_MAP:
        assert t not in _TOOL_CATEGORY_MAP, (
            f"{t} est desormais connu de la carte : ce test ne teste plus rien"
        )

    sent = _assert_a_call_happened(_sent_tool_names(monkeypatch, tmp_path, live_orchestration=True))

    lost = [t for t in UNKNOWN_TO_MAP if t not in sent]
    assert not lost, f"la divulgation a fait disparaitre des outils qu'elle ne connait pas : {lost}"


def test_the_kill_switch_off_disables_the_filter(monkeypatch, tmp_path):
    """Palier 0 : switch off, aucune restriction, même en phase KNOW."""
    sent = _assert_a_call_happened(
        _sent_tool_names(monkeypatch, tmp_path, live_orchestration=True, disclosure="off")
    )

    missing = [t for t in OUT_OF_PHASE if t not in sent]
    assert not missing, f"le switch est off mais {missing} ont ete retires quand meme"


def test_the_switch_on_is_the_default(monkeypatch, tmp_path):
    """Palier 0 : `PROGRESSIVE_DISCLOSURE` vaut `on` par défaut **dans le code**.

    `delenv` puis un tour réel : c'est le seul moyen de le prouver. L'absence de
    variable dans `.env` ne dit rien du défaut du code.
    """
    sent = _assert_a_call_happened(_sent_tool_names(monkeypatch, tmp_path, live_orchestration=True))

    leaked = [t for t in OUT_OF_PHASE if t in sent]
    assert not leaked, f"switch absent du tout et pourtant {leaked} ont fuite"


@pytest.mark.parametrize("switch", ["on", "1", "true", "yes"])
def test_every_truthy_spelling_enables_the_filter(monkeypatch, tmp_path, switch):
    """Le filtre doit suivre la convention de killswitch du projet, pas une sienne."""
    sent = _assert_a_call_happened(
        _sent_tool_names(monkeypatch, tmp_path, live_orchestration=True, disclosure=switch)
    )

    leaked = [t for t in OUT_OF_PHASE if t in sent]
    assert not leaked, f"avec ODYSSEUS_PROGRESSIVE_DISCLOSURE={switch!r}, {leaked} ont fuite"


# ─── Le niveau discrimine, pas seulement « filtrer ou pas » ─────────────────


def test_the_level_discriminates_between_phases():
    """Un filtre binaire « outils interdits / outils permis » passerait ce test.

    `update_plan` (catégorie `planning`) est autorisé à `standard` et refusé à
    `minimal`. Si les deux niveaux renvoyaient la même liste, la divulgation ne
    distinguerait pas les phases — elle ne serait qu'une liste unique.
    """
    pdc = get_progressive_disclosure()
    standard = pdc.get_allowed_tools(pdc.resolve_level(Phase.KNOW))
    minimal = pdc.get_allowed_tools(pdc.resolve_level(Phase.CLASSIFY))

    assert REFUSED_ONLY_AT_MINIMAL in standard, "l'outil de contrôle n'est plus autorisé a standard"
    assert REFUSED_ONLY_AT_MINIMAL not in minimal, "l'outil de contrôle n'est plus refusé a minimal"
    assert minimal < standard, "minimal et standard ne sont plus distincts : la phase ne discrimine plus"


# ─── Défaut constaté, verrouillé pour rester visible ───────────────────────


def test_the_first_sequence_phase_is_dead():
    """`CLASSIFY` n'est jamais la phase courante — défaut signalé, non corrigé.

    `agent_loop.py:3039` avance la boucle canonique **avant** de résoudre la phase, donc
    le round 1 est déjà `KNOW` et `CANONICAL_SEQUENCE[0]` (`CLASSIFY`) est inatteignable.

    Ce test ne valide pas ce comportement : il le **rend visible**. Si quelqu'un corrige
    le décalage, ce test échouera et rappellera que les jeux de ce fichier, et les
    compteurs de la documentation, ont été mesurés sur `KNOW`.
    """
    canonical = CanonicalLoop("test-session")
    assert canonical.current is CANONICAL_SEQUENCE[0]

    # Reproduit l'ordre réel de `agent_loop.py:3039-3048`.
    canonical.advance()
    assert canonical.current is Phase.KNOW
    assert canonical.current is not CANONICAL_SEQUENCE[0], (
        "CLASSIFY est desormais atteinte : corriger ce test et les jeux OUT_OF_PHASE, "
        "qui ont ete mesures au niveau standard"
    )
