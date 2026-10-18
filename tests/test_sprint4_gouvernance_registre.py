"""Item 2 du Sprint 4 — le registre doit dire ce qui est actif, donc il doit
couvrir tout ce qui peut l'être.

Le constat a mesuré 12 variables `ODYSSEUS_*` lues par le code de production et
absentes du registre. 11 d'entre elles sont des **interrupteurs de capacité** ; la
12ᵉ (`ODYSSEUS_DURABLE_EXEC`) n'avait plus de lecteur après l'item 1, donc plus
rien à enregistrer — l'inscrire aurait créé exactement le mensonge que le
registre existe pour éviter.

Reste le tri des 29 autres, qui sont de la **configuration** — chemins,
identifiants, délais. Elles n'ont pas leur place dans un registre
d'interrupteurs, et les y mettre noierait la seule distinction qui compte.

**La liste de configuration est explicite, dans ce fichier, avec une raison
chacune.** C'est le choix qui rend la porte tenable : une classification
déduite par expression régulière se déguise en-heuristique et se dégrade
silencieusement au premier nom nouveau. Ici, ajouter une variable au code
échoue tant que personne n'a décidé de ce qu'elle est. C'est plus pénible, et
c'est le but.

Ce test est le **noyau** que l'item 5 fera Monter en porte
(`tools/check_governance.py`). Tant qu'il vit dans `tests/`, il ne tourne que
par la suite ; l'item 5 lui donne une existence propre, avec un code de sortie.
"""

import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.killswitch_registry import read_states  # noqa: E402

LUS = re.compile(
    r"""(?:os\.environ(?:\.get)?\(\s*["']|os\.getenv\(\s*["']|environ\[\s*["'])([A-Z][A-Z0-9_]*)"""
)

# ── Le tri, explicite et motivé ───────────────────────────────────────────────
# Format : variable -> (categorie de configuration, raison du classement).
# « Configuration » signifie : ce n'est PAS un interrupteur de capacité. Un
# chemin, un identifiant, un délai, un secret. Rien à allumer ni à éteindre.
CONFIGURATION: dict[str, str] = {
    "ODYSSEUS_ADMIN_PASSWORD": "secret de demarrage, pas un reglage de capacite",
    "ODYSSEUS_ADMIN_USER": "identifiant de demarrage",
    "ODYSSEUS_ALLOW_OLLAMA_CLI_SCAN": "habilitation d'un scan CLI, pas un interrupteur de module",
    "ODYSSEUS_ALLOW_PRIVATE_CALDAV": "autorisation reseau, site par site",
    "ODYSSEUS_API_TOKEN": "secret d'authentification entre agents",
    "ODYSSEUS_COPILOT_API_VERSION": "version d'API tierce",
    "ODYSSEUS_COPILOT_CLIENT_ID": "identifiant OAuth",
    "ODYSSEUS_COPILOT_EDITOR_VERSION": "version d'editeur",
    "ODYSSEUS_COPILOT_INTEGRATION_ID": "identifiant d'integration",
    "ODYSSEUS_COPILOT_USER_AGENT": "en-tete de protocole",
    "ODYSSEUS_DATA_DIR": "racine de donnees, un chemin",
    "ODYSSEUS_DOCUMENT_OWNER": "proprietaire par defaut",
    "ODYSSEUS_ENV": "etiquette d'environnement",
    "ODYSSEUS_FALLBACK_OWNER": "proprietaire de repli",
    "ODYSSEUS_IMAP_TIMEOUT_SECONDS": "delai reseau",
    "ODYSSEUS_INPROCESS_POLLERS": "nombre de pollers, un parametre",
    "ODYSSEUS_INPROCESS_TASKS": "nombre de taches, un parametre",
    "ODYSSEUS_INTERNAL_BASE": "base d'URL interne",
    "ODYSSEUS_INTERNAL_TOKEN": "secret du canal interne",
    "ODYSSEUS_MAIL_ATTACHMENTS_DIR": "chemin de Piece jointe",
    "ODYSSEUS_MCP_ALLOWED_COMMANDS": "liste blanche de commandes, pas un interrupteur",
    "ODYSSEUS_MISTRAL_REASONING_EFFORT": "parametre de modele",
    "ODYSSEUS_OPA_URL": "adresse du serveur de politique",
    "ODYSSEUS_SINGLE_USER": "mode mono-utilisateur, une posture",
    "ODYSSEUS_SKIP_ADMIN_PROMPT": "comportement d'amorcage",
    "ODYSSEUS_SKIP_RUN_HINT": "comportement d'affichage",
    "ODYSSEUS_THOUGHT_BUS": "residu supprime a l'item 1 : aucun lecteur ne subsiste",
    "ODYSSEUS_URL": "adresse de service",
}

# Les 11 à inscrire à l'item 2. Volontairement nommés ici, et non déduits :
# un test doit dire ce qu'il exige, sinon il exige ce qu'il trouve.
ATTENDUS_AU_REGISTRE = {
    "ODYSSEUS_OPA": "politique de securite — lecteur reel, mais AUCUN importateur",
    "ODYSSEUS_OTEL": "telemetrie OpenTelemetry",
    "ODYSSEUS_APPRISE": "push externe multi-canal",
    "ODYSSEUS_MEILISEARCH": "recherche Meilisearch",
    "ODYSSEUS_PLANNING_ENGINE": "moteur de planification de projet",
    "ODYSSEUS_PREFECT": "ordonnanceur Prefect",
    "ODYSSEUS_QDRANT": "base vectorielle Qdrant",
    "ODYSSEUS_LETTA": "fournisseur de memoire Letta",
    "ODYSSEUS_MEM0": "fournisseur de memoire Mem0",
    "ODYSSEUS_MULTI_AGENT": "dispatch multi-agent (UC-10, gele) — visibilite seule",
    "ODYSSEUS_TOOL_DISCOVERY": "decouverte dynamique d'outils (INT-7), defaut off",
}


@pytest.fixture(scope="module")
def production() -> list[pathlib.Path]:
    return [
        p
        for p in REPO.rglob("*.py")
        if "venv" not in p.parts
        and "node_modules" not in p.parts
        and p.relative_to(REPO).parts[0] != "tests"
    ]


def _lues_par_la_production(production: list[pathlib.Path]) -> set[str]:
    lues: set[str] = set()
    for p in production:
        for m in LUS.finditer(p.read_text(encoding="utf-8", errors="replace")):
            if m.group(1).startswith("ODYSSEUS_"):
                lues.add(m.group(1))
    return lues


def test_aucune_capacite_lue_par_la_production_n_est_hors_registre(production):
    """PREUVE : tout `ODYSSEUS_*` lu est soit au registre, soit classé.

    C'est la porte de l'item. Le message nomme les deux listes fautives et ce
    qu'il faut en faire, parce qu'un test qui dit « ça ne va pas » sans dire
    quoi est un test qu'on corrige au hasard.
    """
    au_registre = {s["env_var"] for s in read_states()}
    lues = _lues_par_la_production(production)

    non_classees = sorted(v for v in lues if v not in au_registre and v not in CONFIGURATION)
    if non_classees:
        pytest.fail(
            f"{len(non_classees)} variable(s) lue(s) par la production ne sont ni au registre "
            f"ni classees comme configuration : {non_classees}\n"
            "  Si c'est une capacite — un module qu'on peut allumer ou eteindre — elle "
            "appartient au registre : sans lui, le tableau ne repond plus a sa question.\n"
            "  Si c'est un chemin, un identifiant, un delai ou un secret, ajoute-la a "
            "CONFIGURATION dans ce fichier, avec la raison. Le tri se fait a la main et "
            "se relit ; il ne se deduit pas, parce qu'une deduction qui se degrade en "
            "silence est pire que pas de porte."
        )

    # Et l'inverse : une entree de CONFIGURATION que plus rien ne lit est un
    # residu. Le dire evite d'accumuler des justifications mortes.
    orphelines = sorted(v for v in CONFIGURATION if v not in lues and v != "ODYSSEUS_THOUGHT_BUS")
    assert not orphelines, (
        f"{len(orphelines)} variable(s) sont classees comme configuration mais plus rien ne les lit : "
        f"{orphelines}. Supprime-les de CONFIGURATION, sinon la liste se remplit de justifications "
        "mortes et cesse d'etre un tri."
    )


def test_les_onze_capacites_attendues_sont_effectivement_au_registre():
    """CONTRE-ÉPREUVE de contenu : le test précédent passe aussi sur un registre vide.

    Sans cette seconde assertion, un registre vidé passerait le premier test par
    accident — les variables seraient alors « hors registre » mais aussi « non
    classées », donc le test échouerait. Il reste qu'un test qui vérifie la
    couverture doit vérifier ce qu'il exige nommément, pas seulement ce qu'il
    découvre.
    """
    au_registre = {s["env_var"]: s for s in read_states()}
    manquants = sorted(v for v in ATTENDUS_AU_REGISTRE if v not in au_registre)
    assert not manquants, (
        f"{len(manquants)} capacite(s) attendue(s) au registre en sont absentes : "
        f"{[(v, ATTENDUS_AU_REGISTRE[v]) for v in manquants]}"
    )


def test_opa_est_coupe_par_defaut_sans_mentir_sur_son_cable(production):
    """CONTRE-ÉPREUVE de la decision OPA : couper, sans encoder un faux.

    Le v8 tranche « couper par defaut ». Il proposait aussi `wired=False`, ce qui
    serait **faux** : `wired` signifie « un lecteur existe », et
    `opa_client.py:23` en est un. Ecrire `wired=False` afficherait « ce switch
    n'est pas reel » alors que la lecture est reelle et que c'est l'INTEGRATION
    qui manque — un mensonge dans l'autre sens, ce qui n'est pas mieux.

    Ce test verrouille les deux moities séparément : coupe par defaut, et
    `wired` exact. L'absence d'importateur est un troisieme fait, qui doit
    apparaitre dans la description — c'est ce que verifie le test suivant.
    """
    opa = {s["env_var"]: s for s in read_states()}["ODYSSEUS_OPA"]

    assert str(opa["default"]).lower() in {"off", "0", "false", "no"}, (
        f"ODYSSEUS_OPA est a {opa['default']!r} : l'operateur qui lit le tableau doit voir "
        "qu'aucune politique n'est appliquee. Un moteur de politique qu'on croit actif et "
        "qui ne l'est pas est la forme exacte du defaut que ce registre existe pour interdire."
    )
    assert opa["wired"] is True, (
        "ODYSSEUS_OPA a bien un lecteur (opa_client.py). `wired=False` affirmerait le "
        "contraire, et le champ ne dit pas cela. Ce qui manque n'est pas le lecteur, "
        "c'est l'import du module : deux faits, deux champs ou deux phrases."
    )


def test_opa_est_coupe_dans_le_code_pas_seulement_dans_le_tableau(production):
    """CONTRE-ÉPREUVE du piege que j'ai committed : le defaut vit dans le CODE.

    J'ai d'abord pose `default=off` au registre et conclu que la decision v8
    etait executee. Elle ne l'etait pas : `opa_client.py` lisait toujours
    `os.getenv("ODYSSEUS_OPA", "on")`, donc le moteur restait actif et le
    tableau affichait le contraire. C'est exactement « un registre qui ne ment
    pas » qui etait viole — par moi, en croyant l'executer.

    C'est `tests/test_killswitch_registry.py` qui l'a rattrape, et non mon test :
    il compare le defaut declare a celui que le **lecteur reel** applique. Ce
    test-ci verifie donc le code, parce que l'ordre de verite commence par lui.

    Sans cette assertion, le test precedent suffit et le defaut peut retroler
    dans le code sans que rien ne parle — le tableau resterait vert.
    """
    lecteur = (REPO / "services/security/opa_client.py").read_text(encoding="utf-8")
    m = re.search(r"""os\.getenv\(\s*["']ODYSSEUS_OPA["']\s*,\s*["']([^"']*)["']""", lecteur)
    assert m is not None, (
        "la lecture d'ODYSSEUS_OPA n'est plus litterale : le verificateur de "
        "tests/test_killswitch_registry.py ne pourra plus la voir, et le tableau "
        "recommencera a diverger du code sans qu'on le voie."
    )
    assert m.group(1).lower() in {"off", "0", "false", "no"}, (
        f"le CODE lit `os.getenv(\"ODYSSEUS_OPA\", {m.group(1)!r})` : le moteur est encore actif "
        "par defaut. Le registre peut afficher `off` tant qu'il veut — c'est ce qui est arrive "
        "avant ce test. Couper se fait dans le code, l'affichage ne suit que."
    )

    # Et les deux moities disent la meme chose, sinon le tableau ment encore.
    declare = {s["env_var"]: s for s in read_states()}["ODYSSEUS_OPA"]["default"]
    assert str(declare).lower() == m.group(1).lower(), (
        f"le registre dit {declare!r} et le code applique {m.group(1)!r} : l'operateur lit une "
        "chose, le systeme en fait une autre."
    )


def test_le_verificateur_du_registre_voit_les_lectures_sans_defaut_litteral(production):
    """CONTRE-ÉPREUVE du verificateur : son angle mort est-il refermé ?

    `os.getenv("ODYSSEUS_X")` sans defaut litteral etait invisible au
    verificateur du registre. Six variables en profitaient, dont une portee
    `wired=False` a tort — le drapeau avait donc pourri sans bruit. Ce test
    echoue si une lecture sans defaut litteral redevient invisible.
    """
    src = (REPO / "tests/test_killswitch_registry.py").read_text(encoding="utf-8")
    assert "_READER_SANS_DEFAUT_RE" in src, (
        "le verificateur du registre ne reconnait plus les lectures sans defaut litteral : "
        "six variables redeviennent invisibles, dont ODYSSEUS_ZEN_FROM_ENDPOINT dont le "
        "`wired=False` etait faux. Le defaut doit etre capture comme vide, ce que "
        "`_normalise` lit deja comme « eteint »."
    )

    # Et l'angle mort est reellement referme : la detection trouve une lecture nue.
    sans_defaut = re.compile(r"""(?:os\.environ\.get|os\.getenv)\(\s*["'](ODYSSEUS_[A-Z0-9_]+)["']\s*\)""")
    trouvees = set()
    for p in production:
        for m in sans_defaut.finditer(p.read_text(encoding="utf-8", errors="replace")):
            trouvees.add(m.group(1))
    assert trouvees, "plus aucune lecture sans defaut litteral dans le code : revoquer ce test, il n'a plus d'objet"
    assert "ODYSSEUS_ZEN_FROM_ENDPOINT" in trouvees or not any(
        s["env_var"] == "ODYSSEUS_ZEN_FROM_ENDPOINT" for s in read_states()
    ), "incoherence inattendue sur ZEN_FROM_ENDPOINT"


def test_la_description_d_opa_dit_qu_aucun_module_ne_l_importe(production):
    """CONTRE-ÉPREUVE de transparence : le fait doit etre lisible, pas deviné.

    Un registre qui affiche `ODYSSEUS_OPA=off` sans dire pourquoi ne permet pas
    de distinguer « coupe volontairement » de « mort et oublie ». La raison est
    donc dans le texte, et ce test la vérifie.
    """
    opa = {s["env_var"]: s for s in read_states()}["ODYSSEUS_OPA"]
    desc = (opa.get("desc") or "").lower()
    assert "aucun" in desc and "import" in desc, (
        f"la description d'ODYSSEUS_OPA ne dit pas que le module n'est importe par aucun "
        f"autre : {opa.get('desc')!r}. C'est l'information qui distingue un interrupteur "
        "coupe d'un interrupteur mort."
    )
    # Le second moiety : savoir que l'absence d'importateur est un fait, ET que la
    # coupure est un choix. Sans le second, le lecteur ne peut pas distinguer une
    # extinction réfléchie d'un oubli — les deux affichent `off`.
    assert "decision" in desc or "décision" in desc, (
        f"la description d'ODYSSEUS_OPA ne dit pas que la coupure est une decision : "
        f"{opa.get('desc')!r}. Un `off` sans cause lue se confond avec un `off` par oubli."
    )

    # Et l'absence d'importateur est verifiee, pas seulement affirmee.
    opa_mod = "services.security.opa_client"
    importateurs = [
        str(p.relative_to(REPO))
        for p in production
        if re.search(rf"(?:^|\n)\s*from\s+{re.escape(opa_mod)}\b|(?:^|\n)\s*import\s+{re.escape(opa_mod)}\b", p.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not importateurs, (
        f"la description d'ODYSSEUS_OPA affirme qu'aucun module ne l'importe, mais "
        f"{importateurs} l'importe(nt). Le code a bouge : la description doit suivre."
    )


def test_aucune_variable_n_est_a_la_fois_registre_et_configuration(production):
    """CONTRE-ÉPREUVE de coherence du tri : pas de variable dans les deux listes.

    C'est la derive realiste : quelqu'un declare « ce n'est pas une capacite » et
    laisse l'entree au registre, ou l'inverse. Les deux listes sont alors vraies
    et fausse en meme temps, et le test de couverture passe — parce qu'il ne teste
    que l'absence d'intersection avec le registre, pas l'absence de conflit.

    Ce controle a ete ajoute apres une mutation qui revelait exactement ce trou :
    vider la liste des attendus ne casse rien, parce qu'une liste vide n'exige
    rien. Une porte qui ne peut pas etre affaiblie sans qu'on le voie n'est pas
    une porte.
    """
    au_registre = {s["env_var"] for s in read_states()}
    dans_les_deux = sorted(set(CONFIGURATION) & au_registre)
    assert not dans_les_deux, (
        f"{len(dans_les_deux)} variable(s) sont au registre ET classees comme configuration : "
        f"{dans_les_deux}. Une variable ne peut pas etre une capacite et un chemin en meme "
        "temps. Tranchez, puis supprimez-la d'une des deux listes."
    )


def test_multi_agent_est_visible_sans_changer_de_defaut(production):
    """CONTRE-ÉPREUVE de périmètre : rendre visible n'est pas activer.

    UC-10 est une escalade gelée. Inscrire son interrupteur au registre pour que
    l'opérateur le voie est de la gouvernance ; changer son défaut serait une
    activation. Ce test verrouille la frontière.
    """
    registre = {s["env_var"]: s for s in read_states()}
    multi = registre.get("ODYSSEUS_MULTI_AGENT")
    assert multi is not None, (
        "ODYSSEUS_MULTI_AGENT n'est pas au registre. Il est lu par la boucle : l'operateur "
        "ne peut donc pas savoir si le multi-agent est actif. C'est ce que l'inscription corrige."
    )
    assert str(multi["default"]).lower() in {"off", "0", "false", "no"}, (
        f"ODYSSEUS_MULTI_AGENT est a {multi['default']!r}. UC-10 est une escalade gelee : "
        "l'inscrire ne doit pas l'activer. Si ce test echoue, quelqu'un a franchi la "
        "frontiere — et il faut le savoir."
    )
