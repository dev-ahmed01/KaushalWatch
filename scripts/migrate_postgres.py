"""Explicit versioned schema migration for protected PostgreSQL persistence.

Run `python scripts/migrate_postgres.py --apply` with a migration-scoped
database credential. Never run during app startup or against unknown data.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "backend" / "sql" / "0001_initial.sql"
VERSION = 1


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dsn = os.getenv("KAUSHALWATCH_DATABASE_URL", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        parser.error("KAUSHALWATCH_DATABASE_URL must be a PostgreSQL DSN")

    with psycopg.connect(dsn, connect_timeout=5) as db:
        if args.check:
            exists = db.execute("SELECT to_regclass('kw_schema_migrations')").fetchone()[0]
            installed = (db.execute(
                "SELECT version FROM kw_schema_migrations WHERE version = %s", (VERSION,)
            ).fetchone() if exists else None)
            if not installed:
                parser.error("PostgreSQL v1 schema migration has not been applied")
            for name in ("kw_cases", "kw_analysis_history", "kw_edge_events",
                         "kw_centre_settings"):
                if db.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0] is None:
                    parser.error("Missing PostgreSQL table: " + name)
            print("PostgreSQL v1 schema verified.")
            return

        # Single migration owner across processes. Idempotent if repeated.
        db.execute("SELECT pg_advisory_xact_lock(%s)", (82630093,))
        db.execute(DDL.read_text(encoding="utf-8"))
        db.execute(
            "INSERT INTO kw_schema_migrations(version) VALUES (%s) "
            "ON CONFLICT (version) DO NOTHING", (VERSION,)
        )
    print("PostgreSQL v1 schema applied.")


if __name__ == "__main__":
    main()
