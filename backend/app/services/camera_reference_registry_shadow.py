"""Phase 3F: durable, shadow-only reference provenance and approval policy.

Local SQLite development store, NOT an exposed API. Principal must be supplied
by an already-authenticated trusted server boundary, never request JSON/headers.
Role and scope checks here are defense-in-depth, not an identity verifier.
No image bytes are stored in SQLite, no automatic reference enrollment.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ReferencePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class TrustedActor:
    """Server-injected authorization context (NOT self-authenticating)."""

    subject: str
    role: str
    centre_id: str

    def __post_init__(self) -> None:
        if not all(isinstance(v, str) and 1 <= len(v.strip()) <= 128
                   for v in (self.subject, self.role, self.centre_id)):
            raise ReferencePolicyError("Trusted principal fields are required")


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 256:
        raise ReferencePolicyError(f"{field} must be nonblank and at most 256 chars")
    return value.strip()


def _hash(value: str) -> str:
    if not isinstance(value, str) or not HEX_SHA256.fullmatch(value):
        raise ReferencePolicyError("Reference fingerprint must be lowercase SHA-256")
    return value


def _utc(now: datetime | None) -> str:
    dt = now or datetime.now(timezone.utc)
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ReferencePolicyError("Timezone-aware timestamp required")
    return dt.astimezone(timezone.utc).isoformat()


class ShadowReferenceRegistry:
    """ACID metadata store with append-only hash-chained transition events."""

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if str(self.path) == ":memory:":
            raise ReferencePolicyError("Use persistent filesystem DB for audit")
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reference_proposals (
                    centre_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    capture_id TEXT NOT NULL,
                    reviewed_source_id TEXT NOT NULL,
                    proposer TEXT NOT NULL,
                    approver TEXT,
                    approval_review_id TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (centre_id, camera_id),
                    CHECK (status IN ('PENDING_REVIEW','APPROVED','SUSPENDED','REVOKED'))
                );
                CREATE TABLE IF NOT EXISTS reference_audit (
                    centre_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    prior_hash TEXT NOT NULL,
                    chain_hash TEXT NOT NULL,
                    PRIMARY KEY (centre_id, camera_id, seq)
                );
                CREATE TRIGGER IF NOT EXISTS reference_audit_no_update
                    BEFORE UPDATE ON reference_audit
                    BEGIN SELECT RAISE(ABORT, 'reference audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS reference_audit_no_delete
                    BEFORE DELETE ON reference_audit
                    BEGIN SELECT RAISE(ABORT, 'reference audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS reference_proposals_no_delete
                    BEFORE DELETE ON reference_proposals
                    BEGIN SELECT RAISE(ABORT, 'reference record cannot be deleted'); END;
            """)

    def _connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _authorize(actor: TrustedActor, centre_id: str, role: str) -> None:
        if not isinstance(actor, TrustedActor):
            raise ReferencePolicyError("A server-issued trusted actor is required")
        if actor.centre_id != centre_id or actor.role != role:
            raise ReferencePolicyError("Actor lacks centre-scoped reference permission")

    @staticmethod
    def _lookup(db, centre_id: str, camera_id: str):
        return db.execute(
            "SELECT * FROM reference_proposals WHERE centre_id=? AND camera_id=?",
            (centre_id, camera_id),
        ).fetchone()

    @staticmethod
    def _append(db, centre_id, camera_id, revision, action, actor, stamp, details):
        previous = db.execute(
            "SELECT seq,chain_hash,event_at FROM reference_audit "
            "WHERE centre_id=? AND camera_id=? ORDER BY seq DESC LIMIT 1",
            (centre_id, camera_id),
        ).fetchone()
        if previous and stamp <= previous["event_at"]:
            raise ReferencePolicyError("Event time must increase monotonically")
        seq = previous["seq"] + 1 if previous else 1
        prevhash = previous["chain_hash"] if previous else "0" * 64
        payload = json.dumps(details, sort_keys=True, separators=(",", ":"))
        envelope = json.dumps(
            [centre_id, camera_id, seq, revision, action, actor.subject,
             stamp, payload, prevhash],
            separators=(",", ":"),
        )
        chain = hashlib.sha256(envelope.encode("utf-8")).hexdigest()
        db.execute(
            "INSERT INTO reference_audit "
            "(centre_id,camera_id,seq,revision,action,actor,event_at,payload_json,prior_hash,chain_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (centre_id,camera_id,seq,revision,action,actor.subject,
             stamp,payload,prevhash,chain),
        )

    def propose(
        self, *, actor: TrustedActor, camera_id: str, sha256: str,
        capture_id: str, reviewed_source_id: str,
        at: datetime | None = None,
    ) -> dict:
        camera_id = _text(camera_id, "camera_id")
        sha256 = _hash(sha256)
        capture_id = _text(capture_id, "capture_id")
        reviewed_source_id = _text(reviewed_source_id, "reviewed_source_id")
        self._authorize(actor, actor.centre_id, "camera_operator")
        centre_id = actor.centre_id
        stamp = _utc(at)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._lookup(db, centre_id, camera_id)
            if current and current["status"] not in ("SUSPENDED", "REVOKED"):
                raise ReferencePolicyError("Existing reference must be suspended or revoked")
            revision = current["revision"] + 1 if current else 1
            if current:
                db.execute(
                    "UPDATE reference_proposals SET revision=?,status=?,sha256=?,capture_id=?,"
                    "reviewed_source_id=?,proposer=?,approver=NULL,approval_review_id=NULL,"
                    "updated_at=? WHERE centre_id=? AND camera_id=?",
                    (revision,"PENDING_REVIEW",sha256,capture_id,reviewed_source_id,
                     actor.subject,stamp,centre_id,camera_id),
                )
            else:
                db.execute(
                    "INSERT INTO reference_proposals "
                    "(centre_id,camera_id,revision,status,sha256,capture_id,"
                    "reviewed_source_id,proposer,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (centre_id,camera_id,revision,"PENDING_REVIEW",sha256,
                     capture_id,reviewed_source_id,actor.subject,stamp),
                )
            self._append(db,centre_id,camera_id,revision,"PROPOSE",actor,stamp,{
                "sha256":sha256,"capture_id":capture_id,
                "reviewed_source_id":reviewed_source_id,
            })
        return self.snapshot(centre_id=centre_id,camera_id=camera_id,actor=actor)

    def approve(
        self, *, actor: TrustedActor, camera_id: str, review_id: str,
        confirmed_healthy: bool, confirmed_same_view: bool,
        independent_comparison: bool, expected_revision: int,
        at: datetime | None = None,
    ) -> dict:
        camera_id = _text(camera_id,"camera_id")
        review_id = _text(review_id,"review_id")
        if type(expected_revision) is not int or expected_revision <= 0:
            raise ReferencePolicyError("Expected positive revision is required")
        if any(type(x) is not bool for x in (
            confirmed_healthy,confirmed_same_view,independent_comparison
        )) or not all((confirmed_healthy,confirmed_same_view,independent_comparison)):
            raise ReferencePolicyError("Independent positive evidence is required")
        self._authorize(actor,actor.centre_id,"camera_reviewer")
        stamp = _utc(at)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._lookup(db,actor.centre_id,camera_id)
            if not current or current["status"] != "PENDING_REVIEW":
                raise ReferencePolicyError("No pending proposal")
            if current["revision"] != expected_revision:
                raise ReferencePolicyError("Stale reference revision")
            if current["proposer"] == actor.subject:
                raise ReferencePolicyError("Independent approver must differ from proposer")
            db.execute(
                "UPDATE reference_proposals SET status='APPROVED',approver=?,"
                "approval_review_id=?,updated_at=? WHERE centre_id=? AND camera_id=?",
                (actor.subject,review_id,stamp,actor.centre_id,camera_id),
            )
            self._append(db,actor.centre_id,camera_id,expected_revision,
                         "APPROVE",actor,stamp,{"review_id":review_id,
                         "checks":["healthy","same_view","independent_comparison"]})
        return self.snapshot(centre_id=actor.centre_id,camera_id=camera_id,actor=actor)

    def transition(
        self, *, actor: TrustedActor, camera_id: str, action: str,
        reason: str, expected_revision: int,
        at: datetime | None = None,
    ) -> dict:
        camera_id = _text(camera_id,"camera_id")
        reason = _text(reason,"reason")
        if action not in ("SUSPEND","REVOKE"):
            raise ReferencePolicyError("Unsupported reference action")
        if type(expected_revision) is not int or expected_revision <= 0:
            raise ReferencePolicyError("Expected positive revision required")
        self._authorize(actor,actor.centre_id,"camera_reviewer")
        stamp = _utc(at)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._lookup(db,actor.centre_id,camera_id)
            if not current or current["revision"] != expected_revision:
                raise ReferencePolicyError("Missing or stale reference")
            if action == "SUSPEND" and current["status"] != "APPROVED":
                raise ReferencePolicyError("Only approved reference can be suspended")
            if action == "REVOKE" and current["status"] not in (
                "PENDING_REVIEW","APPROVED","SUSPENDED"
            ):
                raise ReferencePolicyError("No revocable reference")
            db.execute(
                "UPDATE reference_proposals SET status=?,updated_at=? "
                "WHERE centre_id=? AND camera_id=?",
                ("SUSPENDED" if action == "SUSPEND" else "REVOKED",
                 stamp,actor.centre_id,camera_id),
            )
            self._append(db,actor.centre_id,camera_id,expected_revision,action,
                         actor,stamp,{"reason":reason})
        return self.snapshot(centre_id=actor.centre_id,camera_id=camera_id,actor=actor)

    def snapshot(self, *, centre_id: str, camera_id: str, actor: TrustedActor) -> dict:
        self._authorize(actor,centre_id,actor.role)
        if actor.role not in ("camera_operator","camera_reviewer"):
            raise ReferencePolicyError("Unsupported camera role")
        with self._connection() as db:
            current = self._lookup(db,centre_id,camera_id)
            if current is None:
                return {"centre_id":centre_id,"camera_id":camera_id,"status":"UNENROLLED",
                        "revision":0,"production_integration":False}
            return {
                "centre_id":centre_id,"camera_id":camera_id,
                "status":current["status"],"revision":current["revision"],
                "sha256":current["sha256"],"capture_id":current["capture_id"],
                "reviewed_source_id":current["reviewed_source_id"],
                "proposer":current["proposer"],"approver":current["approver"],
                "approval_review_id":current["approval_review_id"],
                "production_integration":False,
            }

    def verify_audit_chain(self, *, centre_id: str, camera_id: str,
                           actor: TrustedActor) -> bool:
        self._authorize(actor,centre_id,"camera_reviewer")
        with self._connection() as db:
            records = db.execute(
                "SELECT * FROM reference_audit WHERE centre_id=? AND camera_id=? "
                "ORDER BY seq",(centre_id,camera_id),
            ).fetchall()
        previous_hash="0"*64
        for index,row in enumerate(records,1):
            if row["seq"]!=index or row["prior_hash"]!=previous_hash:
                return False
            envelope=json.dumps(
                [centre_id,camera_id,row["seq"],row["revision"],row["action"],
                 row["actor"],row["event_at"],row["payload_json"],previous_hash],
                separators=(",",":"),
            )
            calculated=hashlib.sha256(envelope.encode("utf-8")).hexdigest()
            if calculated!=row["chain_hash"]:
                return False
            previous_hash=calculated
        return True
