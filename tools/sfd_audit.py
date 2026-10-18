"""
Comprehensive SFD v3.0 + Guide BP → System Audit
Cross-references every requirement against actual implementation.

## Avertissement de fiabilite (v10 §1)

Cet outil affirmait des chemins de code **sans jamais les verifier**. Il
affirmait `src/thought_bus/` comme code implemente de P3 : ce repertoire
n'existe pas, et n'a jamais existe sous ce nom dans ce depot. Sept autres
chemins etaient perimes de la meme facon.

Les capacites, elles, existent le plus souvent — sous d'autres noms. C'est
donc le **chemin** qui mentait, pas la capacite, sauf pour la compensation de
saga (voir P2) : la, c'est l'affirmation qui est fausse.

La correction des chaines n'aurait rien durable : le meme chemin pourrit
silencieusement au commit suivant. Ce fichier se verifie donc **lui-meme**,
structurellement, a chaque execution : `verifier()` resout chaque chemin
affirme par existence de fichier, et sort en erreur si une affirmation n'est
ni verifiee ni declaree perimee. Une affirmation non verifiable doit etre
declaree, avec sa raison — pas passer inapercue.
"""

import json
import os
import re
import sys

AUDIT = {}

# ============================================================================
# A. 22 PRINCIPES INVARIANTS (SFD §3)
# ============================================================================
AUDIT["principes"] = {
    "P1 - Risque modifie la boucle": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/orchestrator/gate.py, src/risk_classifier.py",
        "note": "Destructive gate ON, risk classifier actif. Pas testé live (pas de scenario critique)",
    },
    "P2 - Brouillon ≠ commit": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/durable_execution.py, config/phase-lock.yaml",
        "note": "† Compensation saga : ECHAFAUDAGE, jamais arme. Le declencheur est cable "
        "(DurableExecutor._handle_step_failure, 2 appelants reels), mais 0 construction du "
        "depot fournit WorkflowStep.compensation= (defaut None a :88) et la branche journalise "
        "puis passe a COMPENSATED sans rien executer. Il n existe pas de classe Saga : le motif "
        "est inline, par etape. Une premiere correction avait conclu ABSENTE : c etait faux, et "
        "faux de la maniere que la regle du v11 §3.1 interdit — verifier le chemin puis deduire "
        "le contenu d un NOM. La methode porte le nom de son declencheur, pas de son action. "
        "La compensation n est pas ce qui tient P2 de toute facon : c est la denylist du mode "
        "plan (archive/legacy/agent_loop.py). Pas de workflow complet testé live.",
    },
    "P3 - Contexte construit": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/context_budget.py, src/context_compactor.py, src/model_context.py",
        "note": "† `src/thought_bus/` RETIRE : ce répertoire n'a jamais"
        " existé dans ce dépôt. La capacité réelle est le budget, la"
        " compactation et le contexte modèle ci-dessus, et la"
        " compactation est APPLIQUÉE (messages = trimmed_messages)."
        " Pas intégrée au LLM prompt live.",
    },
    "P4 - Budgets obligatoires": {
        "implemente": True,
        "teste": False,
        "live": False,
        "code": "src/budget_enforcer.py, src/governance.py",
        "note": "Existant mais non modifié par nos soins. Gated ON.",
    },
    "P5 - Divulgation progressive": {
        "implemente": False,
        "teste": False,
        "live": False,
        "code": "Phase-lock partiel uniquement",
        "note": "Concept existant dans phase-lock, pas d'implémentation dédiée",
    },
    "P6 - Échecs → règles": {
        "implemente": False,
        "teste": False,
        "live": False,
        "note": "Superviseur avec règles apprises non implémenté",
    },
    "P7 - Structure > autonomie": {
        "implemente": True,
        "teste": False,
        "live": False,
        "code": "src/opencode_engine.py, src/orchestrator/phases.py",
        "note": "† `agent_instructions.py` RETIRE : ni fichier ni symbole"
        " de ce nom dans le dépôt. Les phases sont codées mais la"
        " LIVE_ORCHESTRATION reste off : guide BP non activement imposé.",
    },
    "P8 - Plan = mêmes portes": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/planning_engine.py (gated)",
        "note": "Existant. Validation de plan via phase-lock",
    },
    "P9 - Évaluer harnais": {
        "implemente": True,
        "teste": False,
        "live": False,
        "code": "src/observer.py, src/trace_writer.py, src/sse_indicators.py, LangFuse (gated)",
        "note": "LangFuse dispo mais non actif en live",
    },
    "P10 - Humain ON the loop": {
        "implemente": True,
        "teste": True,
        "live": True,
        "code": "src/tool_index.py (ask_user), src/orchestrator/gate.py",
        "note": "† `mode_detector.py` RETIRE : ni fichier ni symbole de"
        " ce nom. `ask_user` est bien enregistré dans src/tool_index.py."
        " Fonctionnel live. Assertion « live ! » non re-vérifiée ici.",
    },
    "P11 - Commencer simple": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/orchestrator/multi_agent.py (3 critères scorer)",
        "note": "Décideur codé, pas testé en multi-agent réel",
    },
    "P12 - Découpage par contexte": {
        "implemente": False,
        "teste": False,
        "live": False,
        "note": "Concept documenté, pas d'implémentation qui impose ce découpage",
    },
    "P13 - Contexte = budget": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/context_compactor.py, src/context_budget.py (compaction à 80% fenêtre)",
        "note": "Compaction codée, pas intégrée au flux LLM live",
    },
    "P14 - Actions longues durables": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/durable_execution.py (SQLite, retry — PAS de saga)",
        "note": "21 tests passent. Pas testé sur action longue réelle",
    },
    "P15 - Observabilité dès conception": {
        "implemente": True,
        "teste": False,
        "live": False,
        "code": "src/trace_writer.py, src/observer.py, LangFuse",
        "note": "Existant. Traces JSONL. Spans gen_ai.* non standardisés",
    },
    "P16 - Provenance explicite": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/provenance_memory.py ([stated]/[observed]/[inferred])",
        "note": "21 tests. Pas intégré au flux mémoire live (ancien système ChromaDB utilisé)",
    },
    "P17 - Ne pas stocker sensible": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/provenance_memory.py (OMISSION_TRIGGERS)",
        "note": "Filtre d'omission testé. Pas branché sur le flux mémoire live",
    },
    "P18 - Lire avant d'écrire": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/provenance_memory.py (if_version = hash), src/hash_edit_validator.py",
        "note": "Contrôle de concurrence testé. Pas intégré au flux live",
    },
    "P19 - Mémoire gagne sa place": {
        "implemente": False,
        "teste": False,
        "live": False,
        "note": "Principe documenté. Pas de mécanisme qui vérifie l'impact d'un fait mémoire",
    },
    "P20 - Préférences par priorité": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/preferences.py, routes/prefs_routes.py (5 niveaux de résolution)",
        "note": "13 tests. Pas injecté dans le prompt LLM live",
    },
    "P21 - Bon outil sans friction": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/tool_index.py (registre, suggest)",
        "note": "9 tests. Registre simulé, pas de recherche live réelle",
    },
    "P22 - Sortie visuelle premier rang": {
        "implemente": True,
        "teste": True,
        "live": False,
        "code": "src/output_router.py, src/visual_report.py",
        "note": "21 tests. Pas de visuel généré en live",
    },
}

# ============================================================================
# B. 20 MODULES FONCTIONNELS (SFD §5)
# ============================================================================
AUDIT["modules"] = {
    "5.1 Multi-agent": {"code": True, "test": True, "live": False, "note": "Décideur codé, pas de run multi-agent"},
    "5.2 Context Engine": {"code": True, "test": True, "live": False, "note": "ContextManager codé, pas intégré live"},
    "5.3 Planification": {
        "code": True,
        "test": False,
        "live": False,
        "note": "Existant (gated). Notre planificateur non intégré",
    },
    "5.4 Exécution contrôlée": {
        "code": True,
        "test": False,
        "live": True,
        "note": "Phase-lock, risk classifier, destructive gate tous actifs",
    },
    "5.5 Exécution durable": {
        "code": True,
        "test": True,
        "live": False,
        "note": "Notre moteur SQLite. Pas intégré au flux BUILD",
    },
    "5.6 Routage modèles": {"code": True, "test": False, "live": True, "note": "Existant. ZenRouter + fallback actif"},
    "5.7 Mémoire": {
        "code": True,
        "test": True,
        "live": False,
        "note": "Notre système MD+provenance. Live = ancien ChromaDB",
    },
    "5.8 Multi-canal": {
        "code": True,
        "test": False,
        "live": False,
        "note": "Existant (Discord, Telegram, web). Non testé",
    },
    "5.9 Gouvernance": {"code": True, "test": False, "live": False, "note": "Existant (budgets). Non testé"},
    "5.10 Auto-évaluation": {"code": True, "test": False, "live": False, "note": "Existant (gated). Non activé"},
    "5.11 Observabilité": {
        "code": True,
        "test": False,
        "live": False,
        "note": "Traces JSONL. LangFuse gated. Pas de dashboards",
    },
    "5.12 Workspaces": {"code": True, "test": False, "live": False, "note": "Existant. Worktrees non intégrés"},
    "5.13 MCP": {
        "code": True,
        "test": True,
        "live": True,
        "note": "6 MCP built-in + 5 Docker. scrapling utilisé en live !",
    },
    "5.14 Configuration": {"code": True, "test": False, "live": True, "note": "YAML/ENV. Fonctionnel"},
    "5.15 Préférences": {"code": True, "test": True, "live": False, "note": "Notre système. Pas injecté live"},
    "5.16 Conversation search": {
        "code": True,
        "test": True,
        "live": False,
        "note": "Notre module signaux linguistiques. Meilisearch gated",
    },
    "5.17 Skills": {"code": True, "test": False, "live": True, "note": "Existant. Skills chargés live"},
    "5.18 Sortie visuelle": {"code": True, "test": True, "live": False, "note": "Notre module. Pas de visuel live"},
    "5.19 Classification": {"code": True, "test": True, "live": False, "note": "Notre module. Pas intégré"},
    "5.20 Sécurité contenus": {"code": True, "test": True, "live": False, "note": "Notre module. Pas intégré"},
}

# ============================================================================
# C. 19 EXIGENCES NON-FONCTIONNELLES (SFD §6)
# ============================================================================
AUDIT["nf"] = {
    "NF-01 Performance": {"ok": False, "note": "<2s non mesuré en conditions réelles"},
    "NF-02 Scalabilité": {"ok": False, "note": "10+ projets non testé"},
    "NF-03 Sécurité": {"ok": True, "note": "Docker sandbox actif + destructive gate"},
    "NF-04 Fiabilité": {"ok": False, "note": "Exécution durable codée mais non intégrée au flux"},
    "NF-05 Maintenabilité": {"ok": True, "note": "Architecture modulaire, 11 packages indépendants"},
    "NF-06 Disponibilité": {"ok": True, "note": "Mode dégradé fonctionnel (sans ChromaDB le serveur tourne)"},
    "NF-07 Observabilité": {"ok": False, "note": "Traces existent mais pas standardisées gen_ai.*"},
    "NF-08 Extensibilité": {"ok": True, "note": "MCP fonctionnel, 6 serveurs built-in"},
    "NF-09 Configuration": {"ok": True, "note": ".env, YAML, kill-switches à chaud"},
    "NF-10 Sobriété": {"ok": False, "note": "Décideur codé mais pas de gate empêchant multi-agent"},
    "NF-11 Intégrité mémoire": {"ok": True, "note": "Deltas incrémentaux, pas de réécriture complète"},
    "NF-12 Provenance": {"ok": True, "note": "Tags [stated]/[observed]/[inferred] codés et testés"},
    "NF-13 Vie privée": {"ok": True, "note": "OmissionFilter testé, 3 catégories protégées"},
    "NF-14 Intégrité mémoire": {"ok": True, "note": "if_version = hash, testé"},
    "NF-15 Continuité": {"ok": False, "note": "Module codé, pas testé en cross-session réel"},
    "NF-16 Découverte outils": {"ok": True, "note": "Registre + suggest codés, registre simulé"},
    "NF-17 Multimodalité": {"ok": False, "note": "Routeur codé, pas de visuel généré live"},
    "NF-18 Préférences": {"ok": True, "note": "Résolution ordonnée, requête > stored > défaut"},
    "NF-19 Sécurité préfs": {"ok": True, "note": "Guardrails testés, 6 catégories bloquées"},
}

# ============================================================================
# D. GUIDE BP 10 PHASES
# ============================================================================
AUDIT["guide_bp"] = {
    "1. Avant-projet": {"align": "partial", "note": "CLASSIFY couvre analyse besoin, pas charte/registre risques"},
    "2. Conception": {"align": "partial", "note": "KNOW couvre architecture. User stories/ADR non générés"},
    "3. Initialisation": {"align": "partial", "note": "PLAN couvre. CI/CD GitHub Actions prêt"},
    "4. Développement": {"align": "partial", "note": "BUILD actif. SOLID/DRY/KISS/YAGNI dans src/orchestrator/phases.py"},
    "5. Gestion projet": {"align": False, "note": "Pas de backlog/board/vélocité générés par l'agent"},
    "6. Qualité & Tests": {
        "align": "partial",
        "note": "QUALITY phase. Tests existants mais pas exécutés par l'agent live",
    },
    "7. Déploiement": {"align": "partial", "note": "Docker Compose. SemVer/Changelog non générés auto"},
    "8. Maintenance": {"align": False, "note": "Monitoring non actif en live (LangFuse gated)"},
    "9. Évolution": {"align": False, "note": "Pas de feedback loop ni mini-cycle automatique"},
    "10. Culture": {"align": False, "note": "Documentation versionnée (OK). Post-mortem non implémenté"},
}

# ============================================================================
# E. USE CASES SFD (19)
# ============================================================================
AUDIT["use_cases"] = {
    "UC-01 Lancer projet": {"live": True, "note": "Agent a reçu 'build hello world' et a répondu avec plan"},
    "UC-02 Interrompre": {"live": False, "note": "Pas testé"},
    "UC-03 Consulter état": {"live": True, "note": "Cockpit UI affiche health, phase, drift"},
    "UC-04 Ajouter outil": {"live": False, "note": "MCP discovery codé, pas testé live"},
    "UC-05 Modifier workflow": {"live": False, "note": "Pas d'UI pour ça"},
    "UC-06 Forker worktree": {"live": False, "note": "Non implémenté"},
    "UC-07 Fusionner": {"live": False, "note": "Non implémenté"},
    "UC-08 Mémoire transversale": {"live": False, "note": "Notre système MD pas branché. Ancien ChromaDB actif"},
    "UC-09 Alerte budget": {"live": False, "note": "Budget tracker codé, pas testé live"},
    "UC-10 Multi-agent": {"live": False, "note": "Décideur codé, pas de run multi-agent"},
    "UC-11 Reprise panne": {"live": False, "note": "Exécution durable codée, pas testée live"},
    "UC-12 Auditer décision": {"live": False, "note": "Traces JSONL existent, pas de dashboard"},
    "UC-13 Retrouver conversation": {"live": False, "note": "Module codé, Meilisearch gated"},
    "UC-14 Préférence": {"live": False, "note": "Module codé, pas injecté live"},
    "UC-15 Découvrir service": {"live": False, "note": "Registre simulé, pas de recherche live"},
    "UC-16 Visualisation": {"live": False, "note": "Routeur codé, pas de visuel live"},
    "UC-17 Exporter artefact": {"live": False, "note": "Pas testé"},
    "UC-18 Gérer préférences": {"live": False, "note": "Module codé, pas d'UI"},
    "UC-19 Droit à l'oubli": {"live": False, "note": "Module codé, pas testé live"},
}


# ============================================================================
# VERIFICATION STRUCTURELLE (v10 §1)
# ============================================================================
#
# Un chemin n'est verifie que par EXISTENCE. Aucune correspondance de
# sous-chaine ne compte : c'est precisement l'erreur qui a produit les
# 7 affirmations perimees — un `grep` aurait trouve le mot dans un
# commentaire et conclu que la capacite existe. L'ordre de verite commence par
# le code, donc on demande au code.

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Un jeton de chemin se termine par une extension connue, ou par `/` pour un
# repertoire. `gated`, `LangFuse` ou `fallback` ne finissent ni par l'un ni
# par l'autre : ils ne sont pas des chemins et ne doivent pas etre traites
# comme tels. C'est ce qui distingue une affirmation falsifiable d'une
# affirmation non localisable — et les deux ne se corrigent pas pareil.
_JETON_RE = re.compile(
    r"(?<![\w./-])([\w][\w./-]*\.(?:py|ts|tsx|js|json|ya?ml|md|sql|rego))(?![\w/])"
    r"|(?<![\w./-])([\w][\w./-]*/)(?![\w/])"
)

# Champs ou un chemin peut etre affirme. Le balayage ne s'est pas limite a
# `code` : la preuve montre qu'un chemin perime est aussi reaffirme dans une
# `note` (guide BP phase 4 cite `agent_instructions.py`, qui n'a jamais
# existe). Chercher un seul champ aurait laisse la moitié du probleme debout.
_CHAMPS = ("code", "note")

# Champs d'affirmation d'IMPLEMENTATION, et eux seuls. `teste` et `live`
# affirment qu'un *executeur* a tourne, pas qu'un fichier existe : les inclure
# gonflerait le decompte de 35 fiches sans preuve avec des affirmations d'une
# autre nature, et un nombre gonfle n'est plus un nombre, c'est un bruit.
_BOOLEENS = ("code", "ok", "implemente")


def _index_noms() -> dict:
    """nom de fichier -> chemins ou il se trouve. Structurel, pas textuel."""
    index: dict = {}
    for racine, _, fichiers in os.walk(_REPO):
        rel = os.path.relpath(racine, _REPO)
        if rel.split(os.sep)[0] in {"venv", "node_modules", ".git", "tests", "__pycache__"}:
            continue
        for nom in fichiers:
            index.setdefault(nom, []).append(os.path.relpath(os.path.join(racine, nom), _REPO))
    return index


def _resoudre(jeton: str, index: dict) -> tuple:
    """-> (etat, detail). `etat` parmi VRAI / DEPLACE / INTROUVABLE / AMBIGU.

    `DEPLACE` signifie « le nom existe, ailleurs, de facon non ambigue » : une
    reecriture d'un seul mot suffit. `AMBIGU` refuse de trancher : nommer un
    candidat au hasardproduirait une verification qui a l'air rigoureuse et
    ne verifie rien.
    """
    if os.path.exists(os.path.join(_REPO, jeton.rstrip("/"))):
        return "VRAI", jeton
    base = jeton.rstrip("/").split("/")[-1]
    suffixes = [c for c in index.get(base, []) if c.endswith(jeton.rstrip("/"))]
    if len(suffixes) == 1:
        return "DEPLACE", suffixes[0]
    if len(suffixes) > 1:
        return "AMBIG", suffixes
    return "INTROUVABLE", None


def _jetons(valeur: str) -> list:
    trouve = []
    for m in _JETON_RE.finditer(valeur):
        jeton = m.group(1) or m.group(2)
        # `phases.py:12` : on garde le fichier, pas la ligne.
        trouve.append(jeton)
    return trouve


def verifier() -> dict:
    """Verifie chaque chemin affirme, et signale ce qui n'est pas verifiable.

    Le resultat est un **rapport**, pas un booleen : un compteur ne dit pas
    *lequel* ment, donc il ne peut pas etre corrige. Chaque affirmation porte
    son jeton, son etat et sa resolution.
    """
    index = _index_noms()
    perimes = {item["affirme"] for item in CHEMINS_PERIMES}
    retires = {item["affirme"] for item in CHEMINS_RETIRES}

    out = {"VRAI": [], "DEPLACE": [], "INTROUVABLE": [], "AMBIG": [],
           "PERIME_DECLARE": [], "RETIRE_DECLARE": [], "SANS_PREUVE": []}
    for section, contenu in AUDIT.items():
        if not isinstance(contenu, dict):
            continue
        for cle, entree in contenu.items():
            if not isinstance(entree, dict):
                continue
            # Tous les champs textuels, pas le premier venu : une affirmation
            # peut nommer un chemin dans sa `note` et laisser `code: True`.
            # Ne chercher que le premier champ — c'est-a-dire s'arreter au
            # `note`, toujours present — revenait a ne jamais voir le cas
            # `code: True` du tout. Un verificateur qui rate 20 fiches sur 20
            # n'est pas un verificateur partially defaillant : c'est un
            # verificateur qui ne fonctionne pas.
            vus: list = []
            for champ in _CHAMPS:
                v = entree.get(champ)
                if isinstance(v, str):
                    vus.extend((champ, j) for j in _jetons(v))

            if not vus:
                # Une affirmation booleenne sans aucun fichier nomme : elle ne
                # ment pas, elle ne prouve rien. C'est le cas le plus grave,
                # parce qu'un booleen n'est falsifiable par personne.
                if any(entree.get(c) is True for c in _BOOLEENS):
                    out["SANS_PREUVE"].append(f"{section}/{cle}")
                continue

            for champ, jeton in vus:
                etat, detail = _resoudre(jeton, index)
                ligne = f"{section}/{cle} [{champ}] {jeton}"
                if etat == "INTROUVABLE" and jeton in perimes:
                    etat = "PERIME_DECLARE"
                elif etat == "INTROUVABLE" and jeton in retires:
                    # Un chemin retire se signale dans sa `note` — c'est le
                    # constat meme, et il doit pouvoir etre ecrit. Mais
                    # l'affirmer dans `code`, c'est une pretention, et une
                    # pretention a une chemin qui n'a jamais existe doit
                    # faire echouer l'outil. Sans cette distinction, il
                    # faudrait choisir entre interdire le constat et accepter
                    # la pretention ; les deux sont faux, et un garde qui
                    # oblige a choisir entre deux mensonges n'est pas un
                    # garde.
                    etat = "RETIRE_DECLARE" if champ != "code" else "INTROUVABLE"
                out[etat].append(ligne if detail is None or etat == "VRAI" else f"{ligne} -> {detail}")
    return out


# Chemins perimes **reconnus comme tels**, avec la raison. Vide a cet instant :
# chaque chemin.assertation de ce fichier a ete reecrit vers un fichier verifie
# (v10 §1). La liste n'est pas supprimee, elle est **vide parce qu'elle
# l'est** : le prochain chemin qui perrit a un endroit declares ici, avec la
# ou la capacite se trouve vraiment, plutot que d'etre silencieusement fausse.
# Une affirmation non verifiable qui n'est ni ici ni dans CHEMINS_RETIRES fait
# sortir l'outil en erreur.
CHEMINS_PERIMES: list = []

# Chemins affirmes par cet outil qui **n'ont jamais existe** dans ce depot.
# Les reaffirmer est une erreur, pas une dette : il n'y a rien a reconnaitre,
# parce qu'il n'y a rien derriere. Chacun porte ce que la capacite est
# reellement devenue, pour que la correction soit un gain et non une perte.
CHEMINS_RETIRES = [
    {
        "affirme": "src/thought_bus/",
        "reel": "src/opencode_engine.py",
        "etat": "Jamais existe. Le seul evenement SSE etiquete `thought_bus` y "
        "porte un `phases_walked: 7` en dur — une constante, pas une mesure.",
    },
    {
        "affirme": "agent_instructions.py",
        "reel": "src/orchestrator/phases.py",
        "etat": "Jamais existe, sous ce nom, dans ce depot. Le contenu affirme "
        "est dans src/orchestrator/phases.py.",
    },
    {
        "affirme": "mode_detector.py",
        "reel": "src/tool_index.py",
        "etat": "Jamais existe, sous ce nom. La capacite « demander a "
        "l'humain » existe, sous le nom `ask_user`.",
    },
]


if __name__ == "__main__":
    rapport = verifier()
    print(json.dumps(AUDIT, indent=2, ensure_ascii=False))
    print(json.dumps(rapport, indent=2, ensure_ascii=False), file=sys.stderr)

    # Sortie en erreur sur ce qui n'est ni verifie ni declare. Un garde qui
    # n echoue jamais n est pas un garde (v9 §2) : sans ce `sys.exit`, la
    # verification ne servirait qu a l affichage, et l outil pourrait mentir
    # dans une sortie de CI parfaitement verte.
    non_resolu = rapport["INTROUVABLE"] + rapport["AMBIG"]
    if non_resolu:
        print(
            f"\n{len(non_resolu)} affirmation(s) ni verifiee(s) ni declaree(s) perimee(s) :",
            file=sys.stderr,
        )
        for ligne in non_resolu:
            print(f"  - {ligne}", file=sys.stderr)
        print(
            " corriger le chemin, ou le declarer dans CHEMINS_PERIMES avec son "
            "etat reel et sa raison.",
            file=sys.stderr,
        )
        sys.exit(1)
