"""Isolated CI backup/restore drill using native PostgreSQL dump utilities.

Never run against deployed or shared databases. The guard requires an explicit
marker, exact disposable database name and a local PostgreSQL server; refuses
any other target BEFORE creating a database or invoking pg_dump.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import CaseStatus, ComplianceCase
from app.services.postgres_store import PostgresCaseStore

TABLES = (
    "kw_cases", "kw_analysis_history", "kw_centre_settings",
    "kw_edge_events", "kw_evidence_objects", "kw_schema_migrations",
)


def _allowed() -> tuple[dict, str]:
    if os.environ.get("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci":
        raise RuntimeError("Backup drill requires an explicit isolated_ci marker")
    values = conninfo_to_dict(os.environ.get("KAUSHALWATCH_DATABASE_URL", ""))
    if (values.get("dbname") != "kaushalwatch_ci"
            or values.get("host") not in {"127.0.0.1", "localhost"}
            or str(values.get("port", "5432")) != "5432"):
        raise RuntimeError("Refusing backup drill outside local disposable kaushalwatch_ci")
    for tool in ("pg_dump", "pg_restore"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} client is missing; install PostgreSQL client tools")
    env = dict(os.environ)
    env.update({
        "PGHOST": values["host"], "PGPORT": str(values.get("port", 5432)),
        "PGUSER": values.get("user", ""), "PGPASSWORD": values.get("password", ""),
    })
    # User/name/password must stay in environment, not in subprocess argv/logs.
    return env, os.environ["KAUSHALWATCH_DATABASE_URL"]


def snapshot(connection: psycopg.Connection) -> dict:
    state = {}
    for table in TABLES:
        # These are hardcoded table identifiers, not user-controlled SQL.
        rows = connection.execute(
            sql.SQL("SELECT row_to_json(t) AS payload FROM {} AS t").format(
                sql.Identifier(table)
            )
        ).fetchall()
        canonical = sorted(
            json.dumps(row[0], sort_keys=True, default=str) for row in rows
        )
        encoded = json.dumps(canonical, separators=(",", ":"))
        state[table] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        }
    return state


def drill() -> dict:
    env, source_url = _allowed()
    source = conninfo_to_dict(source_url)
    # Only the temporary CI role and the disposable restore DB are used.
    maintenance = dict(source, dbname="postgres")
    name = "kw_restore_ci_" + uuid.uuid4().hex[:12]

    PostgresCaseStore().save_if_absent(ComplianceCase(
        case_id="KW-RESTORE-SENTINEL", centre_id="DEMO-KA-104",
        batch_id="KW-RESTORE-SENTINEL", case_type="attendance_discrepancy",
        severity="medium", summary="Synthetic isolated restore verification",
    ))
    existing = PostgresCaseStore().get("KW-RESTORE-SENTINEL")
    if existing.status == CaseStatus.open:
        PostgresCaseStore().apply_review_action(
            "KW-RESTORE-SENTINEL", CaseStatus.confirmed,
            note="Synthetic restore audit verification", actor="ci-restore-officer",
        )
    with psycopg.connect(source_url) as conn:
        expected = snapshot(conn)
        case = conn.execute(
            "SELECT payload FROM kw_cases WHERE case_id = %s",
            ("KW-RESTORE-SENTINEL",),
        ).fetchone()[0]
        if case["status"] != "confirmed" or not case["review_history"]:
            raise RuntimeError("Source audit sentinel was not written")

    created = False
    try:
        with psycopg.connect(**maintenance, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        created = True
        with tempfile.TemporaryDirectory(prefix="kw-ci-pg-restore-") as folder:
            archive = Path(folder) / "db.dump"
            dump_env = dict(env, PGDATABASE="kaushalwatch_ci")
            restore_env = dict(env, PGDATABASE=name)
            subprocess.run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-acl",
                 "--file", str(archive)],
                env=dump_env, check=True, timeout=90, capture_output=True,
            )
            if not archive.is_file() or archive.stat().st_size == 0:
                raise RuntimeError("PostgreSQL backup archive is empty")
            subprocess.run(
                ["pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
                 "--dbname", name, str(archive)],
                env=restore_env, check=True, timeout=90, capture_output=True,
            )
        with psycopg.connect(**dict(source, dbname=name)) as restore:
            actual = snapshot(restore)
            row = restore.execute(
                "SELECT payload FROM kw_cases WHERE case_id=%s",
                ("KW-RESTORE-SENTINEL",),
            ).fetchone()[0]
            if row["status"] != "confirmed" or not row["review_history"]:
                raise RuntimeError("Restored officer audit history is missing")
        if actual != expected:
            raise RuntimeError("Restored database snapshot differs from backup source")
        return {
            "status": "passed_isolated_ci_restore",
            "tables_verified": len(TABLES),
            "officer_review_history_restored": True,
            "case_rows": actual["kw_cases"]["rows"],
            "evidence_metadata_rows": actual["kw_evidence_objects"]["rows"],
            "scope": "postgres_structured_data_only",
            "note": "No S3 object contents, IAM/KMS, or real disaster recovery tested.",
        }
    finally:
        if created:
            with psycopg.connect(**maintenance, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
                )


def main() -> None:
    report = drill()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
