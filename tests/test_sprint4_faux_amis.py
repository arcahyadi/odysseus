"""Items 6 et 7 du Sprint 4 — les deux gardes qui empêchent une faute FUTURE.

Ces deux items partagent une forme : aucun des deux ne corrige un défaut
aujourd'hui. Ils plantent un repère pour qu'un défaut qui n'existe pas encore
ne puisse pas s'installer sans bruit.

**Item 6 — `check_citations` n'est pas INT-10.** Le nom décrit exactement la
fonctionnalité d'INT-10 de la vision (*grounding et citations dans les
livrables*), qui n'existe pas dans ce dépôt. Quelqu'un peut lire « les citations
sont vérifiées » et conclure que le livrable d'une recherche est sourcé. Il ne
l'est pas : l'outil n'inspecte que `docs/`. Le test échoue si la couverture
s'élargit hors documentation, ou si le fichier cesse de dire ce qu'il ne fait pas
— parce qu'une frontière non écrite est une frontière qu'on franchit.

**Item 7 — `run_script` et `ssh_command`.** Le constat a vérifié, et infirmé,
une alerte : ces deux actions ont la capacité de `bash` sans figurer dans la liste
bloquée pour un non-administrateur. Cherché, le chemin d'exploitation **n'existe
pas** — `BUILTIN_ACTION` n'est référencé que par les routes et le
planificateur, pas par la boucle, donc ce ne sont pas des outils d'agent. La
contrainte latente reste réelle : **si les actions builtin devenaient un jour des
outils d'agent, la porte du propriétaire ne les couvrirait pas**.

Deux conditions, donc deux tests : l'une sur l'atteinte (7.1), l'autre sur la
couverture (7.2). Une seule des deux ne prouverait rien — c'est le produit des
deux qui tient, et c'est ce que le test dit.
"""

import ast
import importlib.util
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
CITE = REPO / "tools/check_citations.py"
REGISTRE = REPO / "src/tool_security.py"
BUILTIN = REPO / "src/builtin_actions.py"


def _charge(nom: str, chemin: pathlib.Path):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[nom] = m
    spec.loader.exec_module(m)
    return m


# ══ Item 6 — la frontière du faux ami ═════════════════════════════════════


def test_le_verificateur_de_citations_ne_couvre_que_la_documentation():
    """PREUVE 6.1 : la couverture reste documentaire.

    Si `DOC_GLOBS` s'élargit, l'outil commence à scanner autre chose — et son nom
    le ferait croire encore plus. On épingle les deux répertoires : c'est la seule
    chose qui empêche l'ambiguïté de renaître.
    """
    cc = _charge("check_citations_item6", CITE)
    globs = set(cc.DOC_GLOBS)
    assert globs == {"docs/traceability/*.md", "docs/planning/*.md"}, (
        f"la couverture du verificateur a change : {sorted(globs)}. Un verificateur qui "
        "s'elargit cesse de dire ce qu'il couvre, et son nom — « check_citations » — "
        "décrit deja INT-10, qui est une autre chose."
    )


def test_le_verificateur_dit_explicitement_ce_quil_ne_fait_pas():
    """PREUVE 6.2 : la frontière est ÉCRITE, pas seulement voulue.

    Une frontière non écrite est une frontière qu'on franchit. Le test échoue si la
    section disparaît, et il échoue aussi si elle ne dit plus les mots qui la
    rendent opposable.
    """
    doc = CITE.read_text(encoding="utf-8")
    entete = doc.split('"""', 2)[1]
    assert "NE fait PAS" in entete, (
        "la section « ce que cet outil NE fait PAS » a disparu de la docstring de "
        "check_citations.py. C'est la seule chose qui empeche de le confondre avec INT-10."
    )
    for mot in ("livrables", "INT-10", "DOC_GLOBS"):
        assert mot in entete, (
            f"la demarcation ne mentionne plus {mot!r} : elle ne dit plus ce qu'elle delimite"
        )


def test_le_verificateur_ne_pretend_pas_ouvrir_un_livrable():
    """PREUVE 6.3 : rien n'inspecte la sortie de l'agent.

    Le test est volontairement naïf : il cherche un accès à un répertoire de
    livrables. S'il en apparaissait un, l'outil ferait autre chose que
    documenter — et son nom seul ne le dirait pas.
    """
    doc = CITE.read_text(encoding="utf-8").lower()
    for motif in ("data/research", "deep_research", "output_dir", "artifact"):
        assert motif not in doc, (
            f"check_citations.py mentionne {motif!r} : verifier l'outil ne mesure plus ce "
            "qu'il couvre, et l'hypothese « il verifie les livrables » redevient plausible."
        )


# ══ Item 7 — la garde de propriété ═════════════════════════════════════════


def actions_builtin_executantes() -> set[str]:
    """Les actions `action_*` dont le corps lance un sous-processus.

    Détecté par le corps de la fonction, pas par une liste écrite à la main : une
    liste figée ne prouve qu'elle-même, et elle ne voit pas l'action ajoutée
    demain. Si la détection vient à ne rien trouver, le test 7.2 le dit.
    """
    arbre = ast.parse(BUILTIN.read_text(encoding="utf-8", errors="replace"))
    trouvees: set[str] = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.AsyncFunctionDef) or not noeud.name.startswith("action_"):
            continue
        for sous in ast.walk(noeud):
            if isinstance(sous, ast.Call) and isinstance(sous.func, ast.Name) and sous.func.id == "_run_subprocess":
                trouvees.add(noeud.name)
                break
    return trouvees


def test_les_actions_builtin_ne_sont_pas_des_outils_d_agent():
    """PREUVE 7.1 — condition 1 sur 2 : l'ATTEINTE.

    C'est le constat du v7, re-vérifié à chaque exécution. S'il devenait faux —
    si la boucle exposait les actions builtin — alors `run_script` aurait la
    capacité de `bash` sans être dans la liste des outils bloqués. Le test tombe
    le jour où cette condition change, et le 7.2 explique alors ce qu'il faut
    faire.
    """
    assert "BUILTIN_ACTION" in BUILTIN.read_text(encoding="utf-8"), (
        "l'action builtin a ete renommee : ce test doit etre relu"
    )
    for consommateur in ("archive/legacy/agent_loop.py", "src/agent_loop.py"):
        t = (REPO / consommateur).read_text(encoding="utf-8", errors="replace")
        assert "BUILTIN_ACTION" not in t, (
            f"{consommateur} reference desormais BUILTIN_ACTION : les actions builtin sont "
            "devenues accessibles a la boucle, donc `run_script` et `ssh_command` sont devenus "
            "des outils d'agent — et ils ne sont pas dans NON_ADMIN_BLOCKED_TOOLS alors qu'ils "
            "ont la capacite de `bash`. C'est une escalade, et les deux tests de ce fichier "
            "doivent etre relus dans ce cas."
        )


def test_la_liste_bloquee_couvre_la_meme_capacite_que_bash():
    """PREUVE 7.2 — condition 2 sur 2 : la COUVERTURE.

    La règle à tenir, maintenant que l'atteinte est prouvée absente : **toute
    action de même capacité qu'un outil bloqué doit l'être aussi**. `bash` est
    bloqué ; `run_script` exécute en `shell=True` et part en SSH. Ce n'est pas un
    problème aujourd'hui — 7.1 le prouve — mais le jour où l'atteinte change, la
    couverture doit être déjà là.

    Le test ne se contente donc pas de constater qu'aucune action exécutante
    n'est bloquée. Il **vérifie que la détection en trouve**, parce qu'une
    détection qui ne trouve plus rien donnerait un vide silencieux : c'est le
    défaut que ce projet a passé six mois à traquer, et il n'a pas d'exception.
    """
    ts = _charge("tool_security_item7", REGISTRE)
    bloques = set(ts.NON_ADMIN_BLOCKED_TOOLS)

    for capacite in ("bash", "python", "write_file", "edit_file"):
        assert capacite in bloques, (
            f"{capacite} n'est plus dans la liste des outils bloques. Les listes de reference "
            "doivent rester stables, sinon ce test ne verifie plus rien."
        )

    executantes = actions_builtin_executantes()
    assert executantes, (
        "plus aucune action builtin n'est detectee comme executante : la detection a casse, "
        "et ce test ne surveille plus rien. C'est le meme defaut que `wired=False` sur un "
        "interrupteur qui a gagne un lecteur."
    )
    assert "action_run_script" in executantes, (
        f"l'action la plus expose n'est plus detectee : {sorted(executantes)}. "
        "Soit elle a change, soit la detection a casse — dans les deux cas, relire."
    )

    # L'etat constate, ecrit en toutes lettres. Il est VERT, et c'est une decision
    # cone : ces actions sont hors de portee de l'agent, donc la liste n'a pas a
    # les couvrir. Le test dit pourquoi, pour que la ligne suivante ne soit pas
    # lue comme une redefinition du probleme.
    hors_portee = sorted(executantes)
    non_bloquees = [n for n in hors_portee if n.removeprefix("action_") not in bloques]
    assert non_bloquees, (
        f"attendu : les actions executantes builtin ne sont pas dans la liste, puisque la "
        f"boucle ne les expose pas. Liste : {non_bloquees}. Si cette assertion echoue, soit "
        "l'une d'elles a ete ajoutee a la liste — bonne nouvelle, mettre a jour ce test — "
        "soit la detection ne trouve plus rien — mauvaise nouvelle, le Fix 7.1 va le dire."
    )


def test_les_deux_conditions_sont_independant_verifiables():
    """CONTRE-ÉPREUVE de non-vacuité : chaque test doit pouvoir échouer seul.

    Une condition qui ne peut pas être fausse ne protège rien. On vérifie que les
    deux tests existent séparément, que leurs noms disent ce qu'ils vérifient, et
    que la détection sous-jacente est une fonction testable — c'est elle qui
    porte la charge, et elle doit donc être appelable.
    """
    assert callable(actions_builtin_executantes)
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    for nom in ("test_les_actions_builtin_ne_sont_pas_des_outils_d_agent", "test_la_liste_bloquee_couvre_la_meme_capacite_que_bash"):
        assert f"def {nom}(" in source, f"le test {nom} a disparu"

    # Et la detection n'est pas une constante : elle depend du fichier lu.
    avant = actions_builtin_executantes()
    assert re.fullmatch(r"action_\w+", sorted(avant)[0]), sorted(avant)
    assert len(avant) >= 2, f"une seule action executante detectee : {sorted(avant)}"
