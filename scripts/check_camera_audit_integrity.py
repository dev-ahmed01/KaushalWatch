"""Read-only Camera Trust audit chain integrity for an approved pilot database.

Inspects structured PostgreSQL audit metadata only. No camera IDs, centre IDs,
raw payloads or source hashes are emitted. A hash-chain PASS is not an
independent anti-tamper attestation: a privileged DB actor could rewrite a
whole chain. Real custody and signed field truth remain external.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.camera_trust_store import _json_hash
from app.services.postgres_transport import (
    postgres_tls_configured, requires_verified_postgres_tls,
)

SCHEMA = "KW_CAMERA_AUDIT_INTEGRITY_V1"
BLOCKED = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
BATCH_SIZE = 256
# Bounded safety limit. Above this, request a reviewed pagination/retention
# policy rather than accidentally accepting a truncated audit.
MAX_EVENTS = 250_000


def _configured(env: dict[str, str]) -> bool:
    dsn = env.get("KAUSHALWATCH_DATABASE_URL", "")
    return (
        requires_verified_postgres_tls(env)
        and env.get("KAUSHALWATCH_STORAGE_BACKEND") == "postgres"
        and postgres_tls_configured(dsn)
    )


def _chain(rows: Iterator[dict[str, Any]], registered_cameras: int) -> dict[str, Any]:
    if not isinstance(registered_cameras, int) or registered_cameras <= 0:
        return {"valid": False, "events_checked": 0, "cameras_checked": 0}
    camera = None
    sequence = 0
    previous_hash = "0" * 64
    total = 0
    cameras = 0
    valid = True
    try:
        for row in rows:
            if total >= MAX_EVENTS or not isinstance(row, dict):
                valid = False
                break
            cid = str(row["camera_id"])
            if cid != camera:
                # SQL always orders by camera UUID and sequence; a repeated or
                # backwards camera group is a failed snapshot.
                if camera is not None and cid <= camera:
                    valid = False
                    break
                camera = cid
                cameras += 1
                sequence = 0
                previous_hash = "0" * 64
            seq = row["sequence"]
            payload = row["payload"]
            if (not isinstance(seq, int) or isinstance(seq, bool)
                    or seq != sequence + 1
                    or not isinstance(payload, dict)
                    or row["previous_sha256"] != previous_hash
                    or not isinstance(row["actor"], str)
                    or not isinstance(row["event"], str)
                    or not isinstance(row["event_sha256"], str)):
                valid = False
                break
            body = {
                "camera_id": cid, "sequence": seq, "actor": row["actor"],
                "event": row["event"], "payload": payload,
                "previous_sha256": previous_hash,
            }
            digest = _json_hash(body)
            if digest != row["event_sha256"]:
                valid = False
                break
            sequence = seq
            previous_hash = digest
            total += 1
    except (KeyError, ValueError, TypeError, OverflowError):
        valid = False
    return {
        "valid": bool(valid and total > 0 and cameras == registered_cameras),
        "events_checked": total, "cameras_checked": cameras,
    }


def _ordered_events(db) -> Iterator[dict[str, Any]]:
    """Keyset-page every audit row under one repeatable-read transaction."""
    last_camera = None
    last_seq = 0
    while True:
        if last_camera is None:
            rows = db.execute(
                """SELECT camera_id, sequence, actor, event, payload,
                          previous_sha256, event_sha256
                   FROM kw_camera_audit
                   ORDER BY camera_id, sequence LIMIT %s""",
                (BATCH_SIZE,),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT camera_id, sequence, actor, event, payload,
                          previous_sha256, event_sha256
                   FROM kw_camera_audit
                   WHERE (camera_id, sequence) > (%s, %s)
                   ORDER BY camera_id, sequence LIMIT %s""",
                (last_camera, last_seq, BATCH_SIZE),
            ).fetchall()
        if not rows:
            return
        for row in rows:
            yield row
        last_camera = rows[-1]["camera_id"]
        last_seq = rows[-1]["sequence"]


def scan_database(db) -> dict[str, Any]:
    """Run only SELECT queries inside a caller-held read-only DB snapshot."""
    registered = db.execute(
        "SELECT COUNT(*) AS count FROM kw_camera_registry"
    ).fetchone()["count"]
    missing = db.execute(
        """SELECT EXISTS (
             SELECT 1 FROM kw_camera_registry r
             WHERE NOT EXISTS (
               SELECT 1 FROM kw_camera_audit a
               WHERE a.camera_id = r.camera_id
             )
           ) AS missing"""
    ).fetchone()["missing"]

    trigger = db.execute(
        """SELECT t.tgenabled AS enabled,
                  pg_get_triggerdef(t.oid) AS definition,
                  pg_get_functiondef(t.tgfoid) AS function_definition
           FROM pg_trigger t
           JOIN pg_class c ON c.oid=t.tgrelid
           WHERE c.oid='kw_camera_audit'::regclass
             AND t.tgname='kw_camera_audit_no_update'
             AND NOT t.tgisinternal"""
    ).fetchone()
    ddl = trigger["definition"] if trigger else ""
    function_ddl = trigger["function_definition"] if trigger else ""
    immutable = bool(
        trigger and trigger["enabled"] in ("O", "A")
        and "BEFORE " in ddl and " UPDATE " in ddl and " DELETE " in ddl
        and "FOR EACH ROW" in ddl
        and "kw_camera_audit_immutable" in ddl
        and "RAISE EXCEPTION" in function_ddl
        and "Camera Trust audit events are immutable" in function_ddl
    )

    chain = _chain(_ordered_events(db), registered)
    return {
        "camera_registry_nonempty": bool(isinstance(registered, int) and registered > 0),
        "no_cameras_missing_audit": missing is False,
        "immutable_trigger_enabled": immutable,
        "full_audit_chain_valid": chain["valid"],
    }


def evaluate(env: dict[str, str], *, probe: bool = False,
             connection_factory=None) -> dict[str, Any]:
    configured = _configured(env)
    checks = {
        "protected_database_tls_configuration": "PASS" if configured else "BLOCKED",
        "camera_registry_nonempty": "NOT_PROBED",
        "no_cameras_missing_audit": "NOT_PROBED",
        "immutable_trigger_enabled": "NOT_PROBED",
        "full_audit_chain_valid": "NOT_PROBED",
    }
    attempted = False
    if probe and configured:
        try:
            connect = connection_factory or psycopg.connect
            with connect(env["KAUSHALWATCH_DATABASE_URL"], row_factory=dict_row,
                         connect_timeout=5) as db:
                # Must be the first SQL statement: all pages and counts see
                # a stable MVCC snapshot without locking officer writers.
                db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                attempted = True
                result = scan_database(db)
                for name, okay in result.items():
                    checks[name] = "PASS" if okay is True else "BLOCKED"
        except Exception:
            # psycopg errors can contain hostnames, DSNs or DB objects.
            # No exception details leave this process.
            for key in tuple(checks):
                if key != "protected_database_tls_configuration":
                    checks[key] = "BLOCKED"
    passed = probe and configured and all(v == "PASS" for v in checks.values())
    return {
        "schema": SCHEMA,
        "read_only_database_audit": "CHECKS_PASS" if passed else "BLOCKED",
        "database_snapshot_attempted": attempted,
        "checks": checks,
        "database_admin_resigning_the_chain_excluded": False,
        "independent_source_custody_verified": False,
        "physical_camera_accuracy_verified": False,
        "pilot_activation": BLOCKED,
        "autonomous_enforcement_authorized": False,
        "secrets_or_source_identifiers_emitted": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Non-exporting Camera Trust audit-chain check; no video access")
    options = p.add_mutually_exclusive_group(required=True)
    options.add_argument("--status", action="store_true")
    options.add_argument("--probe-database", action="store_true")
    args = p.parse_args()
    result = evaluate(dict(os.environ), probe=args.probe_database)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if args.status or result["read_only_database_audit"] == "CHECKS_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
