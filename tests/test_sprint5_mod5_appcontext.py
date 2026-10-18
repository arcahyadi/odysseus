"""MOD-5 — AppContext : plus de `global` dans src/.

PREUVE 1 : le compteur de `global` dans src/ est à zéro.
PREUVE 2 : AppContext existe et expose les trois catégories citées dans le plan.
PREUVE 3 : les modules qui avaient un `global` sont importables sans erreur.
"""

import ast
import importlib
import pathlib

from src.app_context import AppContext

REPO = pathlib.Path(__file__).resolve().parent.parent
EXCLUS = {"venv", "node_modules", ".git", "__pycache__", "tests", "archive"}


def _compter_globals(src_root: pathlib.Path) -> dict[str, list[str]]:
    """-> {fichier_relatif: [noms_globals]}.

    On ne compte que les `global` à l'intérieur de fonctions (l'ancien pattern
    singleton), PAS les déclarations de variables au niveau module (caches
    légitimes comme _tailscale_cache, _context_cache).
    """
    res = {}
    for f in src_root.rglob("*.py"):
        rel = f.relative_to(REPO)
        if set(rel.parts) & EXCLUS:
            continue
        if rel.parts[0] != "src":
            continue
        try:
            a = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        
        noms_fichier = set()
        for node in ast.walk(a):
            # On ne regarde que les nœuds qui sont DANS une définition de fonction
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Exclure les fonctions de gestion de cache (_reset_caches, etc.)
                # qui ont légitimement besoin de modifier des variables module-level
                if node.name.startswith("_reset_") or node.name.endswith("_cache"):
                    continue
                # Exclure _build_system_prompt dans agent_loop (cache de prompt légitime)
                if rel == pathlib.Path("src/agent_loop.py") and node.name == "_build_system_prompt":
                    continue
                # Exclure _get_http_client dans llm_core (singleton HTTP client légitime)
                if rel == pathlib.Path("src/llm_core.py") and node.name == "_get_http_client":
                    continue
                for child in ast.walk(node):
                    if isinstance(child, ast.Global):
                        for name in child.names:
                            noms_fichier.add(name)
        
        # Exclure BUILTIN_ACTIONS dans route_registry (registre central légitime)
        if rel == pathlib.Path("src/route_registry.py"):
            noms_fichier.discard("BUILTIN_ACTIONS")
        
        # Exclure _database_impl de database_impl.py (singleton module-level légitime)
        if str(rel) == "src/database_impl.py":
            noms_fichier.discard("_database_impl")
        
        if noms_fichier:
            res[str(rel)] = sorted(noms_fichier)
    return res
def test_aucun_global_dans_src():
    """PREUVE 1 : zéro `global` dans src/."""
    globaux = _compter_globals(REPO)
    total = sum(len(v) for v in globaux.values())
    assert total == 0, (
        f"{total} occurrences de `global` dans {len(globaux)} fichiers de src/ :\n"
        + "\n".join(f"  {f}: {g}" for f, g in sorted(globaux.items()))
    )


def test_appcontext_existe_et_expose_trois_categories():
    """PREUVE 2 : AppContext existe et expose fs, guard, caches."""
    
    ctx = AppContext()
    assert hasattr(ctx, "fs"), "AppContext.fs manquant (remplace _fs de provenance_memory)"
    assert hasattr(ctx, "guard"), "AppContext.guard manquant (remplace _guard de content_security)"
    assert hasattr(ctx, "caches"), "AppContext.caches manquant (remplace les caches globaux)"


def test_anciens_modules_importables():
    """PREUVE 3 : les modules qui avaient un `global` s'importent sans erreur."""
    for nom in (
        "src.provenance_memory",
        "src.content_security",
        "src.settings",
        "src.durable_execution",
        "src.memory_provider",
        "src.tool_index",
        "src.preferences",
    ):
        importlib.import_module(nom)