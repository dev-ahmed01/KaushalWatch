"""Private, immutable S3 evidence with PostgreSQL-backed integrity metadata.

The local SIH prototype continues to use its existing file/index store.
Protected multi-instance deployments select s3+postgres explicitly. S3 objects
may remain orphaned if a DB write fails; an orphan is never made visible to
officers because reads require BOTH a persisted case and matching DB metadata.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import os
import re

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
import cv2
import numpy as np

from app.models import EvidenceRecord
from app.services.evidence import dhash, hamming_hex
from app.services.postgres_store import connection

EVIDENCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
CENTRE_ID = re.compile(r"^[A-Za-z0-9_-]{2,128}$")
BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def configuration() -> tuple[str, str, str]:
    if os.getenv("KAUSHALWATCH_ENV", "development").strip().lower() in {
        "development", "dev", "local", "test"
    }:
        raise RuntimeError("Private evidence requires protected officer authentication mode")
    if os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json") != "postgres":
        raise RuntimeError("Private evidence requires PostgreSQL persistence")
    bucket = os.getenv("KAUSHALWATCH_EVIDENCE_S3_BUCKET", "").strip()
    region = os.getenv("KAUSHALWATCH_EVIDENCE_S3_REGION", "").strip()
    kms = os.getenv("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID", "").strip()
    if not BUCKET_NAME.fullmatch(bucket) or not region or not kms:
        raise RuntimeError("Private evidence bucket, region and KMS key must be configured")
    if not re.fullmatch(r"[a-z0-9-]{3,32}", region):
        raise RuntimeError("Invalid object storage region")
    # Do not allow arbitrary endpoints or HTTP during a protected deployment.
    if os.getenv("KAUSHALWATCH_EVIDENCE_S3_ENDPOINT_URL"):
        raise RuntimeError("Custom S3 endpoints are unsupported for protected evidence")
    return bucket, region, kms


def _client():
    _, region, _ = configuration()
    return boto3.client(
        "s3", region_name=region,
        config=Config(signature_version="s3v4", retries={"max_attempts": 2, "mode": "standard"},
                      connect_timeout=5, read_timeout=12),
    )


def _validate_identity(evidence_id: str, centre_id: str) -> None:
    if not EVIDENCE_ID.fullmatch(evidence_id) or not CENTRE_ID.fullmatch(centre_id):
        raise ValueError("Evidence ID or centre ID is unsafe")


def persist_private_evidence(frame: np.ndarray, evidence_id: str, metadata: dict) -> EvidenceRecord:
    centre = metadata.get("centre_id")
    if not isinstance(centre, str):
        raise ValueError("Private evidence must belong to a centre")
    _validate_identity(evidence_id, centre)
    if not isinstance(metadata.get("privacy_transform"), str):
        raise ValueError("An explicit pre-storage privacy transform is required")
    bucket, _, kms = configuration()
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Evidence frame JPEG encoding failed")
    payload = encoded.tobytes()
    if len(payload) == 0 or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("Evidence exceeds the protected image size limit")
    digest = hashlib.sha256(payload).hexdigest()
    perceptual_hash = dhash(frame)
    key = f"evidence/v1/{centre}/{evidence_id}.jpg"
    # Storage-side conditional create prevents a second uploader replacing
    # an existing object. All reads re-validate SHA-256 against the case.
    _client().put_object(
        Bucket=bucket, Key=key, Body=payload, ContentType="image/jpeg",
        ChecksumSHA256=base64.b64encode(bytes.fromhex(digest)).decode("ascii"),
        IfNoneMatch="*", ServerSideEncryption="aws:kms", SSEKMSKeyId=kms,
        CacheControl="no-store",
        Metadata={"sha256": digest, "centre": centre, "evidence-id": evidence_id},
    )
    with connection() as db:
        # A transaction-scoped centre lock ensures two workers derive duplicate
        # evidence notices from the same committed history.
        db.execute("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", (centre, 82630094))
        candidates = db.execute(
            """SELECT evidence_id, perceptual_hash FROM kw_evidence_objects
               WHERE centre_id = %s ORDER BY created_at, evidence_id""", (centre,)
        ).fetchall()
        dup = next((row["evidence_id"] for row in candidates
                    if hamming_hex(perceptual_hash, row["perceptual_hash"]) <= 4), None)
        inserted = db.execute(
            """INSERT INTO kw_evidence_objects
               (evidence_id, centre_id, object_key, sha256, perceptual_hash)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT(evidence_id) DO NOTHING RETURNING evidence_id""",
            (evidence_id, centre, key, digest, perceptual_hash),
        ).fetchone()
        if not inserted:
            raise ValueError("Evidence ID collision refused")
    return EvidenceRecord(
        evidence_id=evidence_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        frame_path=f"object://{evidence_id}", sha256=digest,
        perceptual_hash=perceptual_hash, duplicate_of=dup, metadata=metadata,
    )


def fetch_private_evidence(record: EvidenceRecord, centre_id: str) -> bytes | None:
    """Call ONLY after checking case membership and officer centre scope."""
    _validate_identity(record.evidence_id, centre_id)
    bucket, _, _ = configuration()
    with connection() as db:
        rows = db.execute(
            """SELECT centre_id, object_key, sha256, perceptual_hash
               FROM kw_evidence_objects WHERE evidence_id = %s""",
            (record.evidence_id,),
        ).fetchone()
    if rows is None:
        return None
    if (rows["centre_id"] != centre_id or rows["sha256"] != record.sha256
            or rows["perceptual_hash"] != record.perceptual_hash):
        raise ValueError("Evidence integrity index differs from persisted case")
    expected_key = f"evidence/v1/{centre_id}/{record.evidence_id}.jpg"
    if rows["object_key"] != expected_key:
        raise ValueError("Evidence object key does not match its centre")
    response = _client().get_object(Bucket=bucket, Key=expected_key)
    body = response["Body"]
    try:
        content = body.read(MAX_IMAGE_BYTES + 1)
    finally:
        body.close()
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Evidence image is absent or exceeds the size limit")
    if hashlib.sha256(content).hexdigest() != record.sha256:
        raise ValueError("Evidence image SHA-256 mismatch")
    return content
