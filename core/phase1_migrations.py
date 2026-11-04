"""
core/phase1_migrations.py

Idempotent startup migrations for Phase 1 columns.

Adds the three new columns to the existing `sessions` table when they are
missing. Safe to call on every app startup — each ALTER TABLE is a no-op if
the column already exists.

Requirements: 13.1, 13.4
"""
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def run_phase1_migrations(engine):
    """Idempotent column additions on existing tables.

    Adds the Phase 1 session-forking and persona-binding columns to the
    `sessions` table. Each column addition is guarded by
    `_add_col_if_missing`, so calling this function multiple times is safe.
    """
    with engine.connect() as conn:
        _add_col_if_missing(conn, "sessions", "forked_from_session_id", "TEXT")
        _add_col_if_missing(conn, "sessions", "forked_from_message_id", "TEXT")
        _add_col_if_missing(conn, "sessions", "active_persona_id", "TEXT")
        conn.commit()


def _add_col_if_missing(conn, table, column, col_type):
    """Execute ALTER TABLE … ADD COLUMN, swallowing 'column already exists'.

    SQLite raises ``OperationalError: duplicate column name: <col>`` when an
    ADD COLUMN is issued for an already-present column. We catch all
    exceptions so the migration remains idempotent regardless of the
    underlying dialect.
    """
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        logger.info("Phase 1 migration: added column '%s' to table '%s'", column, table)
    except Exception:
        # Column already exists — this is expected on subsequent startups.
        pass
