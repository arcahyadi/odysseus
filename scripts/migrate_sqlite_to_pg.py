#!/usr/bin/env python3
"""Migrate data from the Odysseus SQLite database to PostgreSQL (pgvector).

Usage:
    # With a running PostgreSQL container:
    DATABASE_URL=postgresql+asyncpg://odysseus:odysseus@localhost:5432/odysseus \
        python scripts/migrate_sqlite_to_pg.py

    # Custom SQLite source (defaults to ./data/app.db):
    python scripts/migrate_sqlite_to_pg.py --sqlite ./data/app.db

The script:
    1. Connects to the SQLite database and reads all tables.
    2. Connects to PostgreSQL and enables the pgvector extension.
    3. Creates all Odysseus tables via SQLAlchemy metadata (reuses core.database models).
    4. Copies every row from SQLite → PostgreSQL in batch.
    5. Verifies row counts match.

Safety:
    - Idempotent on re-run (uses INSERT ... ON CONFLICT DO NOTHING where applicable).
    - Dry-run mode: pass --dry-run to preview without writing.
    - Atomic per table (each table copy is its own transaction).
"""

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `core` and `src` are importable.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _parse_pg_url(url: str):
    """Return (host, port, dbname, user, password) from a SQLAlchemy-style PG URL."""
    parsed = urlparse(url)
    return (
        parsed.hostname or "localhost",
        parsed.port or 5432,
        (parsed.path or "/odysseus").lstrip("/"),
        parsed.username or "odysseus",
        parsed.password or "odysseus",
    )


def _table_columns(cursor, table: str) -> list[str]:
    """Return column names for a SQLite table via PRAGMA."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _table_rows(cursor, table: str) -> list[tuple]:
    cursor.execute(f"SELECT * FROM [{table}]")
    return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument(
        "--sqlite",
        default=None,
        help="Path to SQLite database (default: auto-detect from DATABASE_URL env or ./data/app.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing to PostgreSQL",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Resolve SQLite path
    # ------------------------------------------------------------------
    if args.sqlite:
        sqlite_path = args.sqlite
    else:
        env_url = os.getenv("DATABASE_URL", "")
        if env_url.startswith("sqlite:///"):
            sqlite_path = env_url.replace("sqlite:///", "", 1)
        else:
            sqlite_path = str(Path(_PROJECT_ROOT) / "data" / "app.db")

    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    print(f"Source SQLite: {sqlite_path}")

    # ------------------------------------------------------------------
    # 2. Resolve PostgreSQL URL
    # ------------------------------------------------------------------
    pg_url = os.getenv("DATABASE_URL", "")
    if not pg_url.startswith("postgresql"):
        # Try the explicit POSTGRES_URL env var
        pg_url = os.getenv("POSTGRES_URL", "")
    if not pg_url.startswith("postgresql"):
        print("ERROR: Set DATABASE_URL or POSTGRES_URL to a PostgreSQL connection string.")
        print("  Example: postgresql://odysseus:odysseus@localhost:5432/odysseus")
        sys.exit(1)

    host, port, dbname, user, password = _parse_pg_url(pg_url)
    print(f"Target PostgreSQL: {user}@{host}:{port}/{dbname}")

    # ------------------------------------------------------------------
    # 3. Connect to both databases
    # ------------------------------------------------------------------
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 is required.  pip install psycopg2-binary")
        sys.exit(1)

    pg_conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
    pg_conn.autocommit = False

    # ------------------------------------------------------------------
    # 4. Enable pgvector extension
    # ------------------------------------------------------------------
    with pg_conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        pg_conn.commit()
        print("  ✓ pgvector extension enabled")

    # ------------------------------------------------------------------
    # 5. Create tables via SQLAlchemy (reuses core.database.Base)
    # ------------------------------------------------------------------
    # Point DATABASE_URL to the PG target so engine binds correctly
    os.environ["DATABASE_URL"] = pg_url
    from core.database import Base  # noqa: E402
    from core.database import engine as sa_engine

    # We'll use raw psycopg2 for bulk inserts (faster than ORM).
    # But we need the DDL from SQLAlchemy, so create_all on the PG engine.
    if not args.dry_run:
        # create_engine binds to the PG URL now
        Base.metadata.create_all(bind=sa_engine)
        print("  ✓ Tables created via SQLAlchemy metadata")
    else:
        print("  [dry-run] Would create tables via SQLAlchemy metadata")

    # ------------------------------------------------------------------
    # 6. Enumerate tables present in both databases
    # ------------------------------------------------------------------
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'chat_messages_fts%'"
    )
    sqlite_tables = [row[0] for row in sqlite_cursor.fetchall()]

    with pg_conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        pg_tables = {row[0] for row in cur.fetchall()}

    tables_to_migrate = [t for t in sqlite_tables if t in pg_tables]
    tables_to_migrate.sort()

    if not tables_to_migrate:
        print("No overlapping tables found between SQLite and PostgreSQL.")
        sys.exit(1)

    print(f"\nTables to migrate ({len(tables_to_migrate)}):")
    for t in tables_to_migrate:
        count = sqlite_cursor.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        print(f"  {t}: {count} rows")

    # ------------------------------------------------------------------
    # 7. Copy data — table by table
    # ------------------------------------------------------------------
    total_rows = 0
    total_errors = 0
    t_start = time.time()

    for table in tables_to_migrate:
        cols = _table_columns(sqlite_cursor, table)
        rows = _table_rows(sqlite_cursor, table)

        if not rows:
            print(f"  {table}: 0 rows, skipping")
            continue

        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(f'"{c}"' for c in cols)
        insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

        if args.dry_run:
            print(f"  [dry-run] {table}: would INSERT {len(rows)} rows")
            total_rows += len(rows)
            continue

        try:
            with pg_conn.cursor() as cur:
                # Use executemany for batch insert
                # Convert sqlite3.Row to plain tuples
                plain_rows = [tuple(row) for row in rows]
                cur.executemany(insert_sql, plain_rows)
            pg_conn.commit()
            total_rows += len(rows)
            print(f"  ✓ {table}: {len(rows)} rows migrated")
        except Exception as e:
            pg_conn.rollback()
            total_errors += 1
            print(f"  ✗ {table}: FAILED — {e}")

    elapsed = time.time() - t_start

    # ------------------------------------------------------------------
    # 8. Verify row counts
    # ------------------------------------------------------------------
    if not args.dry_run:
        print("\nVerification:")
        verify_ok = True
        with pg_conn.cursor() as cur:
            for table in tables_to_migrate:
                sqlite_count = sqlite_cursor.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                pg_count = cur.fetchone()[0]
                status = "✓" if pg_count == sqlite_count else "✗"
                if pg_count != sqlite_count:
                    verify_ok = False
                print(f"  {status} {table}: SQLite={sqlite_count}, PG={pg_count}")

        if verify_ok:
            print("\n✅ All row counts match!")
        else:
            print("\n⚠️  Some row counts differ — review above.")

    # ------------------------------------------------------------------
    # 9. Summary
    # ------------------------------------------------------------------
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Migration complete:")
    print(f"  Tables: {len(tables_to_migrate)}")
    print(f"  Rows:   {total_rows}")
    print(f"  Errors: {total_errors}")
    print(f"  Time:   {elapsed:.1f}s")

    sqlite_conn.close()
    pg_conn.close()

    sys.exit(1 if total_errors else 0)


if __name__ == "__main__":
    main()
