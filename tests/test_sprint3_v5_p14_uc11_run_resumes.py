"""Sprint 3 v5 item 8 — un run interrompu puis relancé doit **reprendre**.

Le défaut
---------
`DurableExecutor.create_workflow` (`src/durable_execution.py:113`) n'a **aucun
appelant**. Rien n'est donc jamais persisté, `data/workflows/` reste vide, et
`resume()` renvoie toujours `None`.

Pire : le bloc M6.3 qui appelle `resume()` est à `agent_loop.py:4553`, c'est-à-dire
**après** la boucle de rounds. Il ne pouvait donc rien restaurer même si le fichier
avait existé — il ne faisait que journaliser. C'est le reliquat R2 du rapport v4 :
l'unique action de `resume()` était un `logger.info`.

La preuve de fin
----------------
« Relancé » ne veut pas dire « recommencé ». La property vérifiée est qu'un deuxieme
stream sur la meme session **reprend au round ou le premier s'est arrete**, au lieu de
redemander au modele depuis le debut. C'est observable dans le flux : le deuxieme run
annonce son round de depart, et le modele recoit la conversation deja avancee.

Comment le run est « interrompu »
---------------------------------
En **consommant le generateur et en le fermant** au milieu du flux — exactement ce que
fait un client qui se deconnecte, ou un serveur qui redemarre. Fermer un generateur
async est une vraie interruption : le code apres le `yield` n'est pas execute, donc
aucun bloc de finalisation ne peut sauver le run. C'est ce qui distingue cet item d'un
test qui simule l'interruption en appelant un helper.

Ce que le test ne prétend pas
-----------------------------
Il ne teste pas `DurableExecutor` en isolation : `resume()` et `create_workflow()`
fonctionnaient deja, ils n'etaient simplement appeles par personne. Le test entre par la
route de production — `stream_agent_loop` — parce que c'est la seule ou le defaut
existe.
"""

import asyncio
import json
import pathlib

import pytest

import src.agent_loop as al
import src.durable_execution as dex

SUBSTANTIAL = "bonjour, explique-moi la différence entre ces deux approches"

# Outils proposés : aucun ne doit être bloqué par la porte propriétaire, sinon on
# mesurerait cette porte-là au lieu de la reprise.
OFFERED = {"list_sessions", "list_models", "web_search", "ask_user", "create_document", "update_plan"}


@pytest.fixture(autouse=True)
def workflow_dir(monkeypatch, tmp_path):
    """Redirige la persistance vers un répertoire temporaire.

    `WORKFLOW_DIR` est ancré sur le module (et non sur le CWD) pour qu'une reprise
    survive au crash qu'elle traite : c'est le défaut que cet item corrige. Conséquence
    pour les tests : un `chdir` ne redirige plus l'écriture, il faut le dire
    explicitement — sinon le test écrit dans le dépôt et passe pour une preuve alors
    qu'il pollue.
    """
    target = tmp_path / "data" / "workflows"
    monkeypatch.setattr(dex, "WORKFLOW_DIR", target)
    return target


def _drain(monkeypatch, tmp_path, *, session_id, stop_after_round=None):
    """Un tour réel. `stop_after_round` ferme le générateur après ce round = interruption.

    Retourne (phases, rounds_vus_par_le_modele, evenements).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_DURABLE_EXECUTION", "on")
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", "on")

    rounds_seen: list[int] = []
    events: list[dict] = []

    async def _fake_stream(_candidates, messages, **kw):
        rounds_seen.append(len(messages))
        n = len(rounds_seen)
        if n < 3:
            yield "data: " + json.dumps(
                {"type": "tool_calls", "calls": [{"id": f"c{n}", "name": "list_sessions", "arguments": "{}"}]}
            ) + "\n\n"
        else:
            yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    async def _run():
        agen = al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": SUBSTANTIAL}],
            max_rounds=5,
            relevant_tools=set(OFFERED),
            session_id=session_id,
        )
        current_round = 0
        try:
            async for chunk in agen:
                if not chunk.startswith("data: "):
                    continue
                try:
                    ev = json.loads(chunk[6:].strip())
                except ValueError:
                    continue
                events.append(ev)
                if ev.get("type") == "agent_step":
                    current_round = ev.get("round", current_round)
                if stop_after_round is not None and current_round >= stop_after_round:
                    break
        finally:
            await agen.aclose()

    asyncio.run(_run())
    return rounds_seen, events


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_an_interrupted_run_is_resumed_not_restarted(monkeypatch, tmp_path):
    """PREUVE DE FIN : le relancement continue, il ne repart pas de zéro.

    Échoue sur le code d'aujourd'hui : le premier run n'écrit rien, donc le second
    repart de la conversation initiale et le modèle voit la même chose qu'au premier
    tour — c'est-à-dire qu'il n'y a **aucune** reprise.
    """
    session = "sess-resume-item8"

    # Run 1 : interrompu après le round 2 (le générateur est fermé en plein flux).
    first_rounds, _ = _drain(monkeypatch, tmp_path, session_id=session, stop_after_round=2)
    assert first_rounds, "le premier run n'a pas appelle le modele : le test ne prouve rien"

    # Run 2 : même session, relance après l'interruption.
    second_rounds, _ = _drain(monkeypatch, tmp_path, session_id=session)

    assert second_rounds, "le run relance n'a pas appele le modele"
    assert second_rounds[0] > first_rounds[0], (
        f"le run relance repart de zero : le modele a vu {second_rounds[0]} messages, "
        f"comme au premier tour ({first_rounds[0]}). La conversation n'a pas ete reprise."
    )


def test_the_resume_is_announced_in_the_stream(monkeypatch, tmp_path):
    """La reprise doit être visible dans le flux, pas seulement dans un log.

    Un utilisateur dont le run a repris doit pouvoir le voir ; et un diagnostic qui ne se
    voit pas ne se distingue pas d'un redémarrage silencieux.
    """
    session = "sess-resume-visible"
    _drain(monkeypatch, tmp_path, session_id=session, stop_after_round=2)
    _, events = _drain(monkeypatch, tmp_path, session_id=session)

    types = {ev.get("type") for ev in events}
    assert "run_resumed" in types, (
        f"aucun evenement de reprise dans le flux (types vus : {sorted(t for t in types if t)})"
    )


def test_the_durable_state_survives_as_a_file(monkeypatch, tmp_path, workflow_dir):
    """Contre-épreuve de réalisme : l'état doit être SUR DISQUE, pas en mémoire.

    Une reprise qui ne survivrait pas au process n'aurait aucun intérêt : le cas d'usage
    est précisément le crash. On vérifie donc le fichier, pas seulement le comportement.
    """
    session = "sess-resume-disk"
    _drain(monkeypatch, tmp_path, session_id=session, stop_after_round=2)

    files = list(workflow_dir.glob("*.json"))
    assert files, "rien n'a ete persiste : la reprise ne survivrait pas a un crash"
    payload = json.loads(files[0].read_text())
    assert payload.get("context", {}).get("messages"), "l'etat persiste ne contient pas la conversation"


def test_the_state_is_anchored_not_relative_to_the_working_directory(monkeypatch, tmp_path, workflow_dir):
    """PREUVE de la cause racine : la reprise fonctionne depuis n'importe quel CWD.

    Une reprise stockée sous le CWD du process d'avant n'est pas trouvée par le process
    suivant s'il démarre ailleurs — et le cas d'usage étant le crash, changer de
    répertoire au redémarrage est la norme, pas l'exception. On change donc de CWD entre
    les deux tours, et on exige la vraie preuve : le second tour doit se declarer repris.
    """
    session = "sess-ancre"
    _drain(monkeypatch, tmp_path, session_id=session, stop_after_round=2)

    autre_cwd = tmp_path / "ailleurs"
    autre_cwd.mkdir()
    monkeypatch.chdir(autre_cwd)

    _, events = _drain(monkeypatch, tmp_path, session_id=session)
    assert "run_resumed" in {e.get("type") for e in events}, (
        "la reprise n'a pas ete trouvee depuis un autre CWD : l'etat est encore stocke "
        "relativement au repertoire du process"
    )


def test_retention_keeps_one_run_per_session(monkeypatch, tmp_path, workflow_dir):
    """Contre-épreuve de ressources : la rétention borne la croissance du répertoire.

    Ce module n'écrivait rien du tout jusqu'à cet item. Sans rétention, il laisserait un
    fichier par tour et par session, et la recherche de reprise parcourrait tout le
    répertoire à chaque tour. Une session ne doit donc conserver que son run courant.
    """
    session = "sess-retention"
    for _ in range(3):
        _drain(monkeypatch, tmp_path, session_id=session)

    fichiers = list(workflow_dir.glob("*.json"))
    assert len(fichiers) == 1, f"la retention doit laisser 1 run par session, trouve {len(fichiers)}"


def test_retention_does_not_touch_another_session(monkeypatch, tmp_path, workflow_dir):
    """Contre-épreuve de cloisonnement : la rétention ne doit pas manger le voisin.

    Une suppression trop large supprimerait l'état d'une autre session, qui ne pourrait
    alors plus reprendre. On vérifie que les deux survivent à plusieurs tours.
    """
    _drain(monkeypatch, tmp_path, session_id="sess-A")
    _drain(monkeypatch, tmp_path, session_id="sess-B")
    _drain(monkeypatch, tmp_path, session_id="sess-A")
    _drain(monkeypatch, tmp_path, session_id="sess-B")

    noms = {json.loads(p.read_text()).get("name") for p in workflow_dir.glob("*.json")}
    assert noms == {"sess-A", "sess-B"}, f"la retention a touche une autre session : {noms}"


def test_the_default_state_path_does_not_depend_on_the_working_directory(monkeypatch):
    """PREUVE de la cause racine, au niveau de la DÉFAUT : le chemin est ancré.

    Deux raisons pour lesquelles ce test est à part, et pas dans le flux habituel :

    * les autres tests redirigent `WORKFLOW_DIR` vers un répertoire temporaire, ce qui les
      rend aveugles à cette propriété — la mutation « chemin relatif au CWD » les
      laissait tous passer. Mesuré, puis comblé ;
    * le fixture `autouse` ci-dessus patche justement l'attribut que ce test veut lire
      dans son état par défaut. `monkeypatch.undo()` annule ce patch pour que la valeur
      d'origine soit observée, et rien d'autre n'est relâché ensuite.

    Un chemin relatif au CWD ferait dépendre la reprise du répertoire de lancement : le
    fichier écrit par le process d'avant n'est pas trouvé par le suivant — c'est-à-dire
    que la reprise échoue précisément dans le cas du crash qu'elle corrige.
    """
    monkeypatch.undo()
    defaut = dex.WORKFLOW_DIR

    assert defaut.is_absolute(), f"le chemin par defaut est relatif : {defaut}"
    assert ".." not in defaut.parts, f"le chemin par defaut remonte a la racine : {defaut}"
    racine_module = pathlib.Path(dex.__file__).resolve().parent.parent
    assert racine_module in defaut.parents, (
        f"{defaut} n'est pas ancre sur le projet ({racine_module}) : il depend du CWD"
    )


def test_a_new_user_turn_is_never_clobbered_by_a_stale_run(monkeypatch, tmp_path):
    """PREUVE DE NON-RÉGRESSION : une nouvelle question n'est jamais écrasée.

    C'est le danger que la reprise introduit et qu'aucun des autres tests ne couvre. Un
    run interrompu laisse un état persisté ; si l'utilisateur ne se reconnecte pas mais
    pose une *autre* question sur la même session, restaurer l'ancien état remplacerait
    sa saisie par l'ancienne conversation — silencieusement, sans erreur, sans trace.

    Le test envoie donc une question DIFFÉRENTE après l'interruption, et exige que le
    modèle la voie. C'est le test qui interdit la régression la plus grave de cet item.
    """
    session = "sess-nouvelle-question"
    _drain(monkeypatch, tmp_path, session_id=session, stop_after_round=2)

    nouvelle = "attends, parle-moi plutot de la securite des mots de passe"
    vus: list[list] = []

    async def _fake_stream(_candidates, messages, **kw):
        vus.append(list(messages))
        yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_DURABLE_EXECUTION", "on")
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", "on")
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    async def _run():
        agen = al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": nouvelle}],
            max_rounds=1,
            relevant_tools=set(OFFERED),
            session_id=session,
        )
        try:
            async for _ in agen:
                pass
        finally:
            await agen.aclose()

    asyncio.run(_run())

    assert vus, "le run n'a pas appele le modele : le test ne prouve rien"
    contenu = json.dumps(vus[0], ensure_ascii=False)
    assert nouvelle in contenu, (
        "la nouvelle question de l'utilisateur a disparu de la conversation envoyee au "
        "modele : l'etat persiste d'un run anterieur l'a ecrasee"
    )


# ─── Contre-épreuves ───────────────────────────────────────────────────────


def test_a_fresh_session_is_not_announced_as_resumed(monkeypatch, tmp_path):
    """Contre-épreuve : une session neuve ne doit PAS prétendre reprendre.

    C'est le défaut miroir du précédent : un « run_resumed » annoncé à chaque démarrage
    rendrait l'événement vide de sens et masquerait les vraies reprises.
    """
    _, events = _drain(monkeypatch, tmp_path, session_id="sess-neuf-v5")

    types = {ev.get("type") for ev in events}
    assert "run_resumed" not in types, "une session sans etat anterieur s'est annoncee comme reprise"


def test_a_completed_run_leaves_nothing_to_resume(monkeypatch, tmp_path):
    """Contre-épreuve : un run terminé ne doit pas ressusciter au lancement suivant.

    Sans cette property, la « reprise » réintroduirait indéfiniment une conversation
    vieille, et le tour suivant de l'utilisateur repartirait de l'ancien contexte.
    """
    session = "sess-complete"
    _drain(monkeypatch, tmp_path, session_id=session)  # va jusqu'au bout
    _, events = _drain(monkeypatch, tmp_path, session_id=session)

    types = {ev.get("type") for ev in events}
    assert "run_resumed" not in types, "un run deja termine a ete repris comme s'il etait interrompu"


def test_the_kill_switch_off_disables_the_persistence(monkeypatch, tmp_path, workflow_dir):
    """`DURABLE_EXECUTION=off` doit ne rien écrire du tout.

    Le switch est `on` par défaut depuis le Palier 0, donc c'est le chemin nominal qu'on
    teste ; le chemin éteint doit rester un vrai no-op, sinon « désactivé » ne veut rien
    dire et la régression passerait inaperçue.
    """
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_DURABLE_EXECUTION", "off")
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", "on")

    async def _fake_stream(_candidates, _messages, **kw):
        yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    async def _run():
        async for _ in al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": SUBSTANTIAL}],
            max_rounds=1,
            relevant_tools=set(OFFERED),
            session_id="sess-switch-off",
        ):
            pass

    asyncio.run(_run())

    assert not list(workflow_dir.glob("*.json")), (
        "le switch etait off mais un etat a ete ecrit sur disque"
    )


@pytest.mark.parametrize("interrompu, attendu_reprise", [(True, True), (False, False)])
def test_la_reprise_ne_dépend_que_de_l_interruption(monkeypatch, tmp_path, interrompu, attendu_reprise):
    """Property de causalité : la reprise est causée par l'interruption, rien d'autre.

    Sans ce test, on ne saurait pas si le deuxième run « reprend » parce qu'on l'a
    interrompu, ou simplement parce que deux runs consécutifs existent — auquel cas la
    preuve de fin ne prouverait rien du tout.
    """
    session = f"sess-causal-{interrompu}"
    _drain(monkeypatch, tmp_path, session_id=session, stop_after_round=2 if interrompu else None)
    _, events = _drain(monkeypatch, tmp_path, session_id=session)

    a_ete_repris = "run_resumed" in {ev.get("type") for ev in events}
    assert a_ete_repris is attendu_reprise, (
        f"interrompu={interrompu}, reprise={a_ete_repris}, attendu={attendu_reprise}"
    )
