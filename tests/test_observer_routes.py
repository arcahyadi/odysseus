"""Contract test for the read-only drift panel route.

GET /api/observer/drift must return the honest Observer.get_summary()
projection: real drift level, never a fabricated value.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.observer_routes import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_drift_endpoint_contract():
    resp = _client().get("/api/observer/drift")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["drift_level"] in {"low", "medium", "high"}
    for key in (
        "harness_touched",
        "runs_tracked",
        "latest_codeburn_one_shot_rate",
        "recommendation",
    ):
        assert key in body


def test_drift_endpoint_types():
    body = _client().get("/api/observer/drift").json()
    assert isinstance(body["harness_touched"], bool)
    assert isinstance(body["runs_tracked"], int)
    assert isinstance(body["recommendation"], str)
    # latest one-shot rate is a float when a codeburn report exists, else None
    assert body["latest_codeburn_one_shot_rate"] is None or isinstance(
        body["latest_codeburn_one_shot_rate"], (int, float)
    )
