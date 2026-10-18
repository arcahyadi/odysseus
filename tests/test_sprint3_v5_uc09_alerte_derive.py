"""Sprint 3 v5 — item 12 (UC-09) — une alerte doit avoir un canal.

La fiche UC-09 disait : une dérive `HIGH` n'est qu'un `logger.warning`, et
« **aucune alerte** ». C'est exact, et la mesure précise pourquoi c'est grave :
le `logger.warning` part dans un fichier que personne ne lit pendant un tour, alors
que l'événement `run_status` porte déjà le niveau de drift — donc la donnée
atteint bien le client, mais **comme un statut parmi d'autres**. Rien ne dit
« ceci mérite qu'on s'en occupe ».

Une alerte a trois propriétés qu'un statut n'a pas : elle doit être
**indiscutable** (pas une ligne dans un flux qu'on peut manquer), elle doit
**survivre à la déconnexion** (item 9 a mesuré que c'est le mode de défaillance
normal : un client qui part perd tout ce qui n'a été que diffusé), et elle doit
porter **la cause et le geste**, pas seulement un niveau.

Le canal retenu est donc la **piste d'audit** — la même que celle construite à
l'item 9, avec le même lecteur, la même route, la même garde `require_admin`. Un
deuxième système d'alerte aurait été une deuxième piste à maintenir et à garder
cohérente ; celui-ci existe déjà, il est testé, et il survit au client.

Et l'alerte part aussi sur le flux, en événement distinct de `run_status` : un
statut se lit, une alerte s'annonce.

D'où les preuves de ce fichier :

* **preuve de fin** — un tour à dérive `HIGH` produit une alerte relisible **par
  HTTP, après coup, par un administrateur** — donc exactement le scénario « le
  client s'est déconnecté » ;
* **contre-épreuve de la porte** — le même alerte n'est **pas** lisible par un
  non-administrateur, sinon l'audit n'est plus un audit ;
* **contre-épreuve de contenu** — l'alerte porte la **cause** et la
  **recommandation**, pas seulement un niveau ; une alerte qui dit « high » sans
  dire pourquoi oblige à refaire le calcul à la main ;
* **contre-épreuve de credibilite** — une derive `LOW` ne declenche **rien**. Une
  alerte qui hurle sur tout le monde n'est plus une alerte.

Le test entre par la **boucle de production** (`stream_agent_loop`) et par la
**route d'audit** relisant par HTTP. Le niveau de dérive est obtenu en patchant
`compute_drift_score` : c'est la couture d'**entrée** du calcul, donc le système
réel reste entier — le verdict, l'écriture, l'émission et la relecture.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.agent_loop as al
from routes.audit_routes import router
from src import constants, trace_writer
from src.observer import DriftLevel, Observer

# ─── Harnais ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def traces_dir(monkeypatch, tmp_path):
    """Redirige `DATA_DIR`, la source unique des fichiers persistés.

    On patche la constante et non le répertoire calculé : c'est ce qui prouve que
    la boucle et la route empruntent le **même** chemin. Patcher
    `trace_writer._traces_dir` validerait un chemin qu'aucun appelant réel n'utilise.
    """
    cible = tmp_path / "data"
    monkeypatch.setattr(constants, "DATA_DIR", str(cible), raising=False)
    return cible / "traces"


@pytest.fixture(autouse=True)
def drift_fixe(monkeypatch):
    """Fixe le niveau de dérive. LOW par défaut : chaque test annonce le sien."""
    niveau = {"valeur": DriftLevel.LOW}

    def _compute(self):
        return niveau["valeur"]

    monkeypatch.setattr(Observer, "compute_drift_score", _compute, raising=False)
    return niveau


def _un_tour(monkeypatch, session: str):
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setenv("ODYSSEUS_DATA_CLASSIFICATION", "on")
    monkeypatch.setenv("ODYSSEUS_CONTENT_SECURITY", "on")

    async def _faux(_candidates, messages, **kw):
        yield "data: " + json.dumps({"delta": "Une reponse ordinaire, sans derive particuliere."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _faux, raising=False)

    async def _run():
        agen = al.stream_agent_loop(
            "https://api.openai.com/v1",
            "gpt-test",
            [{"role": "user", "content": "bonjour"}],
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


def _client(auth: str) -> TestClient:
    """App minimale portant le routeur d'audit.

    `auth` vaut `admin`, `user` ou `none`. Le client se construit sur un
    `auth_manager` minimal et un middleware qui estampille `current_user` — c'est
    le contrat que `require_admin` attend. `is_admin` est un **appelable** qui
    reçoit l'identite, pas un drapeau : un stubbooleen passerait pour un
    administrateur systematiquement, et le contre-epreuve de porte serait verte
    pour la mauvaise raison.
    """
    app = FastAPI()

    if auth != "none":
        app.state.auth_manager = SimpleNamespace(
            is_configured=True,
            is_admin=lambda u: u == "admin",
        )
        identite = "admin" if auth == "admin" else "simple-utilisateur"

        @app.middleware("http")
        async def _etiquette(request, call_next):
            request.state.current_user = identite
            return await call_next(request)

    app.include_router(router)
    return TestClient(app)


def _sur_le_disque(**filtres) -> list[dict]:
    traces, _malformes = trace_writer.read_traces(**filtres)
    return traces


# ─── La preuve de fin ───────────────────────────────────────────────────────


def test_a_high_drift_is_readable_over_http_afterwards(monkeypatch, drift_fixe):
    """PREUVE DE FIN : l'alerte survit au client et se relit par HTTP.

    On lit l'alerte **après** le tour, par la route d'audit, en tant
    qu'administrateur. C'est le scénario que la fiche reproche au log : si
    personne ne regarde le flux au moment du tour, l'information doit rester
    rattrapable. Le `logger.warning` ne l'était pas.
    """
    drift_fixe["valeur"] = DriftLevel.HIGH

    evenements = _un_tour(monkeypatch, session="sess-drift-high")

    # 1) L'alerte est annoncée sur le flux, en événement distinct du statut.
    annonces = [e for e in evenements if e.get("type") == "drift_alert"]
    assert annonces, (
        f"aucune annonce d'alerte sur le flux. Evenements : "
        f"{sorted({e.get('type') for e in evenements if e.get('type')})} — le drift est "
        "pourtant HIGH, donc il n'est que dans run_status, c'est-a-dire perdu dans un statut."
    )
    assert annonces[0]["level"] == "high", f"niveau annonce faux : {annonces[0]}"

    # 2) Elle est relisible après coup, par la route, par un administrateur.
    rep = _client(auth="admin").get("/api/audit/traces", params={"kind": "alert"})
    assert rep.status_code == 200, rep.text
    corps = rep.json()
    alertes = [t for t in corps["traces"] if t.get("kind") == "alert"]
    assert alertes, (
        "l'alerte n'est pas relisible apres le tour : elle n'a survecu que le temps du flux. "
        "C'est exactement le defaut reproche au log,changer de canal."
    )
    derniere = alertes[-1]
    assert derniere["alert"] == "drift", f"l'alerte ne dit pas de quoi elle parle : {derniere}"
    assert derniere["level"] == "high"
    assert derniere.get("session_id") == "sess-drift-high", (
        f"l'alerte n'est pas rattachee a sa session : {derniere}"
    )


def test_the_alert_carries_the_cause_and_the_geste(monkeypatch, drift_fixe):
    """CONTRE-ÉPREUVE de contenu : « high » seul oblige à recalculer à la main.

    `Observer.get_summary()` calcule déjà la cause et la recommandation. Une alerte
    qui ne les transporte pas transmet un résultat et laisse le travail ; celle qui
    les transporte transmet une décision.
    """
    drift_fixe["valeur"] = DriftLevel.HIGH

    _un_tour(monkeypatch, session="sess-drift-cause")

    alertes = _sur_le_disque(kind="alert")
    assert alertes, "aucune alerte sur le disque"
    detail = alertes[-1].get("detail") or {}
    assert detail.get("harness_touched") is not None, (
        f"l'alerte ne dit pas ce qui l'a declenchee : {alertes[-1]}"
    )
    assert detail.get("recommendation"), (
        f"l'alerte ne dit pas quoi faire : {alertes[-1]}. "
        "Un niveau sans geste oblige celui qui reçoit l'alerte a refaire le calcul."
    )
    assert "drift_level" in detail, f"le resume de l'observateur n'est pas passe : {alertes[-1]}"


# ─── Contre-épreuves ────────────────────────────────────────────────────────


def test_a_non_admin_cannot_read_the_alert(monkeypatch, drift_fixe):
    """CONTRE-ÉPREUVE de porte : l'alerte n'est pas une fuite.

    Une alerte est une information sur l'état du système. La poser dans une piste
    lisible par tous ne serait pas une alerte, ce serait une fuite — et la piste
    d'audit existe justement pour n'être pas lisible par tous.
    """
    drift_fixe["valeur"] = DriftLevel.HIGH
    _un_tour(monkeypatch, session="sess-drift-porte")

    assert _sur_le_disque(kind="alert"), "le harnais n'a produit aucune alerte a tester"

    rep = _client(auth="user").get("/api/audit/traces", params={"kind": "alert"})
    assert rep.status_code == 403, f"un non-administrateur a lu l'audit : {rep.status_code} {rep.text}"


def test_a_low_drift_raises_nothing(monkeypatch, drift_fixe):
    """CONTRE-EPREUVE de credibilite : une alerte qui hurle n'est plus une alerte.

    Le cas nominal — une dérive `LOW` — ne doit produire ni annonce sur le flux ni
    enregistrement. Sans cette contre-épreuve, une implémentation qui alerte
    systématiquement passerait tous les autres tests.
    """
    drift_fixe["valeur"] = DriftLevel.LOW

    evenements = _un_tour(monkeypatch, session="sess-drift-low")

    assert not [e for e in evenements if e.get("type") == "drift_alert"], (
        "une derive LOW a declenche une alerte"
    )
    assert _sur_le_disque(kind="alert") == [], "une derive LOW a ete enregistree comme alerte"


def test_the_alert_table_matches_the_enumeration_it_mirrors():
    """CONTRE-ÉPREUVE de table : `_DRIFT_ALERTS` ne peut pas dériver en silence.

    La table est indexée par la **valeur** du niveau, pas par le membre de
    l'énumération — donc sans import au chargement. Le prix de ce choix est
    connu : une faute de frappe, ou une renomination de `DriftLevel.MEDIUM`,
    éteindrait l'alerte sans lever la moindre erreur. Ce test paie ce prix.

    Sans lui, la table pourrait ne plus rien avoir à voir avec l'énumération et
    les autres tests resteraient verts : ils patchent `compute_drift_score`, qui
    renvoie l'énumération, et un décalage passerait inaperçu.
    """
    table = al._DRIFT_ALERTS
    assert set(table) == {niveau.value for niveau in DriftLevel if niveau.name in {"MEDIUM", "HIGH"}}, (
        f"la table {table} ne correspond plus aux niveaux `MEDIUM`/`HIGH` de l'enumeration : "
        f"{ {n.name: n.value for n in DriftLevel} }"
    )
    assert "low" not in table, (
        "`LOW` est dans la table d'alerte : la table ne dit plus quels niveaux meritent "
        "une alerte, elle en ajoute un."
    )
    # Gravites croissantes, sans doublon : deux niveaux qui se confondent
    # produiraient une alerte incapable de distinguer deux gravites.
    valeurs = sorted(table.values())
    assert len(set(valeurs)) == len(valeurs), f"gravites non distinctes : {table}"
    assert valeurs == list(range(1, len(valeurs) + 1)), f"gravites non contigues depuis 1 : {table}"


def test_medium_drift_also_alerts_but_below_high(monkeypatch, drift_fixe):
    """CONTRE-ÉPREUVE de gradation : `MEDIUM` alerte aussi, mais pas au meme titre.

    L'enumeration le dit elle-meme — `MEDIUM` est documente « Derive significative —
    alerte », `HIGH` « re-loop ou escalade ». N'alerter que sur `HIGH` laisserait la
    gradation inexprimée : l'alerte ne distingue alors plus deux gravites
    reellement différentes.
    """
    drift_fixe["valeur"] = DriftLevel.MEDIUM

    evenements = _un_tour(monkeypatch, session="sess-drift-medium")

    annonces = [e for e in evenements if e.get("type") == "drift_alert"]
    assert annonces, "une derive MEDIUM, documentee comme alerte, n'a rien declenche"
    medium = annonces[0]
    assert medium["level"] == "medium", f"niveau annonce faux : {medium}"

    # La gradation se mesure en comparant les deux gravites. Un seul niveau ne
    # prouverait qu'une valeur arbitraire.
    drift_fixe["valeur"] = DriftLevel.HIGH
    _un_tour(monkeypatch, session="sess-drift-comparaison")
    haut = [e for e in _sur_le_disque(kind="alert") if e.get("level") == "high"]
    assert haut, "aucune alerte HIGH a comparer"

    assert medium["severity"] < haut[-1]["severity"], (
        f"MEDIUM et HIGH ont la meme gravite ({medium['severity']}) : l'alerte ne distingue "
        "plus deux gravites reellement differentes."
    )
