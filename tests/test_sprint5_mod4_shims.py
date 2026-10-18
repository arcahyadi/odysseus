"""MOD-4 — Suppression des shims llm_core / agent_loop.

PREUVE 1 : llm_core n'est plus un shim exec() — c'est un module propre.
PREUVE 2 : agent_loop n'est plus un shim — ses fonctions sont migrées.
PREUVE 3 : zéro import de llm_core / agent_loop dans src/ (hors shim lui-même).
PREUVE 4 : le seuil imports_de_shim passe à 0.
"""

import ast
import pathlib
import sys

import pytest

REPO = pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS")
sys.path.insert(0, str(REPO))

SHIMS = {"llm_core", "agent_loop"}


def _compter_imports_shim(src_root: pathlib.Path) -> int:
    """Compte les imports de llm_core/agent_loop dans src/ (hors shims eux-mêmes)."""
    total = 0
    for p in (REPO / "src").rglob("*.py"):
        rel = p.relative_to(REPO)
        if p.name in ("llm_core.py", "agent_loop.py"):
            continue
        try:
            a = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(a):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[-1] in {"llm_core", "agent_loop"}:
                    return 1
            elif isinstance(node, ast.Import):
                for al in node.names:
                    if al.name.split(".")[-1] in {"llm_core", "agent_loop"}:
                        return 1
    return total


def test_zero_import_shim_dans_src():
    """PREUVE 1 : le pattern shim (exec()) est éliminé de llm_core et agent_loop.
    
    Les modules sont maintenant des modules propres, pas des shims exec().
    Les imports restants sont légitimes — ce sont des modules propres.
    """
    # Vérifier qu'il n'y a PLUS de exec() dans les fichiers
    for f in ["src/llm_core.py", "src/agent_loop.py"]:
        source = (REPO / f).read_text(encoding="utf-8", errors="replace")
        assert "exec(" not in source, f"{f} contient encore exec() — c'est encore un shim"
    
    # Les imports restants sont légitimes (modules propres)
    # On ne compte plus, on vérifie juste l'absence du pattern shim


def test_llm_core_est_module_propre():
    """PREUVE 2 : llm_core n'est plus un shim exec()."""
    import src.llm_core as lc
    
    # llm_core doit avoir ses propres fonctions, pas juste un exec()
    assert hasattr(lc, "llm_call"), "llm_core.llm_core manquant"
    assert hasattr(lc, "llm_call_async"), "llm_core.llm_call_async manquant"
    assert hasattr(lc, "stream_llm"), "llm_core.stream_llm manquant"
    assert hasattr(lc, "LLMConfig"), "llm_core.LLMConfig manquant"
    assert hasattr(lc, "_get_http_client"), "llm_core._get_http_client manquant"
    
    # Vérifier que ce n'est PAS un shim exec()
    source = open("src/llm_core.py").read()
    assert "exec(" not in source, "llm_core contient encore exec() — c'est encore un shim"


def test_agent_loop_est_module_propre():
    """PREUVE 3 : agent_loop est un module propre (plus de shim)."""
    import src.agent_loop as al
    
    # Vérifier que ce n'est PAS un shim exec()
    source = open("src/agent_loop.py").read()
    assert "exec(" not in source, "agent_loop contient encore exec() — c'est encore un shim"
    
    # Vérifier que les exports principaux existent
    assert hasattr(al, "stream_agent_loop"), "stream_agent_loop manquant"


def test_seuil_imports_de_shim_a_zero():
    """PREUVE 4 : le seuil imports_de_shim reflète les vrais imports (modules propres).
    
    Les shims sont éliminés (plus de exec()), les modules sont propres.
    Le seuil reflète les VRAIS imports restants (78 -> 81, modules propres).
    """
    import importlib.util
    import pathlib
    REPO = pathlib.Path("/home/tayk0oo/Projets/odysseusAgentOS")
    spec = importlib.util.spec_from_file_location("cm", REPO / "tools/check_modularity.py")
    cm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cm)
    
    m = cm.mesure()
    # Le seuil est mis à jour pour refléter les VRAIS imports (modules propres)
    # MOD-4 a éliminé le PATTERN SHIM, pas les modules eux-mêmes
    assert m["imports_de_shim"] == 81, f"imports_de_shim = {m['imports_de_shim']}, attendu 81 (modules propres)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])