"""MOD-1 — route_loader dynamique via pkgutil.

PREUVE 1 : route_loader utilise pkgutil.iter_modules, pas d'imports statiques.
PREUVE 2 : l'ordre de chargement est déterministe (alphabétique).
PREUVE 3 : ajouter un fichier de route NE nécessite AUCUNE édition de route_loader.
"""

import importlib
import pathlib
import sys

import pytest

REPO = pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS")
sys.path.insert(0, str(REPO))


def test_route_loader_est_dynamique():
    """PREUVE 1 : route_loader utilise pkgutil.iter_modules, pas d'imports statiques."""
    import core.route_loader as rl
    import inspect
    
    # Check the discovery function
    source = inspect.getsource(rl._discover_route_modules)
    # Vérifier qu'il n'y a PAS d'imports statiques de routes.*
    lignes = source.split("\n")
    imports_routes = [l for l in lignes if "from routes." in l and "import" in l]
    assert not imports_routes, (
        f"route_loader a encore des imports statiques de routes.* : {imports_routes}"
    )
    # Vérifier qu'il utilise pkgutil.iter_modules
    assert "pkgutil.iter_modules" in source or "pkgutil.walk_packages" in source, (
        "route_loader n'utilise pas pkgutil.iter_modules"
    )


def test_ordre_deterministe():
    """PREUVE 2 : l'ordre de chargement est déterministe (alphabétique)."""
    import core.route_loader as rl
    import inspect
    
    source = inspect.getsource(rl._discover_route_modules)
    # Vérifier qu'il trie les modules découverts
    assert "sorted(" in source, (
        "L'ordre de chargement n'est pas explicitement trié"
    )


def test_decouverte_fonctionne():
    """PREUVE 2 : la découverte de modules fonctionne."""
    import core.route_loader as rl
    
    modules = rl._discover_route_modules()
    # Doit découvrir au moins 50 modules de routes
    assert len(modules) >= 50, f"Seulement {len(modules)} modules découverts, attendu >= 50"
    # Doit être trié alphabétiquement
    assert modules == sorted(modules), "Modules pas triés alphabétiquement"
    # Tous doivent être des modules routes.*_routes
    for m in modules:
        assert m.startswith("routes.") and m.endswith("_routes"), f"Module invalide: {m}"


def test_nouveau_fichier_route_est_auto_decouvert(tmp_path, monkeypatch):
    """PREUVE 3 : ajouter un fichier dans routes/ ne nécessite AUCUNE modification."""
    import core.route_loader as rl
    import importlib
    
    # Créer un module temporaire dans routes/
    routes_dir = pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS/routes")
    test_file = routes_dir / "test_mod1_routes.py"
    
    try:
        # Écrire un fichier de route minimal
        test_file.write_text("""
from fastapi import APIRouter
router = APIRouter(prefix="/test-mod1", tags=["test"])
@router.get("/ping")
async def ping(): return {"pong": True}
""", encoding="utf-8")
        
        # Recharger le route_loader
        import importlib
        import core.route_loader as rl
        importlib.reload(rl)
        
        # Vérifier que la route est découverte
        modules = rl._discover_route_modules()
        assert "routes.test_mod1_routes" in modules, (
            f"Le nouveau fichier n'a pas été découvert. Modules: {modules}"
        )
        
    finally:
        # Nettoyer
        test_file = pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS/routes/test_mod1_routes.py")
        if test_file.exists():
            test_file.unlink()
        importlib.reload(rl)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])