"""Route Registry — Registre central pour découpler src/ et routes/.

Au lieu que src/ importe routes.* et routes/* importe src/*,
tout passe par ce registre central. C'est le pattern "Registry" pour
briser les dépendances circulaires et le couplage fort.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

# Registres
_ACTIONS: Dict[str, Callable] = {}
_ROUTERS: Dict[str, Any] = {}
_SERVICES: Dict[str, Any] = {}

# ─── Actions builtin (depuis builtin_actions.py) ───────────────────────────

def register_action(name: str, func: callable) -> None:
    """Enregistre une action builtin."""
    _ACTIONS[name] = func


def get_action(name: str) -> callable | None:
    """Récupère une action builtin par son nom."""
    return _ACTIONS.get(name)


def get_all_actions() -> Dict[str, callable]:
    """Retourne toutes les actions builtin enregistrées."""
    return dict(_ACTIONS)


# ─── Routers ───────────────────────────────────────────────────────────────

def register_router(name: str, router: Any) -> None:
    """Enregistre un router FastAPI."""
    _ROUTERS[name] = router


def get_router(name: str) -> Any:
    """Récupère un router par son nom."""
    return _ROUTERS.get(name)


def get_all_routers() -> Dict[str, Any]:
    """Retourne tous les routers enregistrés."""
    return dict(_ROUTERS)


# ─── Services ──────────────────────────────────────────────────────────────

def register_service(name: str, service: Any) -> None:
    """Enregistre un service."""
    _SERVICES[name] = service


def get_service(name: str) -> Any:
    """Récupère un service par son nom."""
    return _SERVICES.get(name)


def get_all_services() -> Dict[str, Any]:
    """Retourne tous les services enregistrés."""
    return dict(_SERVICES)


# ─── API de compatibilité pour builtin_actions ──────────────────────────────

BUILTIN_ACTIONS: Dict[str, callable] = {}  # sera peuplé par l'initialisation


def register_builtin_actions() -> None:
    """Initialise les actions builtin depuis le registre central.
    
    À appeler AU DÉMARRAGE de l'application (dans route_loader ou app_initializer).
    """
    global BUILTIN_ACTIONS
    BUILTIN_ACTIONS.clear()
    BUILTIN_ACTIONS.update(_ACTIONS)


# ─── Reset pour tests ──────────────────────────────────────────────────────

def _reset_for_tests() -> None:
    """Vide tous les registres. Pour l'isolation des tests."""
    global _ACTIONS, _ROUTERS, _SERVICES, BUILTIN_ACTIONS
    _ACTIONS.clear()
    _ROUTERS.clear()
    _SERVICES.clear()
    BUILTIN_ACTIONS.clear()


# Pour compatibilité avec l'ancien code
RouteRegistry = type(
    "RouteRegistry",
    (),
    {
        "register": staticmethod(register_action),
        "get": staticmethod(get_action),
        "all": staticmethod(get_all_actions),
        "register_router": staticmethod(register_router),
        "get_router": staticmethod(get_router),
        "register_service": staticmethod(register_service),
        "get_service": staticmethod(get_service),
        "register_builtin_actions": staticmethod(register_builtin_actions),
        "_reset_for_tests": staticmethod(_reset_for_tests),
    },
)