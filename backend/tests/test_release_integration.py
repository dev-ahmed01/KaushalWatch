"""Release cross-stack acceptance: signed OIDC + PostgreSQL + private S3.

Uses the isolated CI Postgres database, ephemeral signing key, and an in-memory
S3 stand-in. No official IdP, real S3/KMS, real training-centre CCTV or live
government records are involved. Synthetic fixtures cannot certify a pilot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
import sys
from pathlib import Path

import jwt
import numpy as np
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import ComplianceCase
from app.services import object_evidence, oidc_identity
from app.services.postgres_store import PostgresCaseStore

FIRST = "DEMO-KA-104"
SECOND = "DEMO-KA-112"
ISSUER = "https://idp.example.org/ci-kaushalwatch"
JWKS = "https://idp.example.org/jwks"
API_AUDIENCE = "api://kaushalwatch"
SUB_ADMIN = "release-admin-subject"
SUB_REVIEWER = "release-centre-reviewer-subject"
SUB_VIEWER = "release-centre-viewer-subject"


class MemoryS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.read_keys: list[str] = []

    def put_object(self, **args):
        assert args["IfNoneMatch"] == "*"
        assert args["ServerSideEncryption"] == "aws:kms"
        assert args["SSEKMSKeyId"] == "alias/release-synthetic-kms"
        assert args["Key"] not in self.objects
        self.objects[args["Key"]] = args["Body"]

    def get_object(self, **args):
        self.read_keys.append(args["Key"])
        if args["Key"] not in self.objects:
            raise RuntimeError("Synthetic object not found")
        return {"Body": BytesIO(self.objects[args["Key"]])}


@pytest.fixture
def cross_stack(monkeypatch):
    dsn = os.getenv("KAUSHALWATCH_DATABASE_URL", "")
    if not dsn and not os.getenv("KAUSHALWATCH_TEST_DATABASE"):
        pytest.skip("Cross-stack acceptance uses dedicated isolated PostgreSQL CI only")
    if (os.getenv("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci"
            or "kaushalwatch_ci" not in dsn):
        pytest.fail("Refusing to write to any non-isolated release test database")

    import app.main as main
    if main.STORAGE_BACKEND != "postgres" or main.EVIDENCE_BACKEND != "s3":
        pytest.fail("Release test requires PostgreSQL and S3 route selected at import time")

    with psycopg.connect(dsn) as db:
        db.execute(
            "TRUNCATE kw_evidence_objects, kw_cases, kw_analysis_history, "
            "kw_edge_events, kw_centre_settings RESTART IDENTITY"
        )
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT", "true")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "oidc")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_BACKEND", "s3")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_S3_BUCKET", "kaushalwatch-private-ci")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_S3_REGION", "ap-south-1")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID", "alias/release-synthetic-kms")
    monkeypatch.setenv("KAUSHALWATCH_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("KAUSHALWATCH_OIDC_JWKS_URL", JWKS)
    monkeypatch.setenv("KAUSHALWATCH_OIDC_AUDIENCE", API_AUDIENCE)
    monkeypatch.setenv("KAUSHALWATCH_OIDC_GRANTS_JSON", json.dumps({
        SUB_ADMIN: {
            "actor": "release-network-admin", "role": "network_admin", "centres": []
        },
        SUB_REVIEWER: {
            "actor": "release-centre-reviewer", "role": "centre_reviewer",
            "centres": [FIRST]
        },
        SUB_VIEWER: {
            "actor": "release-centre-viewer", "role": "centre_viewer",
            "centres": [FIRST]
        },
    }))
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public.update({"kid": "release-test-key", "use": "sig", "alg": "RS256"})
    monkeypatch.setattr(oidc_identity, "_load_jwks", lambda _: {"keys": [public]})
    oidc_identity._cached_jwks.cache_clear()
    fake_storage = MemoryS3()
    monkeypatch.setattr(object_evidence, "_client", lambda: fake_storage)

    def issue(subject: str, *, claims: dict | None = None):
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "iss": ISSUER, "aud": API_AUDIENCE, "sub": subject,
            "iat": now - 1, "nbf": now - 1, "exp": now + 600,
            "token_use": "access", "role": "network_admin", "groups": ["superuser"],
            **(claims or {}),
        }
        return {"Authorization": "Bearer " + jwt.encode(
            payload, private_key, algorithm="RS256",
            headers={"kid": "release-test-key", "typ": "at+jwt"},
        )}

    def attach(centre: str, evidence_id: str):
        # Deliberately synthetic frames contain no real people or private data.
        frame = np.full((96, 144, 3), 50 if centre == FIRST else 220, dtype=np.uint8)
        evidence = object_evidence.persist_private_evidence(
            frame, evidence_id, {
                "centre_id": centre, "batch_id": "CI-RELEASE",
                "privacy_transform": "synthetic_test_frame_no_person",
            },
        )
        saved = PostgresCaseStore().save_if_absent(ComplianceCase(
            case_id=f"RC1-{evidence_id}", centre_id=centre,
            batch_id="CI-RELEASE", case_type="attendance_discrepancy",
            severity="medium", summary="Synthetic isolated release acceptance",
            evidence=[evidence],
        ))
        assert saved is True
        return evidence

    yield main, TestClient(main.app), fake_storage, issue, attach
    oidc_identity._cached_jwks.cache_clear()


def test_strict_staging_combines_verified_identity_private_case_and_image(cross_stack):
    _, client, storage, token, attach = cross_stack
    first = attach(FIRST, "RC1-EV-FIRST")
    attach(SECOND, "RC1-EV-SECOND")

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ready").json() == {"ready": True}
    assert client.get("/api/cases").status_code == 401

    allowed = client.get("/api/cases", headers=token(SUB_VIEWER))
    assert allowed.status_code == 200, allowed.text
    assert [row["case_id"] for row in allowed.json()] == ["RC1-RC1-EV-FIRST"]

    img = client.get("/evidence/RC1-EV-FIRST.jpg", headers=token(SUB_VIEWER))
    assert img.status_code == 200, img.text
    assert "no-store" in img.headers["cache-control"]
    assert img.content == storage.objects["evidence/v1/DEMO-KA-104/RC1-EV-FIRST.jpg"]
    assert len(storage.read_keys) == 1
    assert client.get("/evidence/RC1-EV-SECOND.jpg", headers=token(SUB_VIEWER)).status_code == 404
    assert len(storage.read_keys) == 1, "Wrong-centre access must not retrieve S3 bytes"

    # A legitimate verified token with self-declared admin role remains read-only.
    assert client.post("/api/cases/RC1-RC1-EV-FIRST/review", headers=token(SUB_VIEWER),
                       json={"action": "confirmed", "note": "Forged privileged claim"}).status_code == 403

    reviewed = client.post("/api/cases/RC1-RC1-EV-FIRST/review", headers=token(SUB_REVIEWER),
                           json={"action": "confirmed", "note": "Independent synthetic officer confirmation"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "confirmed"
    assert [entry["actor"] for entry in reviewed.json()["review_history"]] == [
        "release-centre-reviewer", "release-centre-reviewer",
    ]
    assert PostgresCaseStore().get("RC1-RC1-EV-FIRST").review_history[-1]["actor"] == "release-centre-reviewer"
    assert first.sha256 not in img.text  # JPEG response never exposes evidence metadata.


def test_cross_stack_revoked_grant_and_corrupted_media_fail_closed(cross_stack, monkeypatch):
    _, client, storage, token, attach = cross_stack
    attach(FIRST, "RC1-EV-REVOKED")
    signed = token(SUB_VIEWER)
    assert client.get("/evidence/RC1-EV-REVOKED.jpg", headers=signed).status_code == 200
    monkeypatch.setenv("KAUSHALWATCH_OIDC_GRANTS_JSON", json.dumps({
        SUB_ADMIN: {"actor": "release-network-admin", "role": "network_admin", "centres": []},
    }))
    assert client.get("/api/cases", headers=signed).status_code == 403
    reads_before = len(storage.read_keys)
    assert client.get("/evidence/RC1-EV-REVOKED.jpg", headers=signed).status_code == 403
    assert len(storage.read_keys) == reads_before
    storage.objects["evidence/v1/DEMO-KA-104/RC1-EV-REVOKED.jpg"] = b"tampered"
    assert client.get("/evidence/RC1-EV-REVOKED.jpg", headers=token(SUB_ADMIN)).status_code == 503
    assert len(storage.read_keys) == reads_before + 1


def test_cross_stack_unprovisioned_or_wrong_audience_cannot_see_media(cross_stack):
    _, client, storage, token, attach = cross_stack
    attach(FIRST, "RC1-EV-DENIED")
    assert client.get("/evidence/RC1-EV-DENIED.jpg", headers=token("new-unprovisioned")).status_code == 403
    assert client.get(
        "/evidence/RC1-EV-DENIED.jpg",
        headers=token(SUB_ADMIN, claims={"aud": "api://wrong-target"}),
    ).status_code == 401
    assert storage.read_keys == []
