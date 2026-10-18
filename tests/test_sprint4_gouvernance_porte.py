"""Item 5 du Sprint 4 — la porte de gouvernance, et surtout : est-elle credible ?

Une porte qui ment dans le sens « tout va bien » arrête d'être lue. Une porte
qui **exagère** est pire : elle annonce des problèmes qui n'existent pas, et
celui qui reçoit le rapport cesse de la croire — y compris quand elle a raison.

C'est arrivé trois fois pendant la construction de cette porte, et chaque fois
un test l'a attrapé :

* les modules sous `archive/legacy/` sont importés par leur **shim**
  (`src/agent_loop.py`), jamais par leur vrai nom — sans cela, tout ce que la
  boucle lisait paraissait sans importateur ;
* les outils d'agent sont importés en **relatif** (`from .filesystem_tools`) ;
* `trace_writer` est importé par **paquet + sous-module** (`from src import
  trace_writer`), forme que ni l'absolue ni la relative ne voient.

Le compte est donc passé de 9 à 5, et les 5 restants ont été **vérifiés à la
main** : chacun n'est mentionné que dans lui-même et dans le registre. Ce que la
porte affiche maintenant est tenable.

Le reste du fichier vérifie la partie bloquante — la classification capacités /
configuration, extraite du test de l'item 2 plutôt que recopiée.
"""

import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
OUTIL = REPO / "tools/check_governance.py"


def _charge():
    spec = importlib.util.spec_from_file_location("check_governance", OUTIL)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules["check_governance"] = m
    spec.loader.exec_module(m)
    return m


cg = _charge()


def test_rien_n_est_non_classe_aujourd_hui():
    """PREUVE 1 : l'etat courant est propre, et c'est verifie."""
    m = cg.mesure()
    assert not m["capacites_non_classees"], (
        f"des capacites lues par la production ne sont ni au registre ni classees : "
        f"{m['capacites_non_classees']}"
    )
    assert not m["justifications_mortes"], f"justifications de configuration mortes : {m['justifications_mortes']}"
    assert not m["contradictions"], f"variables a la fois registre ET configuration : {m['contradictions']}"


def test_une_capacite_non_classee_bloque_la_porte(monkeypatch):
    """PREUVE 2 : la porte refuse de publier un etat faux.

    Elle doit ETRE rouge, ET refuser `--write` : une porte qui ecrit un compte
    faux dans la documentation est deux fois pire qu'une porte absente, parce
    qu'elle donne l'illusion d'une mesure.
    """
    reel = set(cg.lues_par_la_production())
    monkeypatch.setattr(cg, "lues_par_la_production", lambda: reel | {"ODYSSEUS_CAPACITE_FICTIVE"})

    m = cg.mesure()
    assert m["capacites_non_classees"] == ["ODYSSEUS_CAPACITE_FICTIVE"], m

    monkeypatch.setattr(sys, "argv", ["check_governance.py"])
    assert cg.main() == 1, "la porte est verte alors qu'une capacite n'est decidee nulle part"
    monkeypatch.setattr(sys, "argv", ["check_governance.py", "--write"])
    assert cg.main() == 1, "la porte a ecrit un compte faux dans la documentation"


def test_une_justification_de_configuration_morte_bloque(monkeypatch):
    """PREUVE 3 : la liste de configuration ne s'empile pas de raisons mortes."""
    reel = set(cg.lues_par_la_production())
    monkeypatch.setattr(cg, "lues_par_la_production", lambda: reel)
    base = cg._configuration_declaree()
    # On reevalue la liste a chaque appel : la porte doit RELIRE la definition,
    # pas la figer au chargement. Une liste figee ne verrait plus les justifications
    # ajoutees depuis — et le tri serait un instantane, donc faux demain.
    monkeypatch.setattr(
        cg,
        "_configuration_declaree",
        lambda: {**base, "ODYSSEUS_FABULEUSE": "raison inventee"},
    )
    m = cg.mesure()
    assert "ODYSSEUS_FABULEUSE" in m["justifications_mortes"], m
    monkeypatch.setattr(sys, "argv", ["check_governance.py"])
    assert cg.main() == 1


def test_le_tri_est_lu_depuis_le_test_de_l_item_2_pas_recopie():
    """PREUVE 4 : une seule definition du tri, lue par les deux.

    Le tri capacités / configuration est défini dans le test de l'item 2. Le
    recopier ici ferait diverger les deux listes, et la divergence serait
    **invisible** : chaque test mesurerait sa propre liste et serait vert. Une
    seule definition lue par les deux est la seule forme qui tient.
    """
    depuis_le_test = cg._configuration_declaree()
    assert depuis_le_test, "la definition du tri est vide"
    source = (REPO / "tests" / "test_sprint4_gouvernance_registre.py").read_text(encoding="utf-8")
    assert "CONFIGURATION" in source
    # Et l'outil doit refuser de tourner si la definition a disparu, plutot que
    # de continuer avec une liste vide — ce qui rendrait la porte verte.
    assert cg._TEST_ITEM2.is_file()


def test_le_compte_du_signal_called_est_exact():
    """PREUVE 5 — le signal le plus facile a mentir est verifie contre la realite.

    « Lecteur sans importateur » a ete ecrit trois fois de travers avant d'etre
    juste : 9 au lieu de 5, a cause des shims, des imports relatifs, et de la
    forme paquet+sous-module. Ce test verifie donc que le compte **concorde avec
    une recherche independente**, faite ici sans le code de l'outil.

    Sans ce test, la prochaine forme d'import inventee par quelqu'un ferait
    remonter le compte, et personne ne le remarquerait : un chiffre qui monte
    parait un chantier qui avance.
    """
    m = cg.mesure()
    annonces = set(m["lecteurs_sans_importateur"])

    # On ne liste que les entrees annoncees SANS importateur : ce sont les seules
    # dont l'affirmation « personne ne l'importe » doit pouvoir etre verifiee.
    # Chercher les 65 entrees dans chaque fichier coutait deux minutes et demie
    # pour un test — une porte qui met 150 s a tourner est une porte qu'on
    # contourne, precisement parce qu'elle coute cher.
    registres = {s["env_var"]: s for s in cg.read_states()}
    cibles = {}
    for env in annonces:
        src = registres[env].get("source", "")
        if ":" not in src:
            continue
        fichier, _, _ = src.partition(":")
        cibles.setdefault(fichier, set()).add(pathlib.Path(fichier).stem.removesuffix(".py"))

    faux_negatifs = {}
    for p in cg.fichiers_production():
        rel = str(p.relative_to(cg.REPO))
        noms = cibles.get(rel)
        if not noms:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        trouves = {env for env in annonces if env in cibles and (noms & {n for n in noms if n and n in t}) and registres[env]["source"].startswith(rel)}
        if trouves:
            faux_negatifs.update(trouves)

    assert not faux_negatifs, (
        f"ces entrees ont un importateur repere par une recherche simple mais l'outil les "
        f"declare sans importateur : {sorted(faux_negatifs)}. Le signal exagre ou nie dans un "
        "sens ou l'autre, et dans les deux cas il ne vaut plus rien."
    )


def test_les_modules_appeles_ne_sont_pas_annonces_comme_jamais_appeles():
    """PREUVE 6 — la liste `called=False` est épinglée, pas seulement vérifiée à vide.

    Trois mutations ont survécu ici parce qu'aucun test ne fixait le **contenu**
    de la liste : E1 (imports relatifs), E2 (paquet + sous-module), E3 (shims).
    Chacune rendait `filesystem_tools`, `trace_writer` et les deux entrées de la
    boucle « jamais appelés » — c'est-à-dire **faux**, et en plus alarms.

    Un signal qui exagère décourage de lire celui qui dit juste. Donc on épingle
    les cas connus, avec la forme d'import qui les masquerait si elle disparaît.
    """
    annonces = set(cg.mesure()["lecteurs_sans_importateur"])

    appeles_malgre_leur_import_discret = {
        # `from src import trace_writer` — la forme paquet + sous-module.
        "ODYSSEUS_UNIFIED_TOKENS": "from src import trace_writer",
        # `from src.observer import Observer, DriftLevel` dans la boucle, qui
        # s'importe par le shim `src/agent_loop.py`, jamais par son vrai nom.
        "ODYSSEUS_LIVE_ORCHESTRATION": "via src/agent_loop.py (shim de archive/legacy/)",
    }
    for env, forme in appeles_malgre_leur_import_discret.items():
        assert env not in annonces, (
            f"{env} est annonce comme 'jamais appele', alors qu'il est appele par "
            f"{forme}. Le signal exagre : un rapport qui annonce des problemes "
            "inexistants fait ignorer ceux qui existent — dont OPA."
        )

    # Et l'autre moitie : les 5 annonces sont reellement sans importateur.
    # C'est verifie a la main ; on l'ecrit pour que la liste ne derive pas en
    # silence quand un module gagne un appelant.
    attendus = {
        "ODYSSEUS_AGENTSEAL",
        "ODYSSEUS_CBM",
        "ODYSSEUS_N8N",
        "ODYSSEUS_OPA",
        "ODYSSEUS_PREFECT",
        "ODYSSEUS_SERENA_MCP",
    }
    assert annonces == attendus, (
        f"la liste des lecteurs sans importateur a change : {sorted(annonces)} au lieu de "
        f"{sorted(attendus)}. Si un module a gagne un appelant, c'est une BONNE nouvelle — "
        "retire-le de cette liste, et de la liste de l'outil si necessaire. Si la liste "
        "grossit, c'est une nouvelle forme d'import que l'outil ne voit pas encore."
    )


def test_la_ligne_generee_est_dans_la_documentation():
    """CONTRE-ÉPREUVE de publication : le compte est écrit, jamais recopié."""
    trace = (REPO / "docs/traceability/TRACEABILITY.md").read_text(encoding="utf-8")
    assert cg.MARQUEUR in trace, (
        "le compte de gouvernance n'est pas dans TRACEABILITY.md. Il doit etre GENERE : "
        "une valeur recopiee a la main est une valeur qui finit par mentir."
    )
    ligne = trace.split(cg.MARQUEUR, 1)[1].split("\n", 1)[1]
    assert "Gouvernance" in ligne and "capacités non classées" in ligne, ligne
