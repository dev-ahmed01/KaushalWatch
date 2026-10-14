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
MIGRATIONS = (
    (1, ROOT / "backend" / "sql" / "0001_initial.sql"),
    (2, ROOT / "backend" / "sql" / "0002_private_evidence.sql"),
)


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
            if not exists:
                parser.error("PostgreSQL schema migration table is absent")
            applied = {row[0] for row in db.execute(
                "SELECT version FROM kw_schema_migrations").fetchall()}
            required = {version for version, _ in MIGRATIONS}
            if not required.issubset(applied):
                parser.error("PostgreSQL schema migration incomplete: "
                             + repr(sorted(required - applied)))
            for name in ("kw_cases", "kw_analysis_history", "kw_edge_events",
                         "kw_centre_settings", "kw_evidence_objects"):
                if db.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0] is None:
                    parser.error("Missing PostgreSQL table: " + name)
            print("PostgreSQL v2 schema verified.")
            return

        # All steps in a single transaction: partial schema migrations abort.
        # Never run implicit schema mutation during web/API server startup.
        db.execute("SELECT pg_advisory_xact_lock(%s)", (82630093,))
        db.execute(MIGRATIONS[0][1].read_text(encoding="utf-8"))
        for version, path in MIGRATIONS:
            found = db.execute(
                "SELECT 1 FROM kw_schema_migrations WHERE version = %s", (version,)
            ).fetchone()
            if not found:
                if version != 1:
                    db.execute(path.read_text(encoding="utf-8"))
                db.execute(
                    "INSERT INTO kw_schema_migrations(version) VALUES (%s)", (version,)
                )
    print("PostgreSQL v2 schema applied.")


if __name__ == "__main__":
    main()
