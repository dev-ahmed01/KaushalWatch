"""Read-only, bounded audit of case-linked PostgreSQL and private S3 evidence.

This module intentionally has no delete, copy, restore, or ACL operations.
Its findings are advisory: an object may be in flight during an inventory,
and a legal hold or retention policy must govern any later remediation.
"""
from __future__ import annotations

import re

from app.services.object_evidence import _client, configuration
from app.services.postgres_store import connection

PREFIX = "evidence/v1/"
KEY_PATTERN = re.compile(r"^evidence/v1/([A-Za-z0-9_-]{2,128})/([A-Za-z0-9_-]{1,100})\.jpg$")
MAX_OBJECTS = 50_000


def audit_private_evidence(*, limit: int = MAX_OBJECTS) -> dict:
    if type(limit) is not int or not 1 <= limit <= MAX_OBJECTS:
        raise ValueError("Evidence audit object limit out of range")
    bucket, _, _ = configuration()

    with connection() as db:
        metadata = db.execute(
            "SELECT evidence_id, centre_id, object_key, sha256 "
            "FROM kw_evidence_objects ORDER BY evidence_id"
        ).fetchall()
        cases = db.execute(
            "SELECT centre_id, payload FROM kw_cases ORDER BY case_id"
        ).fetchall()

    records: dict[str, dict] = {}
    problems: set[str] = set()
    # The comparison must come from persisted cases, not mutable filename hints.
    for case in cases:
        payload = case["payload"]
        if not isinstance(payload, dict) or payload.get("centre_id") != case["centre_id"]:
            problems.add("case_payload_inconsistent")
            continue
        for item in payload.get("evidence", []):
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                problems.add("case_evidence_invalid")
                continue
            evid = item["evidence_id"]
            if evid in records:
                # One evidence ID in multiple cases is not safe to assume unique.
                problems.add("duplicate_case_evidence_reference")
                records[evid]["ambiguous"] = True
            else:
                records[evid] = {
                    "centre": case["centre_id"], "sha256": item.get("sha256"),
                    "ambiguous": False,
                }

    index = {item["evidence_id"]: item for item in metadata}
    if len(index) != len(metadata):
        problems.add("duplicate_evidence_metadata")
    object_keys: set[str] = set()
    orphan_objects = 0
    malformed_objects = 0
    indexed_without_case = 0
    missing_index = 0
    mismatched_records = 0
    missing_objects = 0
    client = _client()
    continuation: str | None = None
    scanned = 0
    while True:
        params = {"Bucket": bucket, "Prefix": PREFIX, "MaxKeys": 1000}
        if continuation:
            params["ContinuationToken"] = continuation
        response = client.list_objects_v2(**params)
        objects = response.get("Contents", [])
        if not isinstance(objects, list):
            raise RuntimeError("Invalid evidence object inventory page")
        for entry in objects:
            scanned += 1
            if scanned > limit:
                raise RuntimeError("Evidence object audit bound reached: incomplete inventory")
            key = entry.get("Key")
            if not isinstance(key, str) or key in object_keys:
                raise RuntimeError("Malformed or repeated S3 inventory key")
            object_keys.add(key)
            match = KEY_PATTERN.fullmatch(key)
            if not match:
                malformed_objects += 1
                continue
            centre, evidence_id = match.groups()
            row = index.get(evidence_id)
            if row is None:
                orphan_objects += 1
            elif row["object_key"] != key or row["centre_id"] != centre:
                mismatched_records += 1
        if not response.get("IsTruncated", False):
            break
        new_token = response.get("NextContinuationToken")
        if not isinstance(new_token, str) or not new_token or new_token == continuation:
            raise RuntimeError("S3 inventory continuation unavailable")
        continuation = new_token

    for eid, row in index.items():
        case = records.get(eid)
        if case is None:
            indexed_without_case += 1
        elif (case["ambiguous"] or case["centre"] != row["centre_id"]
              or case["sha256"] != row["sha256"]):
            mismatched_records += 1
        if row["object_key"] not in object_keys:
            missing_objects += 1
    for eid in records:
        if eid not in index:
            missing_index += 1

    findings = {
        "object_without_index": orphan_objects,
        "index_without_case": indexed_without_case,
        "case_without_index": missing_index,
        "index_without_object": missing_objects,
        "mismatched_identity_or_digest": mismatched_records,
        "malformed_object_key": malformed_objects,
    }
    return {
        "status": ("attention" if any(findings.values()) or problems else "consistent"),
        "completed": True,
        "read_only": True,
        "scope": "private_evidence_inventory_and_case_metadata",
        "counts": {
            "s3_objects": scanned, "metadata_rows": len(metadata),
            "case_evidence_ids": len(records),
        },
        "findings": findings,
        "structural_warnings": sorted(problems),
        "limitations": [
            "Read-only inventory snapshot; concurrent uploads can appear as orphans.",
            "Object payload bytes and real AWS IAM/KMS policy were not audited.",
            "No objects are deleted or restored; retention/legal hold requires approval.",
        ],
    }
