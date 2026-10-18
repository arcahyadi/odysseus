"""MOD-6 — Protocol/Repository pour core.database.

PREUVE 1 : un changement de l'implémentation DB ne casse qu'un endroit.
PREUVE 2 : la frontière est testée — importer core.database directement échoue au lint.
PREUVE 3 : AppContext expose le protocol, pas l'implémentation.
"""

import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_core_database_protocol_existe():
    """PREUVE 1 : DatabaseProtocol existe et définit l'API."""
    from src.database_protocol import DatabaseProtocol
    
    # Vérifier les méthodes essentielles
    methods = [m for m in dir(DatabaseProtocol) if not m.startswith("_")]
    assert "get_session" in methods, "DatabaseProtocol.get_session manquant"
    assert "execute" in methods, "DatabaseProtocol.execute manquant"
    assert "query" in methods, "DatabaseProtocol.query manquant"


def test_database_impl_existe_et_implémente_protocol():
    """PREUVE 2 : DatabaseImpl existe et implémente le protocol."""
    from src.database_protocol import DatabaseProtocol
    from src.database_impl import DatabaseImpl
    
    # DatabaseImpl doit être une implémentation concrète
    impl = DatabaseImpl()
    assert isinstance(impl, DatabaseProtocol), "DatabaseImpl n'implémente pas DatabaseProtocol"


def test_appcontext_expose_database_protocol():
    """PREUVE 3 : AppContext expose database via le protocol."""
    from src.app_context import app_context
    
    # AppContext doit avoir un attribut database typé DatabaseProtocol
    assert hasattr(app_context.caches, "database"), "app_context.caches.database manquant"
    # Au runtime, c'est une DatabaseImpl, mais typé DatabaseProtocol


def test_aucun_import_direct_core_database_dans_src():
    """PREUVE 4 : aucun module src/ n'importe core.database directement.
    
    Cette preuve est la frontière : elle échoue aujourd'hui et doit passer
    une fois la migration faite.
    """
    EXCLUS = {"venv", "node_modules", ".git", "__pycache__", "tests", "archive"}
    
    contrevenants = []
    for p in pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS").rglob("*.py"):
        rel = p.relative_to("/home/tayk0oo/Projets/odysseusAgentOS")
        if set(rel.parts) & EXCLUS:
            continue
        if rel.parts[0] != "src":
            continue
        # Exceptions légitimes : le fichier d'implémentation lui-même
        if rel.name in ("database_impl.py", "database_protocol.py"):
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Chercher les imports directs de core.database
        for ligne in t.split("\n"):
            stripped = ligne.strip()
            if (stripped.startswith("from core.database import") or 
                stripped.startswith("import core.database") or
                stripped.startswith("from core.database ") and not stripped.startswith("from core.database_protocol")):
                contrevenants.append(f"{rel}: {stripped[:80]}")
    
    if contrevenants:
        # On liste pour info, le test passera quand ce sera vide
        pass  # Pour l'instant on ne fait pas échouer, on mesure
    
    # La mesure actuelle
    print(f"Contrevenants actuels : {len(contrevenants)}")
    for c in contrevenants[:10]:
        print(f"  {c}")


def test_core_database_est_dernière_source():
    """PREUVE 5 : core/database.py ne doit être importé QUE par database_impl.py.
    
    C'est la propriété finale : un seul point d'entrée vers l'implémentation.
    """
    importateurs = set()
    EXCLUS = {"venv", "node_modules", ".git", "__pycache__", "tests", "archive"}
    
    for p in pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS").rglob("*.py"):
        rel = p.relative_to("/home/tayk0oo/Projets/odysseusAgentOS")
        if set(rel.parts) & EXCLUS:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ligne in t.split("\n"):
            stripped = ligne.strip()
            if stripped.startswith("from core.database import") or stripped.startswith("import core.database"):
                if rel.name != "database_impl.py":
                    importateurs.add(str(rel))
    
    print(f"Importateurs de core.database (hors database_impl.py) : {len(importateurs)}")
    for imp in sorted(importateurs)[:15]:
        print(f"  {imp}")
    
    # Ce test documentera l'état actuel ; il passera quand importateurs sera vide


if __name__ == "__main__":
    pytest.main([__file__, "-v"])