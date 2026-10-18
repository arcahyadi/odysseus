"""Sprint 3 — item 6 : P16 « la provenance s'écrit vraiment ».

Preuve de fin du plan (`SPRINT-3-PLAN.md` §2 ligne 30) : `[observed]` et
`[inferred]` apparaissent dans `data/memory-fs/`.

Le no-op
--------
`MemoryFS.add_observed` refuse d'écrire si le fichier de domaine n'existe pas
(`src/provenance_memory.py:344-346`) : *« Domain file does not exist — cannot
observe without prior context »*. C'est un contrat **délibéré et testé**
(`tests/test_provenance_memory.py:336-339` `test_add_observed_requires_existing_file`)
et ce test le garde.

Mais rien ne créait jamais `topics/agent-output.md`. L'appel live
(`archive/legacy/agent_loop.py:4400`) était donc un no-op **garanti** — et son
`False` était jeté. Pire : le bloc annonçait ensuite
`"[m6.2] provenance memory updated"` **inconditionnellement** (`:4403`), y
compris quand aucune écriture n'avait eu lieu. Un log qui ne peut pas avoir tort
ne dit rien.

L'agent-output est.create un contexte, pas une garantie de provenance : l'absence
de fichier est un problème de **démarrage**, pas une raison de refuser d'écrire.

Le second défaut, **mien** (item 4) — vérifié, et il n'existe pas
-------------------------------------------------------------
`MemoryFS.add_stated` **ajoute** quand le fichier existe déjà
(`provenance_memory.py:337`) : il ne se remplace pas. `store_impacted_fact`
l'appelle à chaque stockage pour amorcer le domaine, ce qui laissait croire à une
accumulation d'une ligne d'amorce par fait retenu.

J'ai vérifié avant de corriger : `memory_append` est **idempotent** — « Déjà
présent, pas d'erreur » (`:248-250`). L'amorce est donc unique par construction.
Il n'y a pas de défaut, et le test ci-dessous verrouille cette propriété : si
`add_stated` change un jour de sémantique (un bump de version vers « remplace »),
une duplication réapparaîtrait silencieusement dans le store de provenance.
"""

import asyncio
import json
import logging
import re

import pytest

import src.agent_loop as al
import src.provenance_memory as pm
from src.memory_impact import store_impacted_fact
from src.provenance_memory import MemoryFS

OBSERVED_DOMAIN = "agent-output"
IMPACT_DOMAIN = "agent-impact"


@pytest.fixture
def memfs(tmp_path, monkeypatch):
    """Racine pinnée, singleton remis à zéro.

    `get_memory_fs()` mémoïse un `MemoryFS` construit avec `MEMORY_ROOT =
    Path("data/memory-fs")` (CWD-relative, `provenance_memory.py:46`). Sans ce
    reset, le singleton créé par un autre fichier de test serait réutilisé :
    ordre-dépendant, et écrit dans le dépôt.
    """
    fs = MemoryFS(tmp_path / "memory-fs")
    # Migration MOD-5 : _fs est maintenant dans AppContext.caches.fs
    from src.app_context import app_context
    monkeypatch.setattr(app_context.caches, "fs", fs)
    return fs


def _collect(gen):
    async def _run():
        return [c async for c in gen]

    return asyncio.run(_run())


def _delta(text):
    return "data: " + json.dumps({"delta": text}) + "\n\n"


def _run_turn(monkeypatch, tmp_path, user_text, reply):
    """Un tour réel de `stream_agent_loop`, stub LLM, CWD isolé."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_stream(_c, _messages, **kw):
        yield _delta(reply)
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    return _collect(
        al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": user_text}],
            max_rounds=1,
            # Sans outils pertinents le tour part par le « direct low-signal
            # path » (agent_loop.py:2278-2351) qui RETOURNE avant tout le bloc M6.
            relevant_tools={"bash"},
        )
    )


LONG_REPLY = (
    "Voici la marche a suivre, detaillee et complete pour cette demande : "
    "d'abord verifier l'arborescence, puis lire le fichier de configuration, "
    "ensuite adapter la commande en conséquence avant de l'executer."
)


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_a_plain_turn_leaves_an_observed_fact(memfs, monkeypatch, tmp_path):
    """P16 — la preuve de fin du plan : `[observed]` atterrit sur le disque."""
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")

    _run_turn(
        monkeypatch,
        tmp_path,
        "Bonjour, écris un petit script pour lister les fichiers du projet.",
        LONG_REPLY,
    )

    path = memfs.root / f"topics/{OBSERVED_DOMAIN}.md"
    assert path.exists(), f"le domaine {OBSERVED_DOMAIN} n'a jamais ete cree : add_observed est un no-op"
    assert "[observed]" in path.read_text(), "aucune observation enregistree"


def test_stored_inference_lands_with_its_confidence(memfs, monkeypatch):
    """P16 — le second tag : `[inferred]` avec son niveau de confiance."""
    ok, msg = store_impacted_fact("Le projet utilise Poetry", tag="inferred", confidence=0.8)

    assert ok, f"store_impacted_fact a echoue : {msg}"
    text = (memfs.root / f"topics/{IMPACT_DOMAIN}.md").read_text()
    assert "[inferred] Le projet utilise Poetry" in text
    assert "0.8" in text, "la confiance n'est pas enregistree"


# ─── Le défaut que j'ai introduit a l'item 4 ───────────────────────────────


def test_repeated_impact_stores_do_not_accumulate_seed_lines(memfs):
    """Verrou d'une propriété, pas preuve d'un bug.

    `add_stated` ajoute quand le fichier existe (`:337`) ; c'est
    `memory_append` qui est idempotent (`:248-250`, « Déjà présent, pas
    d'erreur »). L'amorce du domaine ne doit donc poser sa ligne **qu'une fois**,
    sinon chaque fait retenu déposerait un faux `[stated]` dans le store et le
    compteur de faits affichés mentirait.
    """
    for i in range(3):
        ok, msg = store_impacted_fact(f"fait retenu {i}")
        assert ok, msg

    text = (memfs.root / f"topics/{IMPACT_DOMAIN}.md").read_text()
    assert text.count("[stated]") == 1, f"l'amorce s'accumule :\n{text}"


def test_repeated_turns_do_not_accumulate_seed_lines(memfs, monkeypatch, tmp_path):
    """Même exigence sur le chemin live : l'amorce `agent-output` est unique.

    Les 3 réponses ont des **longueurs différentes** : l'observation enregistre
    `Agent responded (<n> chars)`, donc trois tours de même longueur donneraient
    trois fois la même ligne — et `memory_append` la déduplique (`:248-250`),
    ce qui est le bon comportement (un fait identique ne se stocke pas deux fois).
    """
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")

    for i in range(3):
        _run_turn(
            monkeypatch,
            tmp_path,
            f"Question {i} : écris un petit script pour lister les fichiers du projet.",
            LONG_REPLY + (" " + "detail supplementaire " * (i + 1)),
        )

    text = (memfs.root / f"topics/{OBSERVED_DOMAIN}.md").read_text()
    assert text.count("[stated]") == 1, f"l'amorce s'accumule :\n{text}"
    assert text.count("[observed]") == 3, f"les 3 observations ne sont pas toutes la :\n{text}"


def test_an_identical_observation_is_not_stored_twice(memfs, monkeypatch, tmp_path):
    """Le dédoublonnage n'est pas un oubli : deux tours identiques donnent une
    seule observation. Sans ce test, « 3 tours ⇒ 3 lignes » pourrait passer pour
    une garantie alors que c'est un simple effet de bord de l'égalité des textes.
    """
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")

    for _ in range(2):
        _run_turn(
            monkeypatch,
            tmp_path,
            "Meme question : écris un petit script pour lister les fichiers.",
            LONG_REPLY,
        )

    text = (memfs.root / f"topics/{OBSERVED_DOMAIN}.md").read_text()
    assert text.count("[observed]") == 1, f"un fait identique a ete stocke deux fois :\n{text}"


# ─── Contre-épreuves ───────────────────────────────────────────────────────


def test_a_protected_turn_still_writes_nothing(memfs, monkeypatch, tmp_path):
    """L'amorce ne doit pas devenir une porte de service autour de la porte P17.

    Créer le fichier de domaine ne crée aucune entrée : un tour PROTECTED doit
    rester vide sur disque, sinon item 6 annulerait silencieusement l'item 1.
    """
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")

    _run_turn(
        monkeypatch,
        tmp_path,
        "Mon diagnostic médical est positif, concluez sur mon cas.",
        LONG_REPLY,
    )

    for domain in (OBSERVED_DOMAIN, IMPACT_DOMAIN):
        path = memfs.root / f"topics/{domain}.md"
        body = path.read_text() if path.exists() else ""
        assert "[observed]" not in body, f"P17 : une observation PROTECTED a atterri dans {domain}"
        assert "[inferred]" not in body, f"P17 : une inférence PROTECTED a atterri dans {domain}"


def test_an_unknown_domain_is_still_refused(memfs):
    """Le contrat testé ne doit pas régresser : l'amorce est un bootstrap
    d'`agent-output`, pas une généralisation qui efface le refus."""
    ok, msg = memfs.add_observed("domaine-inconnu", "quelque chose")

    assert not ok, "add_observed accepte maintenant n'importe quel domaine : le contrat testé a régressé"
    assert "does not exist" in msg


def test_the_profile_is_still_written(memfs, monkeypatch, tmp_path):
    """Contre-épreuve de non-régression : le tag `[stated]` du profil, lui, ne
    dépendait d'aucun amorçage et doit continuer de fonctionner."""
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")
    monkeypatch.setenv("ODYSSEUS_MEMORY_IMPACT", "off")

    _run_turn(
        monkeypatch,
        tmp_path,
        "Bonjour, écris un petit script pour lister les fichiers du projet.",
        LONG_REPLY,
    )

    assert (memfs.root / "profile.md").exists()
    assert "[stated]" in (memfs.root / "profile.md").read_text()


def test_the_reported_writes_match_what_is_on_disk(memfs, monkeypatch, tmp_path, caplog):
    """P16 — le log doit dire ce qui a atterri, pas l'inverse.

    C'est la moitié de la correction qui ne se voyait pas : l'ancien
    `"[m6.2] provenance memory updated"` sortait **inconditionnellement**, donc
    y compris quand les deux écritures avaient été refusées. Une affirmation de
    log non testée redevient un mensonge dès qu'un `if` change.

    La propriété vérifiée : les domaines nommés par le log sont exactement ceux
    dont une entrée a été écrite sur disque.
    """
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")

    with caplog.at_level(logging.INFO):
        _run_turn(
            monkeypatch,
            tmp_path,
            "Bonjour, écris un petit script pour lister les fichiers du projet.",
            LONG_REPLY,
        )

    reported = None
    for rec in caplog.records:
        m = re.search(r"provenance memory: (\d+) write\(s\) \[(.*?)\]", rec.getMessage())
        if m:
            reported = m
    assert reported is not None, "le bloc M6.2 n'a rien dit sur ce qu'il a écrit"

    claimed = {p.strip() for p in reported.group(2).split(",") if p.strip()}

    on_disk = set()
    for domain in (OBSERVED_DOMAIN,):
        path = memfs.root / f"topics/{domain}.md"
        if path.exists() and "[observed]" in path.read_text():
            on_disk.add(domain)
    if (memfs.root / "profile.md").exists() and "[stated]" in (memfs.root / "profile.md").read_text():
        on_disk.add("profile")

    assert claimed == on_disk, f"le log annonce {sorted(claimed)}, le disque dit {sorted(on_disk)}"
    assert int(reported.group(1)) == len(claimed), "le compte annonce ne correspond pas à la liste"
