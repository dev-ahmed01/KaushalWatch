"""Private, metadata-stripped camera reference images (STAGING / SHADOW ONLY).

An image digest proves exact bytes in private storage, NOT camera provenance,
viewpoint authenticity or officer review. No production detector uses this.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from secrets import token_hex

import boto3
from botocore.config import Config
import cv2
import numpy as np

from app.services.protected_camera_reference import (
    CameraReferenceConflict, CameraReferencePolicyError, _actor, _history,
    _locked, _public, _verify, required,
)
from app.services.officer_permissions import OfficerPrincipal
from app.services.postgres_store import connection

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_CANONICAL_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 1920 * 1080
BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")
REGION = re.compile(r"^[a-z0-9-]{3,32}$")


def config() -> tuple[str, str, str]:
    if (os.getenv("KAUSHALWATCH_ENV", "").strip().lower() != "staging"
            or os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW", "").strip().lower()
            != "shadow_artifact"
            or os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "") != "postgres"):
        raise CameraReferencePolicyError("Private reference artifacts are staging-only")
    if os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_ENDPOINT_URL"):
        raise CameraReferencePolicyError("Custom object-store endpoints are disabled")
    bucket = os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_BUCKET", "").strip()
    region = os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_REGION", "").strip()
    kms = os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_KMS_KEY_ID", "").strip()
    if not BUCKET.fullmatch(bucket) or not REGION.fullmatch(region) or not kms:
        raise CameraReferencePolicyError("Private reference S3/KMS settings are required")
    if "/" in kms and not kms.startswith("arn:aws:kms:"):
        raise CameraReferencePolicyError("Invalid KMS key identifier")
    return bucket, region, kms


def _client():
    _, region, _ = config()
    return boto3.client(
        "s3", region_name=region,
        config=Config(
            signature_version="s3v4", retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=5, read_timeout=12,
        ),
    )


def pixel_digest(frame: np.ndarray) -> str:
    """Canonical digest matches the SHA-256 convention from Phase 3F."""
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
            frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0):
        raise CameraReferencePolicyError("Only uint8 BGR camera pixels are supported")
    packed = np.ascontiguousarray(frame)
    meta = json.dumps(
        {"shape": list(packed.shape), "dtype": str(packed.dtype)},
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(
        len(meta).to_bytes(4, "big") + meta + packed.tobytes()
    ).hexdigest()


def _declared_dimensions(data: bytes) -> tuple[int, int]:
    """Preflight untrusted codec dimensions BEFORE allocating a decoded frame."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise CameraReferencePolicyError("Invalid PNG header")
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if not data.startswith(b"\xff\xd8\xff"):
        raise CameraReferencePolicyError("Unsupported image encoding")
    offset = 2
    while offset + 3 < len(data):
        if data[offset] != 0xff:
            raise CameraReferencePolicyError("Malformed JPEG marker")
        while offset < len(data) and data[offset] == 0xff:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in (0xd8, 0x01) or 0xd0 <= marker <= 0xd7:
            continue
        if marker in (0xd9, 0xda) or offset + 2 > len(data):
            break
        size = int.from_bytes(data[offset:offset+2], "big")
        if size < 2 or offset + size > len(data):
            break
        if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
            if size < 7:
                break
            height = int.from_bytes(data[offset+3:offset+5], "big")
            width = int.from_bytes(data[offset+5:offset+7], "big")
            return width, height
        offset += size
    raise CameraReferencePolicyError("Missing or corrupt JPEG dimensions")


def normalize_image(upload: bytes) -> tuple[np.ndarray, bytes, str, str]:
    """Decode one PNG/JPEG into a canonical PNG, with metadata stripped."""
    if not isinstance(upload, bytes) or not 0 < len(upload) <= MAX_UPLOAD_BYTES:
        raise CameraReferencePolicyError("Reference image must be at most 2 MiB")
    if not (
        upload.startswith(b"\x89PNG\r\n\x1a\n")
        or upload.startswith(b"\xff\xd8\xff")
    ):
        raise CameraReferencePolicyError("Only real PNG/JPEG images are supported")
    announced_width, announced_height = _declared_dimensions(upload)
    if not (32 <= announced_width <= 1920 and
            32 <= announced_height <= 1080 and
            announced_width * announced_height <= MAX_PIXELS):
        raise CameraReferencePolicyError("Reference dimensions are unsupported")
    # OpenCV strips source container metadata when re-encoding. The decoded
    # image may be 3-channel BGR (no alpha), with dimensional hard caps.
    frame = cv2.imdecode(np.frombuffer(upload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or frame.dtype != np.uint8 or frame.ndim != 3:
        raise CameraReferencePolicyError("Image could not be decoded")
    height, width = frame.shape[:2]
    if not (32 <= width <= 1920 and 32 <= height <= 1080 and
            width * height <= MAX_PIXELS):
        raise CameraReferencePolicyError("Reference image dimensions are unsupported")
    valid, encoded = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not valid:
        raise CameraReferencePolicyError("Cannot normalize reference image")
    content = encoded.tobytes()
    if len(content) > MAX_CANONICAL_BYTES:
        raise CameraReferencePolicyError("Canonical image exceeds 4 MiB")
    return frame, content, pixel_digest(frame), hashlib.sha256(content).hexdigest()


def object_key(centre_id: str, camera_id: str, revision: int) -> str:
    required(centre_id, "centre")
    required(camera_id, "camera")
    if type(revision) is not int or revision <= 0:
        raise CameraReferencePolicyError("Valid reference revision required")
    return f"camera-references/v1/{centre_id}/{camera_id}/r{revision}/{token_hex(16)}.png"


def _artifact_row(db, centre_id: str, camera_id: str, revision: int):
    return db.execute(
        "SELECT * FROM kw_camera_reference_artifacts WHERE centre_id=%s "
        "AND camera_id=%s AND revision=%s",
        (centre_id, camera_id, revision),
    ).fetchone()


def _read_verified(row: dict) -> tuple[np.ndarray, bytes]:
    bucket, _, _ = config()
    expected_prefix = (
        f"camera-references/v1/{row['centre_id']}/{row['camera_id']}/"
        f"r{row['revision']}/"
    )
    key = row["object_key"]
    if (not key.startswith(expected_prefix) or
            not re.fullmatch(r"[a-f0-9]{32}\.png", key[len(expected_prefix):])):
        raise CameraReferenceConflict("Reference object key has invalid scope")
    response = _client().get_object(Bucket=bucket, Key=key)
    stream = response["Body"]
    try:
        raw = stream.read(MAX_CANONICAL_BYTES + 1)
    finally:
        stream.close()
    if (not raw or len(raw) != row["byte_size"] or
            len(raw) > MAX_CANONICAL_BYTES or
            hashlib.sha256(raw).hexdigest() != row["encoded_sha256"]):
        raise CameraReferenceConflict("Reference object integrity mismatch")
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if (frame is None or frame.dtype != np.uint8 or frame.ndim != 3 or
            frame.shape[2] != 3 or
            frame.shape[1] != row["width"] or frame.shape[0] != row["height"]
            or pixel_digest(frame) != row["pixel_sha256"]):
        raise CameraReferenceConflict("Reference pixel integrity mismatch")
    return frame, raw


def attach_reference_image(
    *, principal: OfficerPrincipal, centre_id: str, camera_id: str,
    expected_revision: int, content: bytes,
) -> dict:
    """One-time S3 create, then reference-scoped transactional DB index.

    An S3 object may be orphaned if the DB commit fails; it is never readable
    through this API without an exact committed row and authorized principal.
    """
    centre_id, camera_id = required(centre_id, "centre"), required(camera_id, "camera")
    actor = _actor(principal, centre_id, "centre_reviewer")
    if type(expected_revision) is not int or expected_revision <= 0:
        raise CameraReferencePolicyError("Reference revision required")
    frame, canonical, digest, stored_sha = normalize_image(content)
    with connection() as db:
        row = _locked(db, centre_id, camera_id)
        history = _history(db, centre_id, camera_id)
        if not _verify(row, history):
            raise CameraReferenceConflict("Reference metadata audit mismatch")
        if (row is None or row["state"] != "PENDING_REVIEW"
                or row["revision"] != expected_revision or
                row["proposed_by"] != actor or row["reference_digest"] != digest):
            raise CameraReferenceConflict("Reference proposal or pixel SHA-256 mismatch")
        if _artifact_row(db, centre_id, camera_id, expected_revision):
            raise CameraReferenceConflict("Reference artifact already attached")
    bucket, _, kms = config()
    key = object_key(centre_id, camera_id, expected_revision)
    _client().put_object(
        Bucket=bucket, Key=key, Body=canonical, ContentType="image/png",
        ChecksumSHA256=base64.b64encode(bytes.fromhex(stored_sha)).decode("ascii"),
        IfNoneMatch="*", ServerSideEncryption="aws:kms", SSEKMSKeyId=kms,
        CacheControl="private, no-store",
        Metadata={"pixel-sha256": digest, "centre": centre_id, "camera-id": camera_id},
    )
    with connection() as db:
        row = _locked(db, centre_id, camera_id)
        history = _history(db, centre_id, camera_id)
        if (not _verify(row, history) or row is None or
                row["state"] != "PENDING_REVIEW" or
                row["revision"] != expected_revision or
                row["proposed_by"] != actor or row["reference_digest"] != digest):
            raise CameraReferenceConflict("Reference proposal changed during upload")
        inserted = db.execute(
            "INSERT INTO kw_camera_reference_artifacts "
            "(centre_id,camera_id,revision,object_key,pixel_sha256,"
            "encoded_sha256,byte_size,width,height,stored_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (centre_id,camera_id,revision) DO NOTHING "
            "RETURNING revision",
            (centre_id,camera_id,expected_revision,key,digest,stored_sha,
             len(canonical),frame.shape[1],frame.shape[0],actor),
        ).fetchone()
        if inserted is None:
            raise CameraReferenceConflict("Reference artifact already attached")
    return {"attached": True, "pixel_sha256": digest, "revision": expected_revision,
            "production_binding": False, "provenance_verified": False}


def artifact_status(*, principal: OfficerPrincipal, centre_id: str, camera_id: str,
                    expected_revision: int) -> dict:
    if not isinstance(principal, OfficerPrincipal) or not principal.can_access(centre_id):
        raise CameraReferencePolicyError("Officer cannot access reference")
    with connection() as db:
        row = _locked(db, centre_id, camera_id)
        history = _history(db, centre_id, camera_id)
        if not _verify(row, history):
            raise CameraReferenceConflict("Reference metadata audit mismatch")
        if row is None or row["revision"] != expected_revision:
            raise CameraReferenceConflict("Reference revision changed")
        item = _artifact_row(db, centre_id, camera_id, expected_revision)
        if item and item["pixel_sha256"] != row["reference_digest"]:
            raise CameraReferenceConflict("Reference metadata and artifact disagree")
    return {"attached": item is not None, "revision": expected_revision,
            "pixel_sha256": item["pixel_sha256"] if item else None,
            "provenance_verified": False, "production_binding": False}


def verified_reference_frame(
    *, principal: OfficerPrincipal, centre_id: str, camera_id: str,
    expected_revision: int, require_reviewed: bool = False,
) -> tuple[np.ndarray, bytes]:
    """Private, officer-scoped read, with revocation + DB/S3 integrity checks."""
    if not isinstance(principal, OfficerPrincipal) or not principal.can_access(centre_id):
        raise CameraReferencePolicyError("Reference centre permission required")
    if principal.role not in ("centre_reviewer","network_admin"):
        raise CameraReferencePolicyError("Only reviewer roles can inspect reference frames")
    with connection() as db:
        row = _locked(db, centre_id, camera_id)
        history = _history(db, centre_id, camera_id)
        if not _verify(row, history):
            raise CameraReferenceConflict("Reference metadata audit mismatch")
        if (row is None or row["revision"] != expected_revision or
                row["state"] not in ("PENDING_REVIEW","REVIEWED_NOT_BOUND") or
                (require_reviewed and row["state"] != "REVIEWED_NOT_BOUND")):
            raise CameraReferenceConflict("Reference is not in a reviewable state")
        item = _artifact_row(db,centre_id,camera_id,expected_revision)
        if item is None or item["pixel_sha256"] != row["reference_digest"]:
            raise CameraReferenceConflict("No matching private reference image")
    return _read_verified(item)
