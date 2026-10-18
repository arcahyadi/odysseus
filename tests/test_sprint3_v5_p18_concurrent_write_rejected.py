"""Sprint 3 v5 — item 10 (P18) — un jeton de version doit circuler entre deux appels.

Ce que la fiche `docs/traceability/02-PRINCIPES-UC.md` (P18) affirme, et ce que la
mesure dit de vrai. La fiche indique que « le jeton est lu et réémis dans le même
appel (`:237` → `:253`), donc le rejet ne peut pas se déclencher ».

**Cette partie de la fiche est fausse, et la mesure la corrige.** `memory_write`
RELIT le disque avant de comparer (`:220-223`) ; un jeton lu lors d'un appel
antérieur est donc bien rejeté, et un test le montre déjà
(`test_memory_append_version_mismatch`). Ce n'est pas là qu'est le défaut.

**La conclusion de la fiche est juste, mais l'endroit est ailleurs.** Les quatre
appelants de production — `add_stated:337`, `add_observed:348`, `add_inferred:359`,
`update_profile:381` — lisent ET appellent dans le même corps de fonction. Le
contrôle de version n'a donc **aucune route de production** : personne ne détient
jamais un jeton d'un tour au suivant. Un rejet qui n'est atteignable que depuis un
test n'est pas un contrôle.

**Et la mesure a trouvé mieux que ce que la fiche décrivait.** En plaçant la
barrière à l'intérieur de `memory_write`, entre la vérification et l'écriture, les
DEUX vérifications passent et les DEUX écritures ont lieu : un fait disparaît en
silence. Le jeton n'empêche la perte que quand la collision tombe entre la lecture
et la relecture — donc par chance d'ordonnancement, pas par garantie. C'est
exactement la faute que le principe « lire avant d'écrire » prétend fermer.

D'où les trois preuves de ce fichier :

* **preuve de fin** — le jeton circule entre deux tours de boucle distincts, un
  autre écrivain passe entre les deux, et le second tour voit son écriture
  **rejetée** puis **réessayée** ; le conflit est rapporté, pas avalé ;
* **contre-épreuve d'atomicité** — huit écrivains concurrents, huit faits, aucun
  ne disparaît (mesuré : sans correction, ils disparaissent) ;
* **contre-épreuve de durabilité** — une écriture interrompue ne détruit pas la
  version précédente.

Le test entre par la **boucle de production** (`stream_agent_loop`, bloc M6.2).
Appeler `MemoryFS` directement pour la preuve de fin mesurerait la classe et non le
système ; les contre-épreuves, elles, portent sur des propriétés de la couche de
stockage qu'aucun tour de boucle ne peut atteindre, et le disent.
"""

import asyncio
import json
import threading

import pytest

import src.agent_loop as al
import src.provenance_memory as pm

DOMAINE = "topics/agent-output.md"


# ─── Harnais ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def racine_memoire(tmp_path, monkeypatch):
    """Redirige la racine mémoire et reconstruit le singleton.

    `get_memory_fs()` mémoïse une instance capturée au premier appel ; sans la
    remettre à `None`, le test validerait la racine réelle du dépôt.
    """
    racine = tmp_path / "memory-fs"
    monkeypatch.setattr(pm, "MEMORY_ROOT", racine, raising=False)
    monkeypatch.setattr(pm, "_fs", None, raising=False)
    yield racine
    monkeypatch.setattr(pm, "_fs", None, raising=False)


def _fs():
    return pm.get_memory_fs()


def _un_tour(monkeypatch, session: str):
    """Fait tourner la boucle de production et renvoie ses événements.

    Le modèle est simulé ; la décision d'écrire, la classification, l'écriture et le
    rapport de conflit ne le sont pas.
    """
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")
    monkeypatch.setenv("ODYSSEUS_DATA_CLASSIFICATION", "on")

    async def _faux(_candidates, messages, **kw):
        yield (
            "data: "
            + json.dumps(
                {"delta": "Voici une reponse suffisamment longue pour etre observee et stockee."}
            )
            + "\n\n"
        )
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _faux, raising=False)

    async def _run():
        agen = al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": "bonjour, explique-moi la difference entre ces deux approches"}],
            max_rounds=2,
            relevant_tools={"list_sessions"},
            session_id=session,
        )
        evenements = []
        try:
            async for morceau in agen:
                if not morceau.startswith("data: "):
                    continue
                try:
                    evenements.append(json.loads(morceau[6:].strip()))
                except ValueError:
                    continue
        finally:
            await agen.aclose()
        return evenements

    return asyncio.run(_run())


# ─── La preuve de fin ───────────────────────────────────────────────────────


def test_a_token_from_an_earlier_turn_is_rejected_then_retried(monkeypatch, racine_memoire):
    """PREUVE DE FIN : le jeton circule, le conflit est rejeté, puis réessayé.

    Tour 1 : la boucle écrit et **retient** le jeton.
    Entre les deux : un autre écrivain modifie le fichier — c'est un tour
    concurrent, écrit par l'API publique du stockage.
    Tour 2 : la boucle présente le jeton du tour 1, désormais périmé. Elle doit
    être **rejetée**, le conflit **rapporté** (événement de flux, pas seulement un
    log), et le fait **tout de même** atterrir — parce qu'un rejet silencieusement
    perdu serait un autre principe qui ment sur lui-même.
    """
    evenements_1 = _un_tour(monkeypatch, session="sess-p18-a")
    assert evenements_1, "le premier tour n'a produit aucun evenement"

    contenu_1, jeton_1 = _fs().memory_read(DOMAINE)
    assert contenu_1 is not None, f"le premier tour n'a rien ecrit sous {racine_memoire}"
    assert jeton_1, "le premier tour n'a rendu aucun jeton : rien ne peut circuler"

    # Un ecrivain concurrent passe entre les deux tours.
    ok, _ = _fs().memory_write(DOMAINE, contenu_1 + "- [observed] ecrivain concurrent\n", jeton_1)
    assert ok, "le second tour: l'ecrivain concurrent n'a pas reussi a ecrire"

    evenements_2 = _un_tour(monkeypatch, session="sess-p18-b")

    conflits = [e for e in evenements_2 if e.get("type") == "memory_conflict"]
    assert conflits, (
        f"aucun conflit n'est rapporte alors que le jeton present etait perime. "
        f"Evenements : {sorted({e.get('type') for e in evenements_2 if e.get('type')})}"
    )
    assert conflits[0]["expected"] == jeton_1, (
        f"le conflit ne rapporte pas le jeton refute : {conflits[0]}"
    )
    assert conflits[0]["actual"] != jeton_1, (
        f"le conflit rapporte un jeton identique a celui presente : il n'y a pas eu conflit. {conflits[0]}"
    )

    contenu_final, _ = _fs().memory_read(DOMAINE)
    assert "- [observed] ecrivain concurrent" in contenu_final, (
        "l'ecrivain concurrent a ete ecrase : la reprise a ecrase au lieu de fusionner"
    )
    assert contenu_final.count("[observed]") >= 2, (
        f"le fait du second tour n'a pas atterri apres le conflit : {contenu_final!r}"
    )


# ─── Contre-épreuves ────────────────────────────────────────────────────────


def test_concurrent_writers_never_lose_a_fact(racine_memoire):
    """CONTRE-ÉPREUVE d'atomicité : huit écrivains, huit faits, aucune perte.

    C'est la régression directe de la mesure : avec la vérification et l'écriture
    dans deux temps, la moitié des faits disparaît selon l'ordonnancement. Le
    contrôle de version ne protégeait que le cas où la collision tombait entre la
    lecture et la relecture.

    Huit fils plutôt que deux : à deux, une collision peut ne pas se produire et le
    test passerait par chance — c'est le défaut qu'un test qui « passe parfois »
    installe. Huit sur le même fichier la rendent systématique.
    """
    _fs().memory_write(DOMAINE, "depart\n", "new")

    N = 8
    barrier = threading.Barrier(N)
    resultats: list[bool] = []
    verrou = threading.Lock()

    def _ecrire(i: int) -> None:
        fs = _fs()
        barrier.wait()
        ok, _ = fs.add_observed("agent-output", f"fait concurrent numero {i}")
        with verrou:
            resultats.append(ok)

    fils = [threading.Thread(target=_ecrire, args=(i,)) for i in range(N)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=30)

    assert len(resultats) == N, f"{len(resultats)}/{N} écrivains n'ont pas rendu de verdict"
    assert all(resultats), f"des écrivains ont echoue : {resultats}"

    contenu, _ = _fs().memory_read(DOMAINE)
    manquant = [i for i in range(N) if f"fait concurrent numero {i}" not in contenu]
    assert not manquant, (
        f"{len(manquant)} fait(s) disparu(s) en silence : {manquant}. "
        "Un fait perdu n'est pas une ecriture rejetee, c'est une donnee perdue."
    )


def test_an_interrupted_write_leaves_the_previous_version_intact(racine_memoire, monkeypatch):
    """CONTRE-ÉPREUVE de durabilité : une écriture coupée ne détruit rien.

    `write_text` écrit dans le fichier cible : un process tué au milieu laisse un
    fichier mémoire tronqué, et la version précédente — celle que le jeton désigne
    — a disparu. Le remplacement atomique (fichier temporaire puis `os.replace`)
    rend l'opération indivisible : il y a une version complète avant, une après,
    jamais une entre les deux.
    """
    fs = _fs()
    fs.memory_write(DOMAINE, "version complete\n", "new")
    _, jeton = fs.memory_read(DOMAINE)

    vrai_remplacement = pm.os.replace

    def _coupable(src, dst):
        raise OSError("process tue au milieu de l'ecriture")

    monkeypatch.setattr(pm.os, "replace", _coupable)
    ok, msg = fs.memory_write(DOMAINE, "version suivante\n", jeton)
    monkeypatch.setattr(pm.os, "replace", vrai_remplacement)

    assert not ok, f"une ecriture interrompue a ete rapportee comme reussie : {msg!r}"
    contenu, jeton_apres = fs.memory_read(DOMAINE)
    assert contenu == "version complete\n", (
        f"la version precedente a ete detruite par une ecriture interrompue : {contenu!r}"
    )
    assert jeton_apres == jeton, "le jeton a change alors que rien n'a ete ecrit"


def test_only_one_of_two_identical_writes_survives(racine_memoire):
    """CONTRE-ÉPREUVE du stockage nu : un jeton ne sert qu'une fois.

    Les contre-épreuves d'atomicité passent toutes par `append_cas`, qui tient le
    verrou de bout en bout. Le verrou de `memory_write` lui-même n'était donc
    jamais mis à l'épreuve par le chemin le plus direct : deux écrivains
    présentant le MÊME jeton. Si ce verrou n'existait pas, les deux écritures
    passeraient et la seconde écraserait la première en silence — le défaut
    exact, à un niveau plus bas. Un garde-fou non éprouvé par sa propre route
    devient décoratif ; celui-ci a donc sa preuve.
    """
    fs = _fs()
    fs.memory_write(DOMAINE, "contenu de depart\\n", "new")
    _, jeton = fs.memory_read(DOMAINE)

    N = 8
    barrier = threading.Barrier(N)
    verdicts: list[bool] = []
    verrou = threading.Lock()

    def _ecrire(i: int) -> None:
        barrier.wait()
        ok, _ = _fs().memory_write(DOMAINE, f"contenu {i}\\n", jeton)
        with verrou:
            verdicts.append(ok)

    fils = [threading.Thread(target=_ecrire, args=(i,)) for i in range(N)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=30)

    assert sum(verdicts) == 1, (
        f"{sum(verdicts)} ecritures ont accepte le meme jeton au lieu d'une seule : "
        "le jeton ne controle plus rien"
    )
    contenu, _ = _fs().memory_read(DOMAINE)
    assert contenu.startswith("contenu de depart\\n") or contenu.startswith("contenu ")


def test_a_stale_token_is_refused_rather_than_overwriting(racine_memoire):
    """CONTRE-ÉPREUVE du contrat : un jeton périmé ne peut pas écraser.

    Le principe tient sans boucle, sans thread et sans course : un jeton qui ne
    correspond plus est refusé. C'est le contrat que la version précédente de ce
    document affirmait déjà porter — on le vérifie directement pour qu'un refactor
    du stockage ne puisse pas le perdre en silence.
    """
    fs = _fs()
    fs.memory_write(DOMAINE, "contenu initial\n", "new")
    _, jeton = fs.memory_read(DOMAINE)
    ok, _ = fs.memory_write(DOMAINE, "contenu remplace\n", jeton)
    assert ok

    ok, msg = fs.memory_write(DOMAINE, "contenu obsolete\n", jeton)

    assert not ok, "un jeton perime a ete accepte : le controle de version ne controle rien"
    assert "Version mismatch" in msg
    contenu, _ = fs.memory_read(DOMAINE)
    assert "contenu obsolete" not in contenu
    assert "contenu remplace" in contenu, "le jeton perime a ecrase la version courante"


def test_writing_without_a_token_keeps_working(racine_memoire):
    """CONTRE-ÉPREUVE de non-régression : le contrat existant ne change pas.

    `add_observed` sans jeton continue de relire puis d'écrire. Le verrou ne doit
    pas rendre l'API fautive, et les tests d'hier doivent rester vrais.

    Le domaine est d'abord semé : `add_observed` refuse d'écrire un fichier de
    domaine inexistant (contrat P16, `provenance_memory.py:344-346`), ce qui n'a
    rien à voir avec le verrou et ferait échouer le test pour une autre raison.
    """
    fs = _fs()
    assert fs.add_stated("agent-output", "graine")[0], "le domaine n'a pas pu etre seme"
    ok, _ = fs.add_observed("agent-output", "premier fait")
    assert ok, "add_observed sans jeton a echoue : le verrou a casse l'ecriture simple"
    ok, _ = fs.add_observed("agent-output", "second fait")
    assert ok

    contenu, _ = fs.memory_read(DOMAINE)
    assert "premier fait" in contenu and "second fait" in contenu
