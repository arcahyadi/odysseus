from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.killswitch_routes import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_killswitches_ok():
    resp = _client().get("/api/killswitches")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["switches"], list) and body["switches"]
    assert "Orchestration" in body["categories"]
    first = body["switches"][0]
    assert {"env_var", "effective", "is_default", "category"}.issubset(first)
