"""Sprint 3 v5 — item 9 (UC-12) — une décision AUTOEVAL doit être AUDITABLE.

Ce que la fiche `docs/traceability/02-PRINCIPES-UC.md` (UC-12) mesure :

* les traces **sont** écrites (`tool_execution.py:672` → `data/traces/*.jsonl`) ;
* mais `trace_writer.py` n'expose **aucune fonction de lecture** et **aucune route**
  ne lit ce fichier.

Et ce que le plan (`SPRINT-3-PLAN.md`, item 9) exige comme preuve de fin :
« `GET /api/audit/traces` rend ce qu'`autoeval` a décidé ».

Mesure préalable, avant d'écrire la moindre ligne : la décision elle-même **n'était
écrite nulle part**. `apply_autoeval` la calcule, la boucle la journalise
(`agent_loop.py:4449`) et l'émet dans le flux SSE (`autoeval_result`) — donc un client
qui se déconnecte avant la fin perd la décision, et personne ne peut la relire après.
Il y a donc deux trous, pas un : rien n'est écrit, et ce qui est écrit n'est pas lisible.

D'où les deux faces de la preuve :

* **la route** rend la décision prise par la boucle, en passant par HTTP ;
* **le disque** la conserve — la route n'est pas une projection en mémoire, et le test
  ne se contente pas d'un `get_traces()` appelé directement.

Le test entre par la **route de production** (`stream_agent_loop`) pour l'écriture, et
par la **route HTTP** pour la lecture. Appeler `write_decision()` ou `read_traces()`
depuis le test mesurerait mes propres fonctions, pas le système.
"""

import asyncio
import contextvars
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.agent_loop as al
from routes.audit_routes import router
from src import constants, trace_writer
from src.observer import DriftLevel, Observer

# Outils proposés : aucun ne doit être bloqué par la porte propriétaire, sinon on
# mesurerait cette porte-là au lieu de l'audit.
OFFERED = {"list_sessions", "list_models", "web_search", "ask_user", "create_document", "update_plan"}


# ─── Harnais ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def run_id_isole():
    """Remplace le ContextVar du `run_id` pour ce test, puis rend l'ancien.

    Mesuré, pas supposé : `ContextVar.set` écrit dans le contexte du thread de
    test et y reste. Sans cette isolation, `test_the_route_can_isolate_one_run`
    qui fixe `run-A` puis `run-B` laisse le process entier avec `run-B`, et
    `test_trace_writer_run_id.py::test_current_run_id_defaults_to_nonempty_uuid`
    échoue — mais seulement selon l'ordre de collecte. C'est exactement la fuite
    d'état global que la norme de test interdit, trouvée par le-suite, pas par
    la théorie.
    """
    precedente = trace_writer._run_id_var
    trace_writer._run_id_var = contextvars.ContextVar("trace_run_id", default=str(uuid.uuid4()))
    yield
    trace_writer._run_id_var = precedente


@pytest.fixture(autouse=True)
def traces_dir(monkeypatch, tmp_path):
    """Redirige `DATA_DIR` — l'unique source de vérité des fichiers persistés.

    On patche la constante et pas le répertoire calculé : c'est ce qui prouve que la
    lecture et l'écriture empruntent le **même** chemin. Un test qui patcherait
    `trace_writer._traces_dir` validerait un chemin qu'aucun appelant réel n'utilise.
    """
    cible = tmp_path / "data"
    monkeypatch.setattr(constants, "DATA_DIR", str(cible), raising=False)
    return cible / "traces"


def _faux_modele(nuev_appels: list):
    """LLM qui appelle un outil puis répond — le seul chemin qui fait tourner les rounds."""

    async def _stream(_candidates, messages, **kw):
        nuev_appels.append(list(messages))
        if len(nuev_appels) < 2:
            yield (
                "data: "
                + json.dumps({"type": "tool_calls", "calls": [{"id": "c1", "name": "list_sessions", "arguments": "{}"}]})
                + "\n\n"
            )
        else:
            yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    return _stream


def _client(*, auth: str) -> TestClient:
    """App minimale portant le routeur d'audit.

    `auth` vaut `admin`, `user` ou `none`. Le client se construit sur un `auth_manager`
    minimal et un middleware qui estampille `current_user` — c'est le contrat que
    `require_admin` attend, et le chemin est identique à celui du vrai middleware.
    """
    app = FastAPI()

    if auth != "none":
        app.state.auth_manager = SimpleNamespace(
            is_configured=True,
            is_admin=lambda u: u == "admin",
        )
        identite = "admin" if auth == "admin" else "simple-utilisateur"

        @app.middleware("http")
        async def _stamp(request, call_next):
            request.state.current_user = identite
            return await call_next(request)

    app.include_router(router)
    return TestClient(app)


def _un_run(monkeypatch, *, session: str, drift: str, faux_modele=None, demande: str = None):
    """Fait tourner la boucle de production et renvoie (appels modèle, événements).

    `drift` vaut `"high"` ou `"low"` et remplace **l'entrée** de la décision, pas la
    décision : `decide_keep_or_revert` (`autoeval.py:86`) revertit sur drift HIGH, et le
    code qui décide, écrit et lit reste le vrai.

    Pourquoi le drift et non un verdict FAIL du vérificateur : ce verdict ne se déclenche
    qu'après un outil « effectful » (`_VERIFIER_EFFECTFUL_TOOLS`, `:2033`), donc le test
    devrait faire écrire un document ou lancer un shell pour obtenir une décision. On
    simule donc l'entrée la moins destructrice des deux, et on garde la preuve au niveau
    de l'entrée — le reste est le vrai système.
    """
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL_ALLOW_RESET", "off")
    monkeypatch.setenv("ODYSSEUS_PROGRESSIVE_DISCLOSURE", "on")
    monkeypatch.setenv("ODYSSEUS_DATA_CLASSIFICATION", "on")

    niveau = DriftLevel.HIGH if drift == "high" else DriftLevel.LOW
    monkeypatch.setattr(Observer, "compute_drift_score", lambda self: niveau, raising=False)

    nuev_appels: list = []
    monkeypatch.setattr(
        al,
        "stream_llm_with_fallback",
        faux_modele or _faux_modele(nuev_appels),
        raising=False,
    )

    async def _run():
        agen = al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": demande or "bonjour, explique-moi la difference entre ces deux approches"}],
            max_rounds=3,
            relevant_tools=set(OFFERED),
            session_id=session,
        )
        evenements = []
        try:
            async for morceau in agen:
                if not morceau.startswith("data: "):
                    continue
                try:
                    ev = json.loads(morceau[6:].strip())
                except ValueError:
                    continue
                evenements.append(ev)
        finally:
            await agen.aclose()
        return evenements

    return nuev_appels, asyncio.run(_run())


# ─── La preuve de fin ──────────────────────────────────────────────────────


def test_the_audit_route_renders_the_decision_autoeval_took(monkeypatch):
    """PREUVE DE FIN : la route rend la décision que la boucle a réellement prise.

    L'Observer rapporte un drift HIGH, donc la politique conservatrice impose `revert`. La
    route doit rendre cette décision — lisible par HTTP, donc par quiconque interroge le
    serveur, et non seulement présente dans le flux SSE que le client avait consommé.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    _un_run(monkeypatch, session="sess-audit-revert", drift="high")

    rep = _client(auth="admin").get("/api/audit/traces", params={"kind": "decision"})

    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["traces"], f"la route n'a rien rendu : {corps}"
    assert all(t.get("kind") == "decision" for t in corps["traces"]), (
        f"kind=decision a renvoyé autre chose : {[t.get('kind') for t in corps['traces']]}"
    )
    decisions = corps["traces"]
    assert decisions[-1]["decision"] == "revert", (
        f"la décision rendue n'est pas celle prise : {decisions[-1]}"
    )


def test_the_decision_outlives_the_stream_that_carried_it(monkeypatch, traces_dir):
    """PREUVE que la route n'est pas une projection en mémoire.

    Le flux SSE s'éteint avec le client ; un audit, non. Le test relit le **disque**
    sans passer par la route HTTP, et exige la même décision : c'est ce qui distingue
    « on a écrit quelque part » de « on a écrit dans le fichier que la route lit ».
    """
    _un_run(monkeypatch, session="sess-audit-disque", drift="high")

    fichiers = sorted(traces_dir.glob("*.jsonl"))
    assert fichiers, f"aucun fichier de trace sous {traces_dir} : rien n'a ete conserve"
    lignes = [json.loads(lgn) for lgn in fichiers[-1].read_text().splitlines() if lgn.strip()]

    decisions = [lgn for lgn in lignes if lgn.get("kind") == "decision"]
    assert decisions, f"la décision n'est pas sur le disque : {lignes[:3]}"
    assert decisions[-1]["decision"] == "revert"
    assert decisions[-1]["drift_level"] == "high", (
        "le motif de la décision n'est pas conservé : un audit qui ne dit pas pourquoi "
        "n'est pas un audit"
    )
    assert decisions[-1]["reverted"] is False, (
        "`reverted` doit rester distinct de `decision` : AUTOEVAL décide 'revert' alors que "
        "ODYSSEUS_AUTOEVAL_ALLOW_RESET est OFF — confondre les deux ferait croire à un "
        "git reset --hard qui n'a pas eu lieu"
    )
    assert decisions[-1]["run_id"], "la décision n'est rattachée à aucun run : elle n'est pas rejoignable"


def test_a_run_that_passed_is_audited_as_keep(monkeypatch):
    """PREUVE de non-régression : un run qui passe est tracé comme `keep`.

    Une route qui ne rendrait que les échecs donnerait une image biaisée de l'audit :
    on ne saurait jamais si le système functioned ou s'il ne disait rien.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    _un_run(monkeypatch, session="sess-audit-keep", drift="low")

    corps = _client(auth="admin").get("/api/audit/traces", params={"kind": "decision"}).json()

    decisions = [t for t in corps["traces"] if t.get("kind") == "decision"]
    assert decisions, "un run qui passe ne laisse aucune trace : l'audit ne couvre que les échecs"
    assert decisions[-1]["decision"] == "keep"


# ─── Contre-épreuves ───────────────────────────────────────────────────────


def test_reading_the_audit_does_not_bring_it_into_existence(monkeypatch, traces_dir):
    """CONTRE-ÉPREUVE de sémantique : lire ne fabrique pas ce qu'elle inspecte.

    Le lecteur résout son chemin par un calculateur non createur, distinct de celui du
    writer. Si les deux se confondent, la route d'audit crée le dossier à sa première
    lecture, et « la piste est vide » devient indiscernable de « la piste n'existe pas
    encore » — deux réponses opposées. Le test vérifie l'absence de dossier, pas le
    contenu rendu.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    assert not traces_dir.exists(), "le harnais a deja cree le dossier : le test ne prouve rien"

    rep = _client(auth="admin").get("/api/audit/traces")

    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["traces"] == [] and corps["ok"] is True
    assert not traces_dir.exists(), (
        f"la lecture a cree {traces_dir} : une route d'audit qui fabrique son propre "
        "répertoire rend une absence de données indiscernable d'une absence de piste"
    )


def test_an_unconfigured_auth_refuses_the_audit_trail(monkeypatch):
    """CONTRE-ÉPREUVE de posture : sans authentification configurée, la route refuse.

    `AUTH_ENABLED=false` est le court-circuit de développement ; c'est la seule voie par
    laquelle la lecture est possible sans identité. Le cas par défaut — aucun
    `auth_manager` — doit être un refus, jamais une fuite.
    """
    monkeypatch.setenv("AUTH_ENABLED", "true")
    rep = _client(auth="none").get("/api/audit/traces")

    assert rep.status_code == 403, f"la fuite d'audit sans authentification est possible : {rep.status_code}"


def test_a_non_admin_cannot_read_the_audit_trail(monkeypatch):
    """CONTRE-ÉPREUVE de cloisonnement : un utilisateur simple ne lit pas l'audit.

    Les traces portent les arguments des outils et les motifs de décision. Ce n'est pas
    de la télémétrie anodine.
    """
    monkeypatch.setenv("AUTH_ENABLED", "true")
    rep = _client(auth="user").get("/api/audit/traces")

    assert rep.status_code == 403, f"un utilisateur non-admin a lu l'audit : {rep.status_code}"


def test_a_torn_trace_line_does_not_break_the_audit(monkeypatch, traces_dir):
    """CONTRE-ÉPREUVE de robustesse : une ligne tronquée est signalée, pas cachée.

    Un fichier JSONL s'arrête sur une ligne incomplète dès qu'un process meurt en
    plein `f.write` — c'est le cas nominal, pas une corruption exceptionnelle. La route
    doit donc répondre 200 **et** dire qu'elle a sauté des lignes. Une route qui
    ignorerait le défaut en silence afficherait un audit plus propre que la vérité.
    """
    traces_dir.mkdir(parents=True, exist_ok=True)
    fichier = traces_dir / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"
    fichier.write_text('{"kind": "decision", "decision": "kee')
    monkeypatch.setenv("AUTH_ENABLED", "false")

    rep = _client(auth="admin").get("/api/audit/traces")

    assert rep.status_code == 200, f"une ligne tronquee a casse la route : {rep.text}"
    corps = rep.json()
    assert corps["malformed"] == 1, f"la ligne illisible n'est pas comptabilisee : {corps}"


def test_the_audit_trail_is_bounded(monkeypatch, traces_dir):
    """CONTRE-ÉPREUVE de ressources : la lecture est bornée, même sur demande.

    Le fichier fait 356 Ko aujourd'hui et grossit à chaque outil exécuté. Une route
    d'audit sans plafond est une voie d'épuisement mémoire, et la borne doit être
    appliquée **côté serveur** : faire confiance à l'appelant n'est pas une borne.

    On écrit donc plus de `MAX_READ_LIMIT` enregistrements — sinon une borne absente
    passerait le test, ce qui est arrivé à la première version de ce test : 40 lignes
    demandées en 10 000 ne dépassent aucun plafond et ne prouvent rien.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    plafond = trace_writer.MAX_READ_LIMIT
    for i in range(plafond + 100):
        trace_writer.write_trace(
            tool=f"outil{i}",
            risk_level="exec",
            args_summary="{}",
            permission_decision="auto_approved",
            outcome="success",
        )

    rep = _client(auth="admin").get("/api/audit/traces", params={"limit": 10_000})

    assert rep.status_code == 200
    corps = rep.json()
    assert len(corps["traces"]) == plafond, (
        f"la borne serveur n'est pas appliquee : {len(corps['traces'])} lignes rendues "
        f"pour un plafond de {plafond}"
    )


def test_the_route_cannot_be_used_to_read_a_file_it_should_not(monkeypatch, tmp_path):
    """CONTRE-ÉPREUVE de cloisonnement : `day` ne permet pas de sortir du dossier.

    `day` devient un nom de fichier. S'il n'est pas validé, `../../secrets` suffit à lire
    n'importe quoi de lisible par le serveur. Le refus est vérifié **par la route**, et le
    lecteur revalide de son côté : l'invariant est posé là où le chemin est construit, pas
    seulement là où la route se rappelle de le poser.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    cible = tmp_path / "ailleurs"
    cible.mkdir()
    (cible / "secret.jsonl").write_text('{"kind": "tool", "tool": "bash"}')

    for jour in ("../../ailleurs/secret", "..%2F..%2Failleurs%2Fsecret", "/etc/passwd", "2026-9-1"):
        rep = _client(auth="admin").get("/api/audit/traces", params={"day": jour})
        assert rep.status_code == 200, f"{jour} a fait echouer la route au lieu d'etre refuse : {rep.text}"
        corps = rep.json()
        assert corps["ok"] is False, f"{jour} a ete accepte : {corps}"
        assert corps["traces"] == [], f"{jour} a retourne des traces : {corps}"


def test_a_day_without_traces_is_an_empty_answer_not_an_error(monkeypatch):
    """CONTRE-ÉPREUVE de sémantique : « rien d'audité ce jour-là » est une réponse.

    Un 404 ferait croire à un incident. Un jour sans trace est le cas normal d'un serveur
    démarré depuis peu, et l'audit doit pouvoir le dire calmement.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    rep = _client(auth="admin").get("/api/audit/traces", params={"day": "1999-01-01"})

    assert rep.status_code == 200, rep.text
    corps = rep.json()
    assert corps["ok"] is True, f"un jour sans trace est traite comme une erreur : {corps}"
    assert corps["traces"] == [] and corps["count"] == 0


def test_the_reader_itself_refuses_a_day_that_is_not_a_date(monkeypatch):
    """CONTRE-ÉPREUVE de défense en profondeur, sur l'API PUBLIQUE du lecteur.

    Ce test appelle `read_traces` directement, et c'est délibéré : la preuve de fin passe
    bien par HTTP, mais l'invariant « un jour est une date, rien d'autre » appartient à la
    fonction qui **construit le chemin**. Le mesurer par la route ne prouve rien de la
    validation du lecteur — la route valide avant de l'appeler, donc une suppression de la
    validation du lecteur passerait tous les autres tests. C'est mesuré : la mutation «
    plus aucune validation dans `read_traces` » laisse 10 tests verts sans ce test.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    for jour in ("../../ailleurs/secret", "/etc/passwd", "2026-9-1", "hier", ""):
        with pytest.raises(ValueError):
            trace_writer.read_traces(day=jour)


def test_a_protected_turn_is_audited_without_its_reasons(monkeypatch, traces_dir):
    """CONTRE-ÉPREUVE P17 : un tour PROTECTED n'écrit pas sa demande sur le disque.

    C'est l'audit croisé qu'exige chaque nouvelle écriture durable. Une seule question à
    poser : la classification précède-t-elle l'écriture ? Au départ, non — le bloc M6.5
    tournait **après** AUTOEVAL, donc la trace partait avant que le contenu soit jugé. Or
    les `verifier_reasons` sont du texte dérivé de la demande : le vérificateur peut en
    citer un fragment. C'est la forme exacte du défaut que P17 sanctionne — un « rien n'a
    été persisté » imprimé à côté d'un fichier qui contient la charge utile.

    Le classifieur n'est **pas** simulé : la demande contient « santé », qui est dans les
    motifs PROTECTED de `data_classification.py:83`. La politique réelle est donc
    exercée, pas une version d'elle. Le test vérifie deux choses : la trace dit que les
    motifs ont été retenus, et le texte de la demande n'est nulle part sur le disque.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    # « santé » accentué : le motif PROTECTED est `r"santé"`, et le classifieur ne
    # normalise pas les accents. « sante » passe largement sous le motif — c'est
    # mesuré, pas supposé.
    demande = "resume-moi mon dossier de santé et mes analyses"

    async def _faux(_candidates, messages, **kw):
        yield "data: " + json.dumps({"delta": "Voici la marche a suivre, detaillee et complete."}) + "\n\n"
        yield "data: [DONE]\n\n"

    _un_run(monkeypatch, session="sess-protege", drift="high", faux_modele=_faux, demande=demande)

    fichiers = sorted(traces_dir.glob("*.jsonl"))
    assert fichiers, "aucune trace : la protection a trop coupé, ou rien n'a ete ecrit"
    brut = fichiers[-1].read_text()
    decisions = [json.loads(lgn) for lgn in brut.splitlines() if lgn.strip() and json.loads(lgn).get("kind") == "decision"]

    assert decisions, f"aucune décision écrite : {brut[:200]}"
    assert decisions[-1]["reasons_omitted"] == "protected", (
        f"la trace ne porte pas la règle appliquée : {decisions[-1]}. Un audit qui affiche "
        "« aucun motif » quand la protection a motifs ne dit pas la vérité."
    )
    assert decisions[-1]["decision"] == "revert", "la décision elle-même est de la métadonnée : elle doit s'écrire"
    assert "santé" not in brut, f"la demande protegee a atterri sur le disque : {brut[:300]}"


def test_an_ordinary_turn_is_audited_with_its_reasons(monkeypatch, traces_dir):
    """CONTRE-ÉPREUVE de non-régression : `reasons_omitted` reste absent normalement.

    Marquer `reasons_omitted` en permanence viderait l'audit de sa valeur : un champ
    toujours rempli n'apprend rien. Ce test verrouille que la marque n'apparaît que quand
    la classification l'a méritée.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    _un_run(monkeypatch, session="sess-ordinaire", drift="high")

    fichiers = sorted(traces_dir.glob("*.jsonl"))
    lignes = [json.loads(lgn) for lgn in fichiers[-1].read_text().splitlines() if lgn.strip()]
    decisions = [lgn for lgn in lignes if lgn.get("kind") == "decision"]

    assert decisions, "aucune décision écrite"
    assert decisions[-1]["reasons_omitted"] is None, (
        f"la protection a ete invoquee sur un tour ordinaire : {decisions[-1]}"
    )


def test_the_route_can_isolate_one_run(monkeypatch):
    """CONTRE-ÉPREUVE de jointure : deux runs ne se contaminent pas.

    C'est l'intérêt d'un `run_id` : rattacher une décision doit pouvoir se ramener au run
    correspondant, sinon la piste est inexploitable dès qu'il y a plus d'un tour.
    """
    monkeypatch.setenv("AUTH_ENABLED", "false")
    trace_writer.set_run_id("run-A")
    trace_writer.write_trace(
        tool="bash",
        risk_level="exec",
        args_summary="{}",
        permission_decision="auto_approved",
        outcome="success",
    )
    trace_writer.set_run_id("run-B")
    trace_writer.write_trace(
        tool="python",
        risk_level="exec",
        args_summary="{}",
        permission_decision="auto_approved",
        outcome="success",
    )

    corps = _client(auth="admin").get("/api/audit/traces", params={"run_id": "run-B"}).json()

    assert corps["traces"], "le filtre par run ne rend rien"
    assert {t["run_id"] for t in corps["traces"]} == {"run-B"}, (
        f"le filtre par run laisse passer les autres runs : {corps['traces']}"
    )
