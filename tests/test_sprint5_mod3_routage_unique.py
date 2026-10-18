"""MOD-3 — source unique du routage modèle.

PREUVE 1 : register_endpoint existe dans endpoint_resolver (API unique).
PREUVE 2 : un seul module a register_endpoint.
PREUVE 3 : tous les modules délèguent vers endpoint_resolver.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.endpoint_resolver as er
import src.orchestrator.dispatcher as dispatcher
import src.ai_interaction as ai_interaction
import src.model_context as mc
import src.zen_router as zen_router


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset des caches avant chaque test."""
    er._reset_caches()
    dispatcher._reset_caches()
    ai_interaction._reset_caches()
    mc._reset_caches()
    zen_router._reset_caches()
    yield
    er._reset_caches()
    dispatcher._reset_caches()
    ai_interaction._reset_caches()
    mc._reset_caches()
    zen_router._reset_caches()


def test_register_endpoint_existe():
    """PREUVE 1 : register_endpoint existe dans endpoint_resolver (API unique)."""
    assert hasattr(er, "register_endpoint"), "endpoint_resolver.register_endpoint manquant"
    assert callable(er.register_endpoint), "register_endpoint n'est pas callable"


def test_tous_ont_reset_caches():
    """PREUVE : tous les modules ont _reset_caches pour l'isolation des tests."""
    for mod in (er, dispatcher, ai_interaction, mc, zen_router):
        assert hasattr(mod, "_reset_caches"), f"{mod.__name__} n'a pas _reset_caches"
        assert callable(mod._reset_caches), f"_reset_caches n'est pas callable dans {mod.__name__}"


def test_tous_importent_endpoint_resolver():
    """PREUVE 3 : les modules délèguent vers endpoint_resolver."""
    import inspect
    
    modules_a_verifier = [
        ("dispatcher", dispatcher),
        ("ai_interaction", ai_interaction),
        ("mc", mc),
        ("zen_router", zen_router),
    ]
    
    for nom, mod in modules_a_verifier:
        source = inspect.getsource(mod)
        # Vérifier que le module importe endpoint_resolver
        assert "endpoint_resolver" in source or "from src.endpoint_resolver" in source, (
            f"{nom} n'importe pas endpoint_resolver"
        )


def test_zen_router_delegate_resolution():
    """zen_router délègue la résolution à endpoint_resolver."""
    import inspect
    source = inspect.getsource(zen_router)
    # zen_router doit utiliser resolve_endpoint_runtime depuis endpoint_resolver
    assert "resolve_endpoint_runtime" in source or "from src.endpoint_resolver import" in source


def test_ai_interaction_delegate_resolution():
    """ai_interaction délègue la résolution runtime à endpoint_resolver."""
    import inspect
    source = inspect.getsource(ai_interaction)
    # _resolve_model utilise resolve_endpoint_runtime
    assert "resolve_endpoint_runtime" in source


def test_un_seul_endpoint_pour_changer():
    """PREUVE 2 : un seul module a register_endpoint."""
    # Seul endpoint_resolver doit avoir register_endpoint
    modules_avec_register = []
    for nom, mod in [
        ("model_context", mc),
        ("dispatcher", dispatcher),
        ("ai_interaction", ai_interaction),
        ("mc", mc),
        ("zen_router", zen_router),
    ]:
        if hasattr(mod, "register_endpoint"):
            modules_avec_register.append(f"{nom}.register_endpoint")
    
    assert not modules_avec_register, (
        f"Plusieurs modules ont register_endpoint : {modules_avec_register}. "
        "Il ne doit y avoir QU'UN endroit pour enregistrer un endpoint."
    )
    
    # endpoint_resolver DOIT l'avoir
    assert hasattr(er, "register_endpoint"), "endpoint_resolver doit avoir register_endpoint"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])