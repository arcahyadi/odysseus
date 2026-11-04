"""Route ordering for the memory router.

``GET /api/memory/{memory_id}`` is a wildcard, and FastAPI matches routes in
registration order. Any fixed path registered *after* it is therefore
unreachable: the wildcard swallows the request and looks up a memory whose id is
the literal path segment, then 404s with "Memory not found".

That is exactly what happened to ``GET /api/memory/time-range`` (Phase 2
Req 2.5/2.6) - declared below the wildcard, so it could never run. These tests
pin the invariant so it cannot regress.
"""
from unittest.mock import MagicMock

import routes.memory_routes as mr


def _router():
    mem = MagicMock()
    mem.load = lambda owner=None: []
    sm = MagicMock()
    return mr.setup_memory_routes(mem, sm)


def _paths(router):
    return [r.path for r in router.routes if hasattr(r, "path")]


def _get_endpoint(router, path):
    for r in router.routes:
        if r.path == path and "GET" in getattr(r, "methods", set()):
            return r.endpoint
    raise AssertionError(f"no GET route for {path}")


def _request():
    state = type("State", (), {"current_user": "alice"})()
    return type("Request", (), {"state": state, "app": type("App", (), {"state": type("AppState", (), {"auth_manager": None})()})()})()


def test_fixed_get_paths_are_registered_before_the_wildcard():
    paths = _paths(_router())
    wildcard = paths.index("/api/memory/{memory_id}")

    # Every fixed GET path must sit ahead of the wildcard, or it is dead code.
    for fixed in ("/api/memory/time-range",):
        assert paths.index(fixed) < wildcard, (
            f"{fixed} is registered after /api/memory/{{memory_id}} and would be "
            "shadowed by it (FastAPI matches in registration order)"
        )


def test_time_range_returns_the_range_shape_not_the_wildcard_shape(monkeypatch):
    """The route must yield {entries, count}, not the wildcard's single item."""
    router = _router()
    monkeypatch.setattr(mr, "get_current_user", lambda request: "alice", raising=False)

    result = _get_endpoint(router, "/api/memory/time-range")(_request())

    assert set(result) == {"entries", "count"}
    assert isinstance(result["entries"], list)


def test_promote_is_registered_before_any_wildcard():
    """No POST wildcard exists today, but keep the fixed paths grouped ahead of
    the wildcard block so adding one later cannot silently shadow /promote."""
    paths = _paths(_router())
    assert paths.index("/api/memory/promote") < paths.index("/api/memory/{memory_id}")
