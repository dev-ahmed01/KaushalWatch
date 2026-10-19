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
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import CaseStatus, ComplianceCase
from app.services.postgres_store import PostgresCaseStore
from app.services.dependency_readiness import REQUIRED_TABLES, REQUIRED_MIGRATIONS
from app.services.camera_trust_store import _json_hash

# Follow the same ten v3 data tables as /api/ready and include the migration
# ledger. Omitting Camera Trust tables would produce false-positive CI restores.
TABLES = (*REQUIRED_TABLES, "kw_schema_migrations")


def _allowed() -> tuple[dict, str]:
    if os.environ.get("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci":
        raise RuntimeError("Backup drill requires an explicit isolated_ci marker")
    # A local hostname is not sufficient when libpq also accepts hostaddr,
    # service-file or ambient PGHOSTADDR overrides that route to remote hosts.
    # Reject them before ANY connection, dump, restore or database creation.
    if os.environ.get("KAUSHALWATCH_ENV", "").lower() in {"pilot", "prod", "production"}:
        raise RuntimeError("Refusing backup drill in a protected environment")
    if any(os.environ.get(name) for name in
           ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE")):
        raise RuntimeError("Refusing backup drill with libpq target overrides")
    try:
        values = conninfo_to_dict(os.environ.get("KAUSHALWATCH_DATABASE_URL", ""))
    except psycopg.Error:
        raise RuntimeError("Invalid isolated CI database configuration") from None
    if (values.get("dbname") != "kaushalwatch_ci"
            or values.get("host") not in {"127.0.0.1", "localhost"}
            or str(values.get("port", "5432")) != "5432"
            or any(values.get(name) for name in ("hostaddr", "service", "servicefile"))):
        raise RuntimeError("Refusing backup drill outside local disposable kaushalwatch_ci")
    if set(REQUIRED_MIGRATIONS) != {1, 2, 3} or len(set(TABLES)) != len(TABLES):
        raise RuntimeError("Recovery drill schema contract needs review")
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



def seed_synthetic_camera() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Populate each Camera Trust v3 table only in the disposable CI database.

    All IDs and source hashes are synthetic, never real camera references.
    The v3 immutable audit uses the same canonical hash function as the
    application; the restore check independently revalidates the chain.
    """
    camera, reference, job, observation = (uuid.uuid4() for _ in range(4))
    source_hash, reference_hash = "a" * 64, "b" * 64
    with psycopg.connect(os.environ["KAUSHALWATCH_DATABASE_URL"]) as db:
        db.execute(
            """INSERT INTO kw_camera_registry
               (camera_id, centre_id, label, source_alias, created_by)
               VALUES (%s,%s,%s,%s,%s)""",
            (camera, "DEMO-KA-104", "CI disposable restore sentinel",
             "synthetic-ci-restore-only", "ci-synthetic-officer"),
        )
        db.execute(
            """INSERT INTO kw_camera_references
               (reference_id,camera_id,sha256,captured_at,note,proposed_by,
                approved_by,approved_at,status)
               VALUES (%s,%s,%s,NOW(),%s,%s,%s,NOW(),'approved')""",
            (reference, camera, reference_hash, "Synthetic-only CI approval",
             "ci-synthetic-proposer", "ci-synthetic-independent-approver"),
        )
        db.execute(
            """INSERT INTO kw_camera_jobs
               (job_id,camera_id,source_alias,source_sha256,idempotency_key,
                status,attempts,sample_limit,created_by)
               VALUES (%s,%s,%s,%s,%s,'succeeded',1,12,%s)""",
            (job, camera, "synthetic-ci-restore-only", source_hash,
             "ci-synthetic-" + str(job), "ci-synthetic-officer"),
        )
        db.execute(
            """INSERT INTO kw_camera_observations
               (observation_id,camera_id,job_id,source_sha256,reference_id,
                payload,review_status,reviewer,review_note,reviewed_at)
               VALUES (%s,%s,%s,%s,%s,%s,'needs_followup',%s,%s,NOW())""",
            (observation, camera, job, source_hash, reference,
             Jsonb({"physical_camera_health": "UNKNOWN",
                    "production_qualified": False,
                    "auto_incident_mutations": 0,
                    "synthetic_disposable_restore": True}),
             "ci-synthetic-independent-reviewer",
             "Physical field verification required"),
        )
        previous = "0" * 64
        for sequence, event, payload in (
            (1, "camera_registered", {"synthetic_disposable_restore": True}),
            (2, "observation_reviewed", {"review_status": "needs_followup"}),
        ):
            actor = "ci-synthetic-independent-reviewer"
            digest = _json_hash({
                "camera_id": str(camera), "sequence": sequence, "actor": actor,
                "event": event, "payload": payload, "previous_sha256": previous,
            })
            db.execute(
                """INSERT INTO kw_camera_audit
                   (event_id,camera_id,sequence,actor,event,payload,
                    previous_sha256,event_sha256)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uuid.uuid4(), camera, sequence, actor, event,
                 Jsonb(payload), previous, digest),
            )
            previous = digest
    return camera, reference, job, observation


def verify_camera_sentinel(
    db: psycopg.Connection,
    ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
) -> bool:
    """Verify the same structured Camera Trust state and audit hash chain."""
    camera, reference, job, observation = ids
    registry = db.execute(
        "SELECT centre_id,source_alias FROM kw_camera_registry WHERE camera_id=%s",
        (camera,),
    ).fetchone()
    approved = db.execute(
        "SELECT status,approved_by FROM kw_camera_references WHERE reference_id=%s AND camera_id=%s",
        (reference, camera),
    ).fetchone()
    job_row = db.execute(
        "SELECT status,attempts FROM kw_camera_jobs WHERE job_id=%s AND camera_id=%s",
        (job, camera),
    ).fetchone()
    observed = db.execute(
        """SELECT review_status,reviewer,payload FROM kw_camera_observations
           WHERE observation_id=%s AND camera_id=%s AND job_id=%s AND reference_id=%s""",
        (observation, camera, job, reference),
    ).fetchone()
    rows = db.execute(
        """SELECT sequence,actor,event,payload,previous_sha256,event_sha256
           FROM kw_camera_audit WHERE camera_id=%s ORDER BY sequence""",
        (camera,),
    ).fetchall()
    previous = "0" * 64
    if (registry != ("DEMO-KA-104", "synthetic-ci-restore-only")
            or approved != ("approved", "ci-synthetic-independent-approver")
            or job_row != ("succeeded", 1)
            or observed is None or observed[0] != "needs_followup"
            or observed[1] != "ci-synthetic-independent-reviewer"
            or not isinstance(observed[2], dict)
            or observed[2].get("physical_camera_health") != "UNKNOWN"
            or observed[2].get("production_qualified") is not False
            or observed[2].get("auto_incident_mutations") != 0
            or len(rows) != 2):
        return False
    for expected_sequence, (sequence, actor, event, payload,
                            prior_hash, event_hash) in enumerate(rows, 1):
        if sequence != expected_sequence or prior_hash != previous:
            return False
        expected = _json_hash({
            "camera_id": str(camera), "sequence": sequence,
            "actor": actor, "event": event, "payload": payload,
            "previous_sha256": previous,
        })
        if event_hash != expected:
            return False
        previous = event_hash
    # An immutable audit trigger is essential to a meaningful restore.
    trigger = db.execute(
        """SELECT EXISTS(
             SELECT 1 FROM pg_trigger t
             JOIN pg_class c ON c.oid = t.tgrelid
             WHERE c.relname = 'kw_camera_audit'
               AND t.tgname = 'kw_camera_audit_no_update'
               AND t.tgenabled != 'D' AND NOT t.tgisinternal)"""
    ).fetchone()
    return trigger is not None and trigger[0] is True


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
    camera_ids = seed_synthetic_camera()
    with psycopg.connect(source_url) as conn:
        if not verify_camera_sentinel(conn, camera_ids):
            raise RuntimeError("Source Camera Trust sentinel is not internally consistent")
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
            restored_camera_ok = verify_camera_sentinel(restore, camera_ids)
            row = restore.execute(
                "SELECT payload FROM kw_cases WHERE case_id=%s",
                ("KW-RESTORE-SENTINEL",),
            ).fetchone()[0]
            if row["status"] != "confirmed" or not row["review_history"]:
                raise RuntimeError("Restored officer audit history is missing")
        if actual != expected or not restored_camera_ok:
            raise RuntimeError("Restored database snapshot differs from backup source")
        return {
            "status": "passed_isolated_ci_restore",
            "tables_verified": len(TABLES),
            "officer_review_history_restored": True,
            "case_rows": actual["kw_cases"]["rows"],
            "evidence_metadata_rows": actual["kw_evidence_objects"]["rows"],
            "camera_registry_rows": actual["kw_camera_registry"]["rows"],
            "camera_jobs_rows": actual["kw_camera_jobs"]["rows"],
            "camera_observations_rows": actual["kw_camera_observations"]["rows"],
            "camera_audit_events": actual["kw_camera_audit"]["rows"],
            "camera_shadow_review_restored": restored_camera_ok,
            "camera_audit_hash_chain_restored": restored_camera_ok,
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
