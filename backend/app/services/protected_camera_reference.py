"""Protected staging-only camera-reference *metadata* workflow.

A proposal/review records human attestations; it NEVER activates a camera
comparator, proves source pixels, changes attendance or certifies tampering.
Actors are resolved by the existing verified FastAPI middleware, NOT by JSON.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from app.services.officer_permissions import OfficerPrincipal
from app.services.postgres_store import connection

SHA256 = re.compile(r"^[a-f0-9]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
STATES = frozenset({"PENDING_REVIEW", "REVIEWED_NOT_BOUND", "SUSPENDED", "REVOKED"})


class CameraReferencePolicyError(ValueError):
    pass


class CameraReferenceConflict(CameraReferencePolicyError):
    pass


def required(value: str, name: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise CameraReferencePolicyError(f"Invalid {name}")
    return value


def _reason(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= 128
            or not all(char.isprintable() for char in value)):
        raise CameraReferencePolicyError("A short printable suspension reason is required")
    return value.strip()


def _actor(principal: OfficerPrincipal, centre_id: str, role: str) -> str:
    if not isinstance(principal, OfficerPrincipal):
        raise CameraReferencePolicyError("Verified officer principal is required")
    if principal.role != role or not principal.can_access(centre_id):
        raise CameraReferencePolicyError("Independent centre-scoped officer role required")
    return required(principal.actor, "actor")


def _event_hash(
    *, centre_id: str, camera_id: str, sequence: int, revision: int,
    action: str, actor: str, happened_at: datetime, summary: dict,
    previous_hash: str,
) -> str:
    canonical = json.dumps(
        [centre_id, camera_id, sequence, revision, action, actor,
         happened_at.astimezone(timezone.utc).isoformat(), summary, previous_hash],
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _history(db: Any, centre_id: str, camera_id: str) -> list[dict]:
    return db.execute(
        "SELECT sequence,revision,action,actor,happened_at,summary,previous_hash,event_hash "
        "FROM kw_camera_reference_events WHERE centre_id=%s AND camera_id=%s "
        "ORDER BY sequence", (centre_id, camera_id),
    ).fetchall()


def _verify(row: dict | None, history: list[dict]) -> bool:
    if not history:
        return row is None
    if row is None:
        return False
    prev = "0" * 64
    latest_proposal = None
    latest_review = None
    for seq, entry in enumerate(history, 1):
        if entry["sequence"] != seq or entry["previous_hash"] != prev:
            return False
        expected = _event_hash(
            centre_id=row["centre_id"], camera_id=row["camera_id"],
            sequence=entry["sequence"], revision=entry["revision"],
            action=entry["action"], actor=entry["actor"],
            happened_at=entry["happened_at"], summary=entry["summary"],
            previous_hash=prev,
        )
        if expected != entry["event_hash"]:
            return False
        if entry["action"] == "PROPOSE":
            latest_proposal = entry
            latest_review = None
        elif entry["action"] == "REVIEW":
            latest_review = entry
        elif entry["action"] not in ("SUSPEND", "REVOKE"):
            return False
        prev = expected
    last = history[-1]
    state = {"PROPOSE": "PENDING_REVIEW", "REVIEW": "REVIEWED_NOT_BOUND",
             "SUSPEND": "SUSPENDED", "REVOKE": "REVOKED"}[last["action"]]
    if not latest_proposal or row["state"] != state or row["revision"] != last["revision"]:
        return False
    data = latest_proposal["summary"]
    return all((
        row["reference_digest"] == data.get("reference_digest"),
        row["capture_id"] == data.get("capture_id"),
        row["source_review_id"] == data.get("source_review_id"),
        row["proposed_by"] == latest_proposal["actor"],
        row["reviewed_by"] == (latest_review["actor"] if latest_review else None),
        row["independent_review_id"] ==
            (latest_review["summary"].get("independent_review_id") if latest_review else None),
        row["updated_at"] == last["happened_at"],
    ))


def _append(db: Any, *, centre_id: str, camera_id: str, revision: int,
            action: str, actor: str, summary: dict, history: list[dict]) -> None:
    sequence = len(history) + 1
    previous_hash = history[-1]["event_hash"] if history else "0" * 64
    now = datetime.now(timezone.utc)
    if history and now <= history[-1]["happened_at"]:
        raise CameraReferenceConflict("Event ordering conflict; retry")
    digest = _event_hash(
        centre_id=centre_id, camera_id=camera_id, sequence=sequence,
        revision=revision, action=action, actor=actor, happened_at=now,
        summary=summary, previous_hash=previous_hash,
    )
    db.execute(
        "INSERT INTO kw_camera_reference_events "
        "(centre_id,camera_id,sequence,revision,action,actor,happened_at,"
        "summary,previous_hash,event_hash) VALUES "
        "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (centre_id, camera_id, sequence, revision, action, actor, now,
         __jsonb(summary), previous_hash, digest),
    )
    return now


def __jsonb(data: dict):
    from psycopg.types.json import Jsonb
    return Jsonb(data)


def _locked(db, centre_id: str, camera_id: str):
    return db.execute(
        "SELECT * FROM kw_camera_reference_proposals "
        "WHERE centre_id=%s AND camera_id=%s FOR UPDATE",
        (centre_id, camera_id),
    ).fetchone()


def _public(row: dict | None, *, centre_id: str, camera_id: str) -> dict:
    if row is None:
        return {
            "centre_id": centre_id, "camera_id": camera_id,
            "state": "UNENROLLED", "revision": 0,
            "production_binding": False,
            "actual_reference_verified": False,
            "attendance_changes_authorized": False,
        }
    return {
        "centre_id": centre_id, "camera_id": camera_id,
        "state": row["state"], "revision": row["revision"],
        "reference_digest": row["reference_digest"],
        "capture_id": row["capture_id"],
        "source_review_id": row["source_review_id"],
        "proposed_by": row["proposed_by"],
        "reviewed_by": row["reviewed_by"],
        "independent_review_id": row["independent_review_id"],
        "production_binding": False,
        "actual_reference_verified": False,
        "attendance_changes_authorized": False,
    }


class ProtectedCameraReferenceWorkflow:
    """PostgreSQL transaction-backed, no auto-enrollment or actor spoofing."""

    def get(self, *, principal: OfficerPrincipal, centre_id: str, camera_id: str) -> dict:
        centre_id, camera_id = required(centre_id, "centre"), required(camera_id, "camera")
        if not isinstance(principal, OfficerPrincipal) or not principal.can_access(centre_id):
            raise CameraReferencePolicyError("Officer cannot view camera reference")
        with connection() as db:
            row = _locked(db, centre_id, camera_id)
            history = _history(db, centre_id, camera_id)
            if not _verify(row, history):
                raise CameraReferenceConflict("Reference audit metadata mismatch")
        result = _public(row, centre_id=centre_id, camera_id=camera_id)
        if os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW", "") == "shadow_artifact":
            from app.services.camera_reference_artifacts import _artifact_row
            with connection() as db:
                image = _artifact_row(db, centre_id, camera_id, row["revision"]) if row else None
            if image and image["pixel_sha256"] != row["reference_digest"]:
                raise CameraReferenceConflict("Reference artifact and proposal mismatch")
            result["artifact_attached"] = bool(image)
        return result

    def propose(self, *, principal: OfficerPrincipal, centre_id: str,
                camera_id: str, reference_digest: str, capture_id: str,
                source_review_id: str, expected_revision: int) -> dict:
        centre_id, camera_id = required(centre_id, "centre"), required(camera_id, "camera")
        actor = _actor(principal, centre_id, "centre_reviewer")
        if not isinstance(reference_digest, str) or not SHA256.fullmatch(reference_digest):
            raise CameraReferencePolicyError("Canonical lowercase pixel SHA-256 required")
        capture_id = required(capture_id, "capture")
        source_review_id = required(source_review_id, "source review")
        if type(expected_revision) is not int or expected_revision < 0:
            raise CameraReferencePolicyError("Expected revision must be nonnegative integer")
        with connection() as db:
            row = _locked(db, centre_id, camera_id)
            history = _history(db, centre_id, camera_id)
            if not _verify(row, history):
                raise CameraReferenceConflict("Reference audit metadata mismatch")
            revision = row["revision"] if row else 0
            if expected_revision != revision:
                raise CameraReferenceConflict("Stale reference revision")
            if row and row["state"] not in ("SUSPENDED", "REVOKED"):
                raise CameraReferenceConflict("Existing proposal must be suspended or revoked")
            revision += 1
            now = datetime.now(timezone.utc)
            if row:
                db.execute(
                    "UPDATE kw_camera_reference_proposals "
                    "SET revision=%s,state='PENDING_REVIEW',reference_digest=%s,"
                    "capture_id=%s,source_review_id=%s,proposed_by=%s,"
                    "reviewed_by=NULL,independent_review_id=NULL,updated_at=%s "
                    "WHERE centre_id=%s AND camera_id=%s",
                    (revision, reference_digest, capture_id, source_review_id,
                     actor, now, centre_id, camera_id),
                )
            else:
                db.execute(
                    "INSERT INTO kw_camera_reference_proposals "
                    "(centre_id,camera_id,revision,state,reference_digest,capture_id,"
                    "source_review_id,proposed_by,updated_at) "
                    "VALUES (%s,%s,%s,'PENDING_REVIEW',%s,%s,%s,%s,%s)",
                    (centre_id,camera_id,revision,reference_digest,capture_id,
                     source_review_id,actor,now),
                )
            _append_with_time(db, centre_id=centre_id,camera_id=camera_id,
                revision=revision,action="PROPOSE",actor=actor,when=now,
                summary={"reference_digest":reference_digest,"capture_id":capture_id,
                         "source_review_id":source_review_id},history=history)
        return self.get(principal=principal,centre_id=centre_id,camera_id=camera_id)

    def review(self, *, principal: OfficerPrincipal, centre_id: str, camera_id: str,
               expected_revision: int, independent_review_id: str,
               verified_healthy: bool, verified_same_view: bool,
               compared_independently: bool) -> dict:
        centre_id, camera_id = required(centre_id, "centre"), required(camera_id, "camera")
        actor = _actor(principal, centre_id, "network_admin")
        independent_review_id = required(independent_review_id, "independent review")
        if (type(expected_revision) is not int or expected_revision <= 0 or
                any(type(x) is not bool for x in (
                    verified_healthy, verified_same_view, compared_independently
                )) or not all((verified_healthy,verified_same_view,compared_independently))):
            raise CameraReferencePolicyError("Independent review evidence and current revision required")
        with connection() as db:
            row = _locked(db, centre_id, camera_id)
            history = _history(db, centre_id, camera_id)
            if not _verify(row, history):
                raise CameraReferenceConflict("Reference audit metadata mismatch")
            if not row or row["state"] != "PENDING_REVIEW":
                raise CameraReferenceConflict("No pending camera-reference review")
            if row["revision"] != expected_revision:
                raise CameraReferenceConflict("Stale reference revision")
            if row["proposed_by"] == actor:
                raise CameraReferencePolicyError("Proposer cannot review own reference")
            if os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW", "") == "shadow_artifact":
                from app.services.camera_reference_artifacts import _artifact_row, _read_verified
                item = _artifact_row(db, centre_id, camera_id, expected_revision)
                if not item or item["pixel_sha256"] != row["reference_digest"]:
                    raise CameraReferenceConflict("Matching private reference image required")
                # Verify actual private storage and canonical pixels, not just
                # request-attested SHA-256 or unverified database metadata.
                _read_verified(item)
            now = datetime.now(timezone.utc)
            db.execute(
                "UPDATE kw_camera_reference_proposals SET state='REVIEWED_NOT_BOUND',"
                "reviewed_by=%s,independent_review_id=%s,updated_at=%s "
                "WHERE centre_id=%s AND camera_id=%s",
                (actor,independent_review_id,now,centre_id,camera_id),
            )
            _append_with_time(db,centre_id=centre_id,camera_id=camera_id,
                revision=expected_revision,action="REVIEW",actor=actor,when=now,
                summary={"independent_review_id":independent_review_id,
                         "checks":["healthy","same_view","independent_comparison"],
                         "binding":"DISABLED"},history=history)
        return self.get(principal=principal,centre_id=centre_id,camera_id=camera_id)

    def suspend(self, *, principal: OfficerPrincipal, centre_id: str,
                camera_id: str, expected_revision: int, reason: str) -> dict:
        centre_id, camera_id = required(centre_id,"centre"), required(camera_id,"camera")
        actor = _actor(principal,centre_id,"network_admin")
        reason = _reason(reason)
        if type(expected_revision) is not int or expected_revision <= 0:
            raise CameraReferencePolicyError("Valid revision required")
        with connection() as db:
            row = _locked(db,centre_id,camera_id)
            history = _history(db,centre_id,camera_id)
            if not _verify(row,history):
                raise CameraReferenceConflict("Reference audit metadata mismatch")
            if not row or row["revision"]!=expected_revision:
                raise CameraReferenceConflict("Reference revision changed")
            if row["state"] not in ("PENDING_REVIEW","REVIEWED_NOT_BOUND"):
                raise CameraReferenceConflict("Nothing to suspend")
            now=datetime.now(timezone.utc)
            db.execute(
                "UPDATE kw_camera_reference_proposals SET state='SUSPENDED',updated_at=%s "
                "WHERE centre_id=%s AND camera_id=%s",
                (now,centre_id,camera_id),
            )
            _append_with_time(db,centre_id=centre_id,camera_id=camera_id,
                revision=expected_revision,action="SUSPEND",actor=actor,when=now,
                summary={"reason":reason},history=history)
        return self.get(principal=principal,centre_id=centre_id,camera_id=camera_id)


def _append_with_time(db, *, centre_id, camera_id, revision, action, actor,
                      when, summary, history):
    seq=len(history)+1
    last=history[-1] if history else None
    if last and when <= last["happened_at"]:
        raise CameraReferenceConflict("Out-of-order audit transition")
    previous_hash=last["event_hash"] if last else "0"*64
    digest=_event_hash(
        centre_id=centre_id,camera_id=camera_id,sequence=seq,revision=revision,
        action=action,actor=actor,happened_at=when,
        summary=summary,previous_hash=previous_hash,
    )
    db.execute(
        "INSERT INTO kw_camera_reference_events "
        "(centre_id,camera_id,sequence,revision,action,actor,happened_at,"
        "summary,previous_hash,event_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (centre_id,camera_id,seq,revision,action,actor,when,__jsonb(summary),
         previous_hash,digest),
    )
