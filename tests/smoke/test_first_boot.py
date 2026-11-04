"""First-boot smoke test — spins the full FastAPI app up against a fresh
temp `data/` directory and hits the liveness, readiness and static-asset
endpoints. Catches the classic "fresh install won't start" regressions the
unit suite can't see: an import that quietly fails on a clean worktree, a
startup hook that assumes `data/` already exists, a route that 500s before
auth, a static bundle that no longer registers.

Deliberately runs the app import in a subprocess so pytest's shared
interpreter (which has already imported fastapi/uvicorn, plus the conftest's
in-memory DATABASE_URL default) can't mask a real first-install failure.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HAS_NODE = shutil.which("node") is not None

_BOOTSTRAP = textwrap.dedent(f"""
    import asyncio, json, os, sys
    sys.path.insert(0, {str(_REPO)!r})
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Fresh-install env: empty data dir, local SQLite, no auth so the routes
    # we probe are actually reachable, no CSP nonce dependency on session.
    from starlette.testclient import TestClient
    import app as appmod

    result = {{"routes": [], "checks": {{}}}}

    with TestClient(appmod.app, raise_server_exceptions=False) as client:
        for path in ("/api/health", "/api/version", "/api/ready", "/", "/login"):
            r = client.get(path)
            result["checks"][path] = {{
                "status": r.status_code,
                "content_type": (r.headers.get("content-type") or "").split(";")[0],
            }}

        # Static shell + a couple of critical JS modules must be served. The
        # SW/JS entrypoints are what makes or breaks a real first load, and
        # route-mounting bugs (wrong StaticFiles path, MIME drift on Windows)
        # only surface here.
        for asset in (
            "/static/index.html",
            "/static/app.js",
            "/static/js/cookbook.js",
            "/static/sw.js",
        ):
            r = client.get(asset)
            result["checks"][asset] = {{
                "status": r.status_code,
                "content_type": (r.headers.get("content-type") or "").split(";")[0],
                "size": len(r.content),
            }}

        # Report the app's version too — proves core.constants imported and
        # the version route's dependency wiring survived a fresh bootstrap.
        v = client.get("/api/version")
        if v.status_code == 200:
            result["version"] = (v.json() or {{}}).get("version")

    print(json.dumps(result))
""")


def _run_bootstrap(tmp_path: Path) -> dict:
    """Execute the child bootstrap with a pristine env. Any unhandled startup
    exception is treated as a first-boot failure and surfaces verbatim."""
    env = os.environ.copy()
    env["ODYSSEUS_DATA_DIR"] = str(tmp_path)
    env["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    env["AUTH_ENABLED"] = "false"
    env["LOCALHOST_BYPASS"] = "true"
    env["SECURE_COOKIES"] = "false"
    # Don't leak the developer's real .env into a fresh-install simulation.
    env.pop("ODYSSEUS_INTERNAL_TOKEN", None)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(_REPO), env=env, timeout=180,
    )
    if proc.returncode != 0:
        # Show the child's stderr so a first-boot crash reads as a real
        # failure in the CI log rather than an opaque non-zero exit.
        pytest.fail(
            "First-boot subprocess failed:\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
    stdout = proc.stdout.strip().splitlines()
    payload_line = next(
        (line for line in reversed(stdout) if line.startswith("{") and line.endswith("}")),
        None,
    )
    if not payload_line:
        pytest.fail(f"No JSON payload from bootstrap. stdout={proc.stdout!r}")
    return json.loads(payload_line)


def test_first_boot_starts_and_serves_core_endpoints(tmp_path):
    """Sut tree: a fresh clone with an empty data dir must come up clean and
    answer the endpoints the login flow depends on."""
    result = _run_bootstrap(tmp_path)
    checks = result["checks"]

    assert checks["/api/health"]["status"] == 200, checks["/api/health"]
    assert checks["/api/version"]["status"] == 200, checks["/api/version"]
    assert result.get("version"), "version payload missing on first boot"

    # Readiness must be 200 on a clean install — DB and data dir are the two
    # things this repo is famous for failing on a fresh tree.
    assert checks["/api/ready"]["status"] == 200, checks["/api/ready"]

    # Shell HTML and login page render.
    assert checks["/"]["status"] in (200, 307, 302), checks["/"]
    assert checks["/login"]["status"] in (200, 302, 307), checks["/login"]


def test_first_boot_serves_static_shell_assets(tmp_path):
    """The SW-precache entrypoints have to be reachable on a fresh install
    with the correct JS/HTML MIME types. Windows registry MIME drift and
    StaticFiles path regressions both show up here first."""
    result = _run_bootstrap(tmp_path)
    checks = result["checks"]
    for asset in (
        "/static/index.html",
        "/static/app.js",
        "/static/js/cookbook.js",
        "/static/sw.js",
    ):
        info = checks[asset]
        assert info["status"] == 200, f"{asset}: {info}"
        assert info["size"] > 0, f"{asset}: empty body"
        if asset.endswith(".js"):
            assert "javascript" in info["content_type"], (
                f"{asset} served with wrong MIME type: {info['content_type']} — "
                "browsers refuse to load ES modules that aren't JavaScript."
            )
        if asset.endswith(".html"):
            assert "html" in info["content_type"], (
                f"{asset} served with wrong MIME type: {info['content_type']}"
            )


def test_first_boot_writes_only_into_its_data_dir(tmp_path):
    """Startup must not create files outside the caller-provided DATA_DIR.
    A leak here (repo-root `data/`, cwd-relative auth.json, etc.) breaks
    containerised and multi-tenant deploys silently."""
    outside_before = {p.name for p in _REPO.iterdir() if p.is_file()}
    _run_bootstrap(tmp_path)
    outside_after = {p.name for p in _REPO.iterdir() if p.is_file()}
    leaked = outside_after - outside_before
    assert not leaked, f"first-boot wrote unexpected files into repo root: {sorted(leaked)}"

    # And the tmp data dir should have *something* in it — proves the app is
    # actually honouring ODYSSEUS_DATA_DIR rather than ignoring it.
    assert any(tmp_path.iterdir()), (
        f"DATA_DIR {tmp_path} empty after first boot — app wrote nothing "
        "into the caller-supplied directory."
    )
