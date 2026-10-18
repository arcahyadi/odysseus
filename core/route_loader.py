# core/route_loader.py
"""Dynamic route discovery and registration for FastAPI.

Uses pkgutil.iter_modules to auto-discover all route modules in routes/,
eliminating the need for static imports. Adding a new route file requires
zero edits to this file.
"""

import importlib
import logging
import pkgutil
import sys
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _discover_route_modules() -> list[str]:
    """Discover all route modules in the routes/ package.
    
    Returns sorted list of module names (e.g. 'routes.auth_routes').
    """
    # routes/ is at project root, two levels up from core/route_loader.py
    routes_path = Path(__file__).parent.parent / "routes"
    modules = []
    
    for finder, name, is_pkg in pkgutil.iter_modules([str(routes_path)]):
        if not is_pkg and name.endswith("_routes"):
            modules.append(f"routes.{name}")
    
    return sorted(modules)


def _load_route_module(module_name: str):
    """Safely import a route module and return its setup function."""
    try:
        module = importlib.import_module(module_name)
        # Convention: setup function is named setup_<name>_routes
        # e.g., routes.auth_routes -> setup_auth_routes
        name = module_name.replace("routes.", "").replace("_routes", "")
        setup_name = f"setup_{name}_routes"
        if hasattr(sys.modules[module_name], f"setup_{name}_routes"):
            return getattr(sys.modules[module_name], f"setup_{name}_routes")
        # Fallback: look for any setup_*_routes function
        for attr in dir(sys.modules[module_name]):
            if attr.startswith("setup_") and attr.endswith("_routes"):
                return getattr(sys.modules[module_name], attr)
        logger.warning(f"No setup_*_routes found in {module_name}")
        return None
    except Exception as e:
        logger.error(f"Failed to load {module_name}: {e}")
        return None


def register_all_routes(app: "FastAPI") -> None:
    """Mount every discovered API router onto *app*.
    
    Auto-discovers all routes.*_routes modules and calls their setup function.
    Adding a new routes/*_routes.py file requires ZERO edits here.
    """
    logger.info("Starting dynamic route discovery...")
    
    modules = _discover_route_modules()
    logger.info(f"Discovered {len(modules)} route modules: {modules}")
    
    loaded = 0
    failed = 0
    
    for module_name in modules:
        setup_fn = _load_route_module(module_name)
        if setup_fn is None:
            logger.warning(f"Skipping {module_name}: no setup function found")
            failed += 1
            continue
        
        try:
            # Call setup function with app.state (injected by FastAPI)
            router = setup_fn()
            if hasattr(router, "routes"):
                # It's a router - include it
                app.include_router(router)
                logger.debug(f"Mounted router from {module_name}")
            else:
                # Could be a tuple (router, cleanup) or just a router
                if isinstance(setup_fn, tuple):
                    for item in setup_fn:
                        if hasattr(item, "routes"):
                            app.include_router(item)
                else:
                    logger.warning(f"Setup function in {module_name} didn't return a router")
            loaded += 1
        except Exception as e:
            logger.error(f"Failed to mount routes from {module_name}: {e}")
            failed += 1
    
    logger.info(f"Route loading complete: {loaded} loaded, {failed} failed")


# Legacy compatibility - for tests that expect the old signature
def _legacy_register_all_routes(app):
    """Legacy wrapper - logs warning and delegates to new dynamic loader."""
    import warnings
    warnings.warn(
        "Legacy register_all_routes called - use dynamic discovery instead",
        DeprecationWarning,
        stacklevel=2
    )
    # Import the new implementation
    from core.route_loader import register_all_routes as new_register
    return new_register(app)