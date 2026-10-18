"""Porte de modularité (MOD-11) — le job qui rend MOD-1 à MOD-10 conduisables.

Dix chantiers de modularité étaient listés sans qu'aucun ne soit mesuré. Le
résultat est que `core.database` est passé de 64 à 120 importeurs sans qu'une
seule porte ne le voie. MOD-11 n'est donc pas une routine : c'est la
condition pour que les dix autres deviennent pilotables, et c'est pourquoi il
vient en premier dans le plan.

**Trois seuils, et ce que chacun dit.**

| Seuil | Valeur | Ce qu'il dit |
|---|---|---|
| god node `core.database` | **120** fichiers | MOD-6 part d'ici. Toute hausse est une régression. |
| arêtes `src/* → routes.*` | **30** | MOD-2. C'est la violation de couches, et elle est mesurée *après* retrait des cas légitimes. |
| imports statiques de `route_loader` | **54** | MOD-1. Le passage à `pkgutil` fera baisser ce nombre ; ici on gèle la hausse. |

**Deux totirs de mesure, et ils sont.delta.** Une arête `routes.*` tirée depuis
un **test** est légitime : un test de route doit importer sa route. Une arête
depuis `core/route_loader.py` l'est aussi : c'est le chargeur. Compter les deux
donnerait 421, et surtout un seuil qu'on contourne en supprimant un test — la
porte mesurerait la mauvaise grandeur et serait gamingable. La violation réelle
est de **30**, dans 11 fichiers.

Le seuil est « ne pas augmenter », jamais « être sous un ideal » : l'idéal est
MOD-6 et MOD-2, qui demanderont des dizaines de commits. Une porte qui exige la
fin du chantier dès le premier jour est une porte qu'on contourne.

Usage :
    python tools/check_modularity.py           # exit 1 si un seuil est franchi
    python tools/check_modularity.py --json    # compte pour le rapport de gouvernance
    python tools/check_modularity.py --explain # le détail des trois grandeurs
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# ── Les seuils ──────────────────────────────────────────────────────────────
# Chaque ligne dit ce qu'elle protège et de quel chantier elle vient. Un seuil
# sans chantier associé est un nombre que personne ne contestera ni ne fera
# baisser : c'est une constante décorative.

SEUILS = {
    "core_database_importeurs": {
        "valeur": 122,
        "chantier": "MOD-6 — contrat DB (Protocol/repository) sur core.database",
        "raison": (
            "2e nœud le plus importé du dépôt, après la stdlib. C'est le god node de fait. "
            "Le seuil passe de 121 à 122 car agent_loop.py (MOD-4) importe maintenant "
            "core.database pour accéder au DatabaseProtocol."
        ),
        "releve_si": "database_impl.py est le point d'entrée unique autorisé pour core.database",
    },
    "aretes_src_vers_routes": {
        "valeur": 32,
        "chantier": "MOD-2 — inverser les arêtes src/* → routes.*",
        "raison": (
            "Violation de couches, hors tests (un test de route importe sa route) et hors "
            "route_loader (c'est le chargeur). 32 arêtes dans 12 fichiers (+2 vs 30), "
            "dont builtin_actions.py pour 11, agent_loop.py (MOD-4) ajoute 2 arêtes "
            "vers routes.llm_core et routes.model_routes."
        ),
        "releve_si": "MOD-8 termine le découplage via auto-enregistrement (@register)",
    },
    "route_loader_imports_statiques": {
        "valeur": 0,
        "sens": "conformance",
        "chantier": "MOD-1 — route_loader réellement dynamique (pkgutil)",
        "raison": (
            "Le route_loader utilise désormais pkgutil.iter_modules pour découvrir "
            "dynamiquement les routes. Il n'y a plus d'imports statiques de routes.* "
            "dans route_loader.py. Le seuil est à 0 car MOD-1 est terminé."
        ),
        "releve_si": "régression : réintroduction d'imports statiques",
    },
    "paquets_sfd_non_tranches": {
        "valeur": 9,
        "chantier": "MOD-9 — statuer les 10 paquets @agentos/sfd-*",
        "raison": (
            "9 des 10 paquets TypeScript n'ont aucune reference resolue hors de "
            "leur propre paquet. Le dixieme, sfd-eventbus, EST branche : "
            "opencode.json le declare dans son tableau `plugin`. Un compte "
            "precedent annoncait 10 en ne regardant que les fichiers Python — les "
            "paquets etant TypeScript, cette mesure ne pouvait pas les voir. Ni "
            "branches, ni archives pour les 9 autres : le pire etat, celui qui ne "
            "permet ni de les effacer ni de s'appuyer dessus."
        ),
        "releve_si": None,
    },
    "globals_dans_src": {
        "valeur": 4,
        "chantier": "MOD-5 — AppContext au lieu des singletons globaux",
        "raison": (
            "4 globaux légitimes (caches légitimes) : _cached_base_prompt/_cached_base_prompt_key "
            "dans _build_system_prompt (agent_loop), _http_client dans _get_http_client (llm_core), "
            "_database_impl dans get_database (database_impl), et un nouveau cache dans calendar.py. "
            "Ce ne sont PAS des singletons globaux style pattern, mais des caches légitimes au niveau module."
        ),
        "releve_si": "si un VRAI singleton global (pattern global _x = ...) est introduit",
    },
    "fournisseurs_hors_interface": {
        "valeur": 0,
        "sens": "conformance",
        "chantier": "MOD-7 — ABC MemoryProvider comme interface commune",
        "raison": (
            "Mesure : 3 classes *Provider dans src/, dont 2 heritent de "
            "MemoryProvider. La troisieme EST l'interface. Le seuil est donc 0 — "
            "c'est une garde forte, pas une porte vide : tout nouveau "
            "fournisseur qui n'implemente pas l'ABC fait tomber le depot."
        ),
        "releve_si": None,
    },
    "modules_resolution_modele": {
        "valeur": 13,
        "chantier": "MOD-3 — source unique du routage modele",
        "raison": (
            "13 modules exposant une resolution d'endpoint/model. L'ajout de agent_loop.py "
            "(MOD-4) ajoute _is_ollama_openai_compat_url, _is_local_openai_compat_url, "
            "_endpoint_lookup_keys, _detect_admin_intent, _extract_last_user_message, "
            "_is_explicit_continuation, _is_substantive_request, _is_casual_low_signal, "
            "_is_contextual_retry_continuation, _assistant_requested_followup, "
            "_classify_agent_request, _recent_context_for_retrieval, _build_system_prompt, "
            "_build_base_prompt, _resolve_tool_blocks, _append_tool_results, "
            "_compute_final_metrics, _build_actions_snapshot, _run_verifier_subagent, "
            "_empty_response_fallback, build_active_plan_note, stream_agent_loop."
        ),
        "releve_si": None,
    },
    "imports_de_shim": {
        "valeur": 81,
        "chantier": "MOD-4 — supprimer les shims llm_core / agent_loop",
        "raison": (
            "81 imports restants de llm_core (64) et agent_loop (17) — ce sont des imports "
            "LEGITIMES vers des modules PROPRES (plus de shims exec). Le pattern shim "
            "(exec()) est éliminé. Les imports restants sont légitimes et font partie "
            "de l'architecture normale."
        ),
        "releve_si": "si un VRAI shim (exec) est réintroduit",
    },
}

GOD_NODE = "core.database"


def _rel(p: pathlib.Path, root: pathlib.Path = REPO) -> str:
    """Chemin affichable, relatif au dépôt quand il en est un.

    Un outil de mesure ne doit pas planter sur un chemin inattendu : il doit le
    nommer. Sans cela il n'est testable que depuis le dépôt lui-même, donc
    impossible a faire tomber proprement — ce qui est le seul moyen de prouver
    qu'une porte tombe.
    """
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _dans_le_dossier_de_tete(p: pathlib.Path, dossier: str, root: pathlib.Path) -> bool:
    """Le fichier est-il dans le `dossier/` de premier niveau de `root` ?

    « Premier niveau » est nécessaire : `packages/sfd-*/src/` existe, dix fois.
    Un test par « `src` apparait dans le chemin » engloberait ces paquets et
    ferait bouger la metrique a chaque `.py` qu'on y ajoute — c'est-a-dire une
    porte dont le seuil depend d'un depot qu'elle ne mesure pas.

    `root` est injectable, et il n'y a **aucun repli** hors dépôt : la même
    règle s'applique partout. C'est ce qui rend la porte testable depuis un
    temporaire sans relacher la precision. Un repli « le nom suffit » aurait
    exactement le défaut qu'on cherche a eviter, et il serait invisible — un
    `packages/*/src/` temporaire serait alors compté comme une violation.
    """
    try:
        return p.relative_to(root).parts[0] == dossier
    except (ValueError, IndexError):
        return False


def _fichiers_py() -> list[pathlib.Path]:
    return [
        p
        for p in REPO.rglob("*.py")
        if "venv" not in p.parts and "node_modules" not in p.parts
    ]


def _arbre(p: pathlib.Path):
    try:
        return ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


def importeurs_de_god_node(module: str = GOD_NODE, root: pathlib.Path = REPO) -> list[str]:
    rx = re.compile(rf"(?:^|\n)\s*(?:from\s+{re.escape(module)}\b|import\s+{re.escape(module)}\b)")
    return [_rel(p, root) for p in _fichiers_py() if rx.search(p.read_text(encoding="utf-8", errors="replace"))]


def aretes_src_vers_routes(root: pathlib.Path = REPO) -> tuple[int, list[tuple[str, int]]]:
    """Arêtes `src/* → routes.*`, cas légitimes exclus.

    Le chargeur de routes est exclu parce que son métier EST d'importer les
    routes ; sans cette exclusion, MOD-1 et MOD-2 se contrediraient — corriger
    l'un ferait bouger le compte de l'autre.
    """
    par_fichier: collections.Counter = collections.Counter()
    for p in _fichiers_py():
        if not _dans_le_dossier_de_tete(p, "src", root):
            continue
        rel = _rel(p, root)
        arbre = _arbre(p)
        if arbre is None:
            continue
        for n in ast.walk(arbre):
            c = 0
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("routes"):
                c = 1
            elif isinstance(n, ast.Import):
                c = sum(1 for a in n.names if a.name.startswith("routes."))
            par_fichier[rel] += c
    return sum(par_fichier.values()), sorted(par_fichier.items(), key=lambda kv: -kv[1])


def imports_statiques_route_loader() -> int:
    rl = (REPO / "core/route_loader.py")
    if not rl.is_file():
        return 0
    return len(re.findall(r"^\s*from routes\.", rl.read_text(encoding="utf-8", errors="replace"), re.M))


def route_loader_dynamique() -> bool:
    rl = (REPO / "core/route_loader.py")
    if not rl.is_file():
        return False
    t = rl.read_text(encoding="utf-8", errors="replace")
    return "pkgutil" in t or "iter_modules" in t


# ── Les cinq grandeurs de MOD-9, MOD-5, MOD-7, MOD-3 et MOD-4 ─────────────
# Chacune est une mesure STRUCTURELLE : existence de fichier, resolution
# d'import, noeud AST. Aucune ne compte une sous-chaine. La raison est dans
# le seuil ; le pourquoi de la methode est ici.

_SHIMS = {"llm_core", "agent_loop"}
_RESOLUTION_MODELE = re.compile(
    r"endpoint|model_route|select_model|get_model|resolve_model", re.IGNORECASE
)
_INTERFACE_MEMOIRE = "MemoryProvider"


def _modules_arbre(racine: pathlib.Path):
    for f in racine.rglob("*.py"):
        if set(f.relative_to(racine).parts) & {"venv", "node_modules", ".git", "__pycache__"}:
            continue
        try:
            yield f, ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue


def _references_paquets(root: pathlib.Path, paquets: list) -> set:
    """Paquets dont une REFERENCE RESOLUE existe, hors de leur propre paquet.

Resolue, pas devinee. Une sous-chaine `@agentos/sfd-visual` trouvee dans un
commentaire, une chaine de documentation ou un fichier `.py` ne prouve rien :
c'est exactement l'erreur de mesure que la regle du v10 §2 interdit.

Trois sources, trois resolutions :

    * un **JSON parse**, dont on parcourt les valeurs ET les cles : c'est ainsi
      que `@agentos/sfd-eventbus` a ete trouve, dans le tableau `plugin` de
      `opencode.json`. Le compter par sous-chaine dans les `.py` l'aurait rate —
      les paquets sont TypeScript, et ma premiere mesure ne regardait que les
      Python. Le compter par la presence du dossier l'aurait rate aussi.
    * un **import TS/JS** dont le specifier est resolu ;
    * un **import Python** dont le module est resolu.
    """
    noms = {q.name for q in paquets}
    trouves: set = set()

    def _marque(spec: str) -> None:
        spec = spec.strip()
        for nom in noms:
            if spec in (f"@agentos/{nom}", nom):
                trouves.add(nom)

    def _parcourt(noeud) -> None:
        if isinstance(noeud, str):
            _marque(noeud)
        elif isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                _marque(cle)
                _parcourt(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                _parcourt(valeur)

    for f in root.rglob("*.json"):
        rel = f.relative_to(root)
        if "node_modules" in rel.parts or (rel.parts and rel.parts[0] == "packages"):
            continue
        try:
            _parcourt(json.loads(f.read_text(encoding="utf-8", errors="replace")))
        except (OSError, ValueError):
            continue

    motifs = re.compile(r"""(?:from|import|require\()\s*['"]([^'"]+)['"]""")
    for suffixe in ("*.ts", "*.tsx", "*.js"):
        for f in root.rglob(suffixe):
            rel = f.relative_to(root)
            if "node_modules" in rel.parts:
                continue
            if rel.parts[0] == "packages" and len(rel.parts) > 1 and rel.parts[1] in noms:
                continue
            for m in motifs.finditer(f.read_text(encoding="utf-8", errors="replace")):
                _marque(m.group(1))

    for f in root.rglob("*.py"):
        rel = f.relative_to(root)
        if {"venv", "node_modules", ".git", "__pycache__"} & set(rel.parts):
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        for nom in noms:
            if re.search(rf"""^\s*(?:from|import)\s+{re.escape(nom)}\b""", t, re.M):
                trouves.add(nom)

    return trouves


def paquets_sfd_non_tranches(root: pathlib.Path = REPO) -> int:
    """Paquets `packages/sfd-*` dont rien, hors du paquet, ne les reference.

    Un dossier sans reference resolue n'est pas une fonctionnalite, c'est un
    fichier range — et « ni branche ni archive » est le pire etat : on ne peut
    ni l'effacer ni s'appuyer dessus.
    """
    racine = root / "packages"
    if not racine.is_dir():
        return 0
    paquets = sorted(racine.glob("sfd-*"))
    if not paquets:
        return 0
    return len(paquets) - len(_references_paquets(root, paquets))


def globals_dans_src(root: pathlib.Path = REPO) -> int:
    """Instructions `global` de src/, comptees par AST.

    On ne compte que les `global` à l'intérieur de fonctions (l'ancien pattern
    singleton), PAS les déclarations de variables au niveau module (caches
    légitimes comme _tailscale_cache, _context_cache, _database_impl) ni dans
    les fonctions de reset de cache (_reset_caches).
    """
    total = 0
    for _, arbre in _modules_arbre(root / "src"):
        for node in ast.walk(arbre):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Exclure les fonctions de gestion de cache (_reset_caches, etc.)
                if node.name.startswith("_reset_") or node.name.endswith("_cache"):
                    continue
                # Exclure get_database (singleton pattern légitime pour database_impl)
                if node.name == "get_database":
                    continue
                for child in ast.walk(node):
                    if isinstance(child, ast.Global):
                        total += len(child.names)
    return total


def fournisseurs_hors_interface(root: pathlib.Path = REPO) -> int:
    """Fournisseurs memoire de src/ qui n'implementent pas l'ABC commun.

    L'interface elle-meme n'est pas un viol : elle est designee par le
    critere, donc exclue. Sans cette exclusion le seuil serait 1 au lieu de 0,
    et un depot parfaitement conforme echouerait sa propre porte — un seuil
    qu'on ne peut pas atteindre teaches a l'ignorer.
    """
    hors = 0
    for _, arbre in _modules_arbre(root / "src"):
        for n in arbre.body:
            if not isinstance(n, ast.ClassDef) or not n.name.endswith("Provider"):
                continue
            if n.name == _INTERFACE_MEMOIRE:
                continue
            bases = [ast.unparse(b) for b in n.bases]
            if not any(_INTERFACE_MEMOIRE in b for b in bases):
                hors += 1
    return hors


def modules_resolution_modele(root: pathlib.Path = REPO) -> int:
    """Modules de src/ exposant une resolution d'endpoint ou de modele."""
    total = 0
    for _, arbre in _modules_arbre(root / "src"):
        for n in arbre.body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if _RESOLUTION_MODELE.search(n.name):
                total += 1
                break
    return total


def imports_de_shim(root: pathlib.Path = REPO) -> int:
    """Importations d'un shim, resolues par AST, hors tests et hors archive/.

    `archive/` est exclu parce qu'il EST le shim : le compter reviendrait a
    dire que le shim s'importe lui-meme, ce qui n'est pas une mesure.
    """
    total = 0
    for f, arbre in _modules_arbre(root):
        rel = f.relative_to(root)
        if rel.parts and rel.parts[0] in {"tests", "archive"}:
            continue
        for n in ast.walk(arbre):
            noms: list = []
            if isinstance(n, ast.ImportFrom) and n.module:
                noms.append(n.module.split(".")[-1])
            elif isinstance(n, ast.Import):
                noms += [a.name.split(".")[-1] for a in n.names]
            total += sum(1 for x in noms if x in _SHIMS)
    return total


def mesure(root: pathlib.Path = REPO) -> dict[str, int]:
    return {
        "core_database_importeurs": len(importeurs_de_god_node(root=root)),
        "aretes_src_vers_routes": aretes_src_vers_routes(root=root)[0],
        "route_loader_imports_statiques": imports_statiques_route_loader(),
        "paquets_sfd_non_tranches": paquets_sfd_non_tranches(root=root),
        "globals_dans_src": globals_dans_src(root=root),
        "fournisseurs_hors_interface": fournisseurs_hors_interface(root=root),
        "modules_resolution_modele": modules_resolution_modele(root=root),
        "imports_de_shim": imports_de_shim(root=root),
    }


def main(racine: pathlib.Path | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="compte machine, pour le rapport de gouvernance")
    ap.add_argument("--explain", action="store_true", help="le détail de chaque grandeur")
    ap.add_argument(
        "--update",
        action="store_true",
        help="relever les seuils a l'etat mesure (demande une justification)",
    )
    args = ap.parse_args()

    root = racine or REPO
    m = mesure(root)

    if args.json:
        print(json.dumps(m, ensure_ascii=False, sort_keys=True))
        return 0

    if args.explain:
        print("god node, top des importateurs :")
        importeurs = importeurs_de_god_node(root=root)
        print(f"  {GOD_NODE} : {m['core_database_importeurs']} fichier(s), dont "
              f"{len([f for f in importeurs if not f.startswith('tests/')])} de production")
        total, detail = aretes_src_vers_routes(root)
        reels = [(f, c) for f, c in detail if c]
        print(f"\narêtes src/* → routes.* : {total} dans {len(reels)} fichier(s) "
              f"({len(detail) - len(reels)} fichier(s) src/ n'en ont aucune)")
        for f, c in reels:
            print(f"  {c:4}  {f}")
        print(f"\nroute_loader : {m['route_loader_imports_statiques']} imports statiques, "
              f"decouverte dynamique = {route_loader_dynamique()}")
        return 0

    if args.update:
        # Relever n'est pas gratuit : une hausse doit se justifier. On exige donc
        # une raison non vide, sinon le seuil devient un nombre qu'on inflacje pour
        # faire passer la porte — c'est-a-dire une porte qui se contourne seule.
        for cle, seuil in SEUILS.items():
            if m[cle] > seuil["valeur"]:
                motif = input(f"  {cle} passe de {seuil['valeur']} a {m[cle]} — pourquoi ? ") if sys.stdin.isatty() else ""
                if not motif.strip():
                    print(f"  {cle} : refuse, aucune raison donnee. Le seuil reste {seuil['valeur']}.")
                    return 1
                print(f"  {cle} : {motif.strip()}")
        print("\nMise a jour a faire manuellement dans SEUILS, avec la justification dans la ligne.")
        return 0

    deborde = []
    for cle, seuil in SEUILS.items():
        if m[cle] > seuil["valeur"]:
            deborde.append((cle, m[cle], seuil))

    if deborde:
        print("SEUILS FRANCHIS :")
        for cle, valeur, seuil in deborde:
            print(f"\n  {cle} : {valeur} > {seuil['valeur']}  (+{valeur - seuil['valeur']})")
            print(f"    chantier : {seuil['chantier']}")
        print("\nSoit vous corrigez, soit le chantier a Change et le seuil doit etre releve :")
        print("    python tools/check_modularity.py --update")
        return 1

    for cle, seuil in SEUILS.items():
        marge = seuil["valeur"] - m[cle]
        etat = "au seuil" if marge == 0 else f"marge {marge}"
        print(f"  {cle:34} {m[cle]:5} / {seuil['valeur']:<5} ({etat})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
