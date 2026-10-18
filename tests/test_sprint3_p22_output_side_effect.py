"""Sprint 3 — item 3 : P22 « La sortie visuelle est une modalité de premier rang ».

Preuve de fin du plan (`SPRINT-3-PLAN.md` §2 ligne 27) : **une demande de
diagramme écrit un fichier.** `route()` est pur (`output_router.py:164-203`) et
la décision n'était que loggée : aucun fichier écrit, aucun outil invoqué. Une
décision d'architecture sans effet de bord n'est pas une architecture.
"""

import asyncio
import contextlib
import json
from pathlib import Path

import src.agent_loop as al
from src.output_router import DesignModule, OutputMode, OutputRouter

DIAGRAM_REQUEST = "Fais un diagramme de l'architecture de ce projet."
DIAGRAM_RESPONSE = (
    "Voici l'architecture en mermaid :\n\n```mermaid\ngraph TD\n  A[Client] --> B[API]\n```\n"
)
PLAIN_REQUEST = "Bonjour, comment ça va ?"
PLAIN_RESPONSE = "Bonjour, merci — tout va bien."


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


# ─── LA preuve de fin ──────────────────────────────────────────────────────


def test_a_diagram_request_writes_a_file(monkeypatch, tmp_path):
    """P22 — la preuve de fin du plan."""
    _run_turn(monkeypatch, tmp_path, DIAGRAM_REQUEST, DIAGRAM_RESPONSE)

    # Scoped to the output dir on purpose: `data/` also holds the classification
    # index (Sprint 3 item 1), which would otherwise be picked up first.
    outputs = tmp_path / "data" / "outputs"
    assert outputs.exists(), "une demande de diagramme n'a produit aucun fichier"

    written = [p for p in outputs.rglob("*") if p.is_file()]
    assert written, "data/outputs existe mais est vide"

    content = written[0].read_text(encoding="utf-8")
    assert "graph TD" in content, "le fichier ne contient pas la source du diagramme"


def test_the_written_file_is_announced_on_the_stream(monkeypatch, tmp_path):
    """Règle 2 : un effet de bord invisible ne peut être ni testé ni noticed."""
    events = _run_turn(monkeypatch, tmp_path, DIAGRAM_REQUEST, DIAGRAM_RESPONSE)

    routed = [e for e in events if e.get("type") == "output_routed"]
    assert routed, f"aucun evenement de sortie : {sorted({e.get('type') for e in events})}"
    assert routed[0]["mode"] == "visual_inline"
    assert routed[0]["path"]


def test_a_plain_request_writes_nothing(monkeypatch, tmp_path):
    """Contre-épreuve : TEXT_ONLY ne doit produire aucun fichier.

    The loop only emits `output_routed` when `apply` actually wrote something —
    the text response IS the output for TEXT_ONLY, so there is no artifact to
    announce. The invariant is therefore "no file, no event".
    """
    events = _run_turn(monkeypatch, tmp_path, PLAIN_REQUEST, PLAIN_RESPONSE)

    assert not (tmp_path / "data" / "outputs").exists()
    assert not [e for e in events if e.get("type") == "output_routed"]


def test_nothing_is_written_when_the_kill_switch_is_off(monkeypatch, tmp_path):
    monkeypatch.setenv("ODYSSEUS_OUTPUT_ROUTER", "off")

    events = _run_turn(monkeypatch, tmp_path, DIAGRAM_REQUEST, DIAGRAM_RESPONSE)

    assert not [e for e in events if e.get("type") == "output_routed"]
    assert not (tmp_path / "data" / "outputs").exists()


# ─── Le routeur, testé directement ─────────────────────────────────────────


def test_router_still_decides_without_writing(tmp_path, monkeypatch):
    """`route()` reste pur : c'est `apply()` qui agit. Mélanger les deux
    rendrait le routeur impossible à tester et il wrote pendant un predict."""
    monkeypatch.chdir(tmp_path)
    decision = OutputRouter().route(request=DIAGRAM_REQUEST, response_text=DIAGRAM_RESPONSE)

    assert decision.mode is OutputMode.VISUAL_INLINE
    assert decision.module is DesignModule.DIAGRAM
    assert not (tmp_path / "data").exists()


def test_apply_writes_and_returns_the_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = OutputRouter()
    decision = router.route(request=DIAGRAM_REQUEST, response_text=DIAGRAM_RESPONSE)

    path = router.apply(decision, DIAGRAM_RESPONSE, out_dir=tmp_path / "out")

    assert path is not None
    assert Path(path).exists()
    assert "graph TD" in Path(path).read_text(encoding="utf-8")


def test_apply_is_a_noop_for_text_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = OutputRouter()
    decision = router.route(request=PLAIN_REQUEST, response_text=PLAIN_RESPONSE)

    assert router.apply(decision, PLAIN_RESPONSE, out_dir=tmp_path / "out") is None
    assert not (tmp_path / "out").exists()


def test_explicit_file_request_is_written_with_its_extension(tmp_path, monkeypatch):
    """Étape 2 de l'arbre : une demande de fichier explicite."""
    monkeypatch.chdir(tmp_path)
    router = OutputRouter()
    decision = router.route(request="crée un fichier .md avec le résumé", response_text=PLAIN_RESPONSE)

    assert decision.mode is OutputMode.FILE_DOWNLOAD
    path = router.apply(decision, PLAIN_RESPONSE, out_dir=tmp_path / "out")
    assert path is not None and str(path).endswith(".md")


def test_apply_refuses_to_overwrite_silently(tmp_path, monkeypatch):
    """Deux sorties de même nom ne doivent pas s'écraser : le contenu perdu est
    irrattrapable, et un écrasement silencieux est la pire trace possible."""
    monkeypatch.chdir(tmp_path)
    router = OutputRouter()
    out = tmp_path / "out"
    first = router.apply(router.route(DIAGRAM_REQUEST, DIAGRAM_RESPONSE), "PREMIER", out_dir=out)

    second = router.apply(router.route(DIAGRAM_REQUEST, DIAGRAM_RESPONSE), "SECOND", out_dir=out)

    assert first != second
    assert "PREMIER" in Path(first).read_text(encoding="utf-8")
    assert "SECOND" in Path(second).read_text(encoding="utf-8")


def test_mcp_branch_is_not_faked(tmp_path, monkeypatch):
    """`connected_mcp_tools` n'est jamais peuplé en production : la branche
    MCP_TOOL ne doit pas s'activer par magie, ni ecrire un fichier."""
    monkeypatch.chdir(tmp_path)
    router = OutputRouter()
    decision = router.route(request=DIAGRAM_REQUEST, response_text=DIAGRAM_RESPONSE)

    assert decision.mode is not OutputMode.MCP_TOOL
    assert router.apply(decision, DIAGRAM_RESPONSE, out_dir=tmp_path / "out") is not None
