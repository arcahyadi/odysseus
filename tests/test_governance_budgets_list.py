"""Contract test for the read-only budgets list route.

GET /api/governance/budgets enumerates every AgentBudget row. Read-only:
never mutates. Empty database is a valid (honest) response — an empty list.

A StaticPool in-memory engine is used so the schema created here survives
across connections (plain ``sqlite:///:memory:`` gives each connection its
own empty database). The route's ``SessionLocal`` is patched onto it.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routes.governance_routes as gov
from core.database import AgentBudget, Base

_EXPECTED_KEYS = {
    "agent_id",
    "run_id",
    "status",
    "tokens_used",
    "max_tokens",
    "cost_usd",
    "max_cost_usd",
    "iterations",
    "max_iterations",
    "paused_reason",
}


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(gov, "SessionLocal", TestingSession)
    app = FastAPI()
    app.include_router(gov.router)
    return TestClient(app), TestingSession


def test_budgets_list_empty_is_ok(env):
    client, _ = env
    resp = client.get("/api/governance/budgets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["budgets"] == []


def test_budgets_list_row_shape_when_present(env):
    client, TestingSession = env
    with TestingSession() as db:
        db.add(AgentBudget(agent_id="agent-1", run_id="run-1", status="active"))
        db.commit()
    body = client.get("/api/governance/budgets").json()
    assert body["ok"] is True
    assert len(body["budgets"]) == 1
    row = body["budgets"][0]
    assert _EXPECTED_KEYS.issubset(row.keys())
    assert row["agent_id"] == "agent-1"
    assert row["status"] == "active"
