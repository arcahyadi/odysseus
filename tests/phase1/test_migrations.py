"""
Integration tests for Phase 1 startup migrations.
Validates idempotency of run_phase1_migrations().
Requirements: 13.1
"""
import pytest
from sqlalchemy import create_engine, text

from core.phase1_migrations import run_phase1_migrations


def _get_columns(engine, table):
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {row[1] for row in rows}


def _make_engine_with_sessions():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE sessions ("
            "  id TEXT PRIMARY KEY, "
            "  name TEXT NOT NULL, "
            "  endpoint_url TEXT NOT NULL, "
            "  model TEXT NOT NULL"
            ")"
        ))
        conn.commit()
    return engine


def test_migrations_add_all_three_columns():
    engine = _make_engine_with_sessions()
    run_phase1_migrations(engine)
    cols = _get_columns(engine, "sessions")
    assert "forked_from_session_id" in cols
    assert "forked_from_message_id" in cols
    assert "active_persona_id" in cols


def test_migrations_idempotent_on_second_call():
    """Calling run_phase1_migrations twice must not raise."""
    engine = _make_engine_with_sessions()
    run_phase1_migrations(engine)
    run_phase1_migrations(engine)  # must not raise
    cols = _get_columns(engine, "sessions")
    assert "forked_from_session_id" in cols


def test_migrations_no_op_when_columns_already_exist():
    """No error when columns were added manually before migrations run."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE sessions ("
            "  id TEXT PRIMARY KEY, "
            "  name TEXT NOT NULL, "
            "  endpoint_url TEXT NOT NULL, "
            "  model TEXT NOT NULL, "
            "  forked_from_session_id TEXT, "
            "  forked_from_message_id TEXT, "
            "  active_persona_id TEXT"
            ")"
        ))
        conn.commit()
    run_phase1_migrations(engine)
    cols = _get_columns(engine, "sessions")
    assert "forked_from_session_id" in cols
    assert "active_persona_id" in cols


def test_migrations_idempotent_three_times():
    engine = _make_engine_with_sessions()
    for _ in range(3):
        run_phase1_migrations(engine)
    cols = _get_columns(engine, "sessions")
    assert len([c for c in cols if c in (
        "forked_from_session_id", "forked_from_message_id", "active_persona_id"
    )]) == 3
