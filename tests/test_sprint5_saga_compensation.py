"""§1 du v11 — la compensation saga : trois états distincts, et un garde qui les tient.

La correction du v10 a conclu « compensation ABSENTE » en cherchant des
symboles dont le **nom** portait `compens`/`saga`. La compensation existe : la
méthode s'appelle d'après son **déclencheur**, `_handle_step_failure`. C'est
l'erreur que la règle du v11 §3.1 interdit — vérifier le chemin, puis déduire le
contenu d'un nom.

L'état réel est plus fin que « présent » et plus fin que « absent » :

* le **déclencheur** est câblé — 2 appelants réels ;
* le **mécanisme** n'est **jamais armé** — `WorkflowStep.compensation` vaut
  `None`, et 0 construction du dépôt ne fournit `compensation=` ;
* l'**action** n'est **pas exécutée** — la branche journalise puis passe le
  statut à `COMPENSATED` sans rien lancer.

Ces trois faits sont épinglés ici. Un garde qui constate l'absence est
inutile : ici on **protège un état mesuré**, pour que le jour où quelqu'un
arme ou implémente la compensation, la suite l'oblige à le faire
sciemment — et non à believes que la capacité existe parce qu'un crochet
tourne.

Et le garde a son entrée cassée, exigée par la règle du v11 §3.2 : armer un
pas **sans** exécuter quoi que ce soit doit faire tomber la suite. C'est
exactement le défaut qu'on constate aujourd'hui dans le code, et c'est
précisément pour cela qu'il doit être interdit.
"""

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
DE = REPO / "src/durable_execution.py"

def _arbre() -> ast.Module:
    return ast.parse(DE.read_text(encoding="utf-8", errors="replace"))


def _classe(arbre: ast.Module, nom: str) -> ast.ClassDef:
    return next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == nom)


def _appels_armes(repo: pathlib.Path) -> list:
    """Constructions de WorkflowStep qui fournissent `compensation=`.

    Résolution par AST dans **tout** le dépôt, hors tests : un test qui arme
    la compensation ne prouve pas que la production le fait, et l'inverse
    On ne compte donc rien : on liste, et on decide apres.
    """
    trouve = []
    for f in repo.rglob("*.py"):
        rel = f.relative_to(repo)
        if {"venv", "node_modules", ".git", "__pycache__"} & set(rel.parts):
            continue
        try:
            a = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for n in ast.walk(a):
            if not isinstance(n, ast.Call):
                continue
            nom = ast.unparse(n.func).split(".")[-1]
            if nom != "WorkflowStep":
                continue
            for kw in n.keywords:
                if kw.arg == "compensation":
                    trouve.append(f"{rel}:{n.lineno}")
    return trouve


def test_le_declencheur_de_compensation_est_cable():
    """PREUVE 1 : le premier des trois faits. Il est vrai, et il doit le rester.

    On l'épingle parce que c'est lui que j'ai nié par erreur. Un garde qui
    Protège l'absence d'un crochet existant amènerait à réécrire la
    documentation — c'est-à-dire à rendre l'audit plus faux qu'il n'était.
    """
    a = _arbre()
    execu = _classe(a, "DurableExecutor")
    assert any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_handle_step_failure" for n in execu.body
    ), "le crochet de compensation a disparu : c'est un changement d'etat, il doit etre decide"

    appels = [
        f"{DE.relative_to(REPO)}:{n.lineno}"
        for f in REPO.rglob("*.py")
        if not ({"venv", "node_modules", ".git", "__pycache__"} & set(f.relative_to(REPO).parts))
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8", errors="replace")))
        if isinstance(n, ast.Call) and "_handle_step_failure" in ast.unparse(n.func)
    ]
    assert len(appels) >= 2, (
        f"le declencheur n'a plus que {len(appels)} appelant(s) : {appels}. "
        "Le declencheur etait cable sur deux sites reels (durable_execution.py:161 et :188)."
    )


def test_le_champ_de_compensation_n_est_arme_par_personne():
    """PREUVE 2 : le deuxième fait — l'échafaudage n'est jamais armé.

    `WorkflowStep.compensation` vaut `None` par défaut, et aucune construction
    du dépôt ne fournit `compensation=`. C'est ce qui distingue cette
    capacité d'une capacité *dormante* : une dormante s'allume avec un
    interrupteur, celle-ci n'a pas d'interrupteur possible, puisque rien ne
    peut armer le crochet.
    """
    a = _arbre()
    ws = _classe(a, "WorkflowStep")
    champ = next(
        n for n in ws.body if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "compensation"
    )
    assert ast.unparse(champ.value) == "None", (
        f"le defaut de WorkflowStep.compensation est {ast.unparse(champ.value)!r} : "
        "l'etat mesure a change, il faut le consigner."
    )
    armes = _appels_armes(REPO)
    assert not armes, (
        f"quelqu'un arme desormais la compensation : {armes}. Deux lectures possibles — "
        "soit l'action est reellement executee, et le statut du v11 doit passer de ABSENT a "
        "PRESENT ; soit elle ne l'est toujours pas, et la compensation vient de devenir une "
        "affirmation de plus sans capacite. Trancher, ne pas laisser trancher la suite."
    )


def test_le_crochet_arme_sans_executer_est_interdit():
    """PREUVE 3 — le garde à entrée cassée (règle v11 §3.2).

    Si la compensation est un jour armée, la branche doit **exécuter** quelque
    chose. Aujourd'hui elle journalise et passe le statut à `COMPENSATED` :
    c'est-à-dire qu'elle **marquerait** des étapes compensées sans en
    compenser aucune. Un marqueur de plus serait pire que rien, parce qu'il
    ferait croire à une reprise atomique.

    Le test est écrit pour échouer le jour où quelqu'un arme — c'est ce qui en
    fait un garde et non une description. L'entrée cassée est demontre
    demonstratee par la mutation M1 du lot de mutations.
    """
    a = _arbre()
    execu = _classe(a, "DurableExecutor")
    crochet = next(n for n in execu.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_handle_step_failure")

    # Ce que la branche fait reellement, une fois le `if step.compensation:` retire.
    #
    # Le critere est « une ACTION », pas « un appel » : un `range(...)` de
    # parcours inverse n'execute rien, et le compter comme une action rendrait la
    # mesure incapable de distinguer un crochet qui travaille d'un crochet qui
    # tourne. Une action est donc soit un appel **attendu**, soit un appel
    # d'execution nomme comme tel. Un critere large donnerait un resultat large,
    # et un resultat large ne prouve rien.
    executes = []
    for n in ast.walk(crochet):
        if isinstance(n, ast.Await) and isinstance(n.value, ast.Call):
            executes.append(("await " + ast.unparse(n.value.func), n.lineno))
        elif isinstance(n, ast.Call):
            fn = ast.unparse(n.func)
            if any(mot in fn.lower() for mot in ("subprocess", "shell", "popen", "exec", "run_", "command")):
                executes.append((fn, n.lineno))

    if _appels_armes(REPO):
        assert executes, (
            "la compensation est desormais armee, mais la branche n'execute rien : "
            "elle passe seulement le statut a COMPENSATED. Marquer une etape compensee "
            "sans la compenser est plus trompeur que de ne rien faire — c'est une "
            "reprise atomique simulee."
        )
    else:
        # Etat actuel : rien n'est arme, donc rien ne s'execute, et c'est consigne.
        assert not executes, (
            f"la branche execute {executes} alors que rien n'est arme : "
            "soit l'etat a change, soit il y a du code mort."
        )


def test_les_docs_du_module_ne_promettent_pas_plus_que_le_code():
    """PREUVE 4 : la documentation du code ne peut pas affirms davantage que lui.

    C'est le point de départ du v11 : `sfd_audit.py` affirmait une compensation
    que le code ne faisait pas. Les docstrings du module avaient la même
    promesse. Un code dont la documentation décrit une capacité absente est un
    mensonge qui se propage — et il se propage mieux qu'une erreur dans un
    audit, parce qu'il ne demande à personne de le vérifier.
    """
    texte = DE.read_text(encoding="utf-8", errors="replace")
    module_doc = ast.get_docstring(_arbre()) or ""
    if not _appels_armes(REPO):
        assert "jamais arme" in module_doc or "jamais armé" in module_doc, (
            "le module ne dit plus que la compensation est un echafaudage non arme, "
            "alors que c'est l'etat mesure. Rendre la promesse serait announcee."
        )
    assert "PAS de saga" in texte or "jamais armé" in texte or "jamais arme" in texte, (
        "plus aucune trace de l'etat reel de la compensation dans le module : "
        "le silence n'est pas une correction, c'est une disparition de l'information."
    )
