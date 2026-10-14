"""Private S3 evidence regression: real PostgreSQL, fake in-memory object API.

Only the isolated kaushalwatch_ci database may be mutated by these tests.
The S3 stand-in does not assert AWS IAM/KMS infrastructure compliance;
it verifies application-side access checks, immutability and SHA gating.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import ComplianceCase
from app.services.postgres_store import PostgresCaseStore
from app.services import object_evidence as obj

C1 = "DEMO-KA-104"
C2 = "DEMO-KA-112"
ADMIN_KEY = "CI_Synthetic_Officer_AccessKey_0123456789abcdef"
VIEWER_KEY = "CI_Synthetic_Viewer_AccessKey_0123456789abcdef"


class FakeObjectStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.put_requests: list[dict] = []
        self.read_requests: list[str] = []

    def put_object(self, **kw):
        assert kw["ServerSideEncryption"] == "aws:kms"
        assert kw["IfNoneMatch"] == "*"
        assert kw["ContentType"] == "image/jpeg"
        assert kw["SSEKMSKeyId"] == "alias/ci-evidence-only"
        if kw["Key"] in self.objects:
            raise RuntimeError("S3 conditional-create collision")
        self.objects[kw["Key"]] = kw["Body"]
        self.put_requests.append(kw)

    def get_object(self, **kw):
        self.read_requests.append(kw["Key"])
        if kw["Key"] not in self.objects:
            raise RuntimeError("S3 missing or unavailable")
        return {"Body": io.BytesIO(self.objects[kw["Key"]])}


    def list_objects_v2(self, **kw):
        keys = sorted(k for k in self.objects if k.startswith(kw["Prefix"]))
        start = int(kw.get("ContinuationToken", "0"))
        stop = min(len(keys), start + min(kw.get("MaxKeys", 1000), 1000))
        return {
            "Contents": [{"Key": key} for key in keys[start:stop]],
            "IsTruncated": stop < len(keys),
            **({"NextContinuationToken": str(stop)} if stop < len(keys) else {}),
        }


@pytest.fixture
def private_env(monkeypatch):
    dsn = os.getenv("KAUSHALWATCH_DATABASE_URL", "")
    if not dsn and not os.getenv("KAUSHALWATCH_TEST_DATABASE"):
        pytest.skip("Requires isolated PostgreSQL CI service")
    if os.getenv("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci" or "kaushalwatch_ci" not in dsn:
        pytest.fail("Refusing non-isolated evidence test database")
    import app.main as main
    if main.EVIDENCE_BACKEND != "s3":
        pytest.fail("Private-evidence integration requires S3 router at app import time")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_BACKEND", "s3")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_S3_BUCKET", "kaushalwatch-private-ci")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_S3_REGION", "ap-south-1")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID", "alias/ci-evidence-only")
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", (
        '{"pg-admin":"' + ADMIN_KEY + '","pg-viewer":"' + VIEWER_KEY + '"}'))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",
                       '{"pg-admin":{"role":"network_admin","centres":[]},'
                       '"pg-viewer":{"role":"centre_viewer","centres":["DEMO-KA-104"]}}')
    with psycopg.connect(dsn) as conn:
        conn.execute("TRUNCATE kw_evidence_objects, kw_cases RESTART IDENTITY")
    fake = FakeObjectStorage()
    monkeypatch.setattr(obj, "_client", lambda: fake)
    return main, fake


def _frame():
    rng = np.random.default_rng(121)
    return rng.integers(0, 255, (192, 256, 3), dtype=np.uint8)


def _create(private_env, *, evidence_id="EV-S3-001", centre_id=C1, persist_case=True):
    main, fake = private_env
    evidence = obj.persist_private_evidence(
        _frame(), evidence_id, {"centre_id": centre_id, "batch_id": "TEST-1",
                              "privacy_transform": "full_frame_blur_due_untrusted_camera"})
    if persist_case:
        PostgresCaseStore().save_if_absent(ComplianceCase(
            case_id="PG-" + evidence_id,
            centre_id=centre_id, batch_id="TEST-1",
            case_type="camera_integrity", severity="high",
            summary="Synthetic object-evidence record", evidence=[evidence]))
    return evidence


def test_private_evidence_authorized_through_original_browser_path(private_env):
    main, fake = private_env
    record = _create(private_env)
    assert record.frame_path == "object://EV-S3-001"
    assert len(fake.put_requests) == 1
    assert fake.put_requests[0]["Metadata"]["sha256"] == record.sha256
    client = TestClient(main.app)
    url = "/evidence/EV-S3-001.jpg"
    assert client.get(url).status_code == 401
    allowed = client.get(url, headers={"Authorization": "Bearer " + VIEWER_KEY})
    assert allowed.status_code == 200
    assert allowed.headers["content-type"] == "image/jpeg"
    assert allowed.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in allowed.headers["cache-control"]
    assert allowed.content == fake.objects["evidence/v1/DEMO-KA-104/EV-S3-001.jpg"]
    assert len(fake.read_requests) == 1
    assert not any(key in allowed.text for key in ("kaushalwatch-private-ci", "object://"))


def test_centre_viewer_cannot_retrieve_other_centre_evidence(private_env):
    main, fake = private_env
    _create(private_env, evidence_id="EV-S3-002", centre_id=C2)
    client = TestClient(main.app)
    response = client.get("/evidence/EV-S3-002.jpg",
                          headers={"Authorization": "Bearer " + VIEWER_KEY})
    assert response.status_code == 404
    assert fake.read_requests == []
    assert client.get("/evidence/EV-S3-002.jpg",
                      headers={"Authorization": "Bearer " + ADMIN_KEY}).status_code == 200


def test_unattached_object_never_reachable_even_by_network_admin(private_env):
    main, fake = private_env
    _create(private_env, evidence_id="EV-S3-003", persist_case=False)
    res = TestClient(main.app).get(
        "/evidence/EV-S3-003.jpg", headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert res.status_code == 404
    assert fake.read_requests == []


def test_tampered_object_blocked_not_streamed(private_env):
    main, fake = private_env
    _create(private_env, evidence_id="EV-S3-004")
    fake.objects["evidence/v1/DEMO-KA-104/EV-S3-004.jpg"] = b"corrupted-image"
    res = TestClient(main.app).get(
        "/evidence/EV-S3-004.jpg", headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert res.status_code == 503
    assert res.headers["cache-control"] == "private, no-store"
    assert b"corrupted-image" not in res.content


def test_missing_object_fails_closed_and_hides_storage_details(private_env):
    main, fake = private_env
    _create(private_env, evidence_id="EV-S3-005")
    fake.objects.clear()
    res = TestClient(main.app).get(
        "/evidence/EV-S3-005.jpg", headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert res.status_code == 503
    assert b"kaushalwatch-private-ci" not in res.content


def test_db_index_tamper_blocks_even_if_object_bytes_exist(private_env):
    main, fake = private_env
    _create(private_env, evidence_id="EV-S3-006")
    with psycopg.connect(os.environ["KAUSHALWATCH_DATABASE_URL"]) as conn:
        conn.execute("UPDATE kw_evidence_objects SET sha256 = %s WHERE evidence_id = %s",
                     ("f" * 64, "EV-S3-006"))
    res = TestClient(main.app).get(
        "/evidence/EV-S3-006.jpg", headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert res.status_code == 503
    assert fake.read_requests == []


def test_private_write_enforces_identity_privacy_and_immutable_collision(private_env):
    main, fake = private_env
    with pytest.raises(ValueError, match="unsafe"):
        obj.persist_private_evidence(_frame(), "../EV-evil", {
            "centre_id": C1, "privacy_transform": "privacy_transform"})
    with pytest.raises(ValueError, match="privacy transform"):
        obj.persist_private_evidence(_frame(), "EV-PRIVACY-1", {"centre_id": C1})
    _create(private_env, evidence_id="EV-S3-007")
    with pytest.raises(RuntimeError, match="collision"):
        _create(private_env, evidence_id="EV-S3-007")
    assert len(fake.objects) == 1


def test_duplicate_detection_is_scoped_to_centre(private_env):
    _create(private_env, evidence_id="EV-DUP-001", centre_id=C1)
    within = _create(private_env, evidence_id="EV-DUP-002", centre_id=C1)
    different = _create(private_env, evidence_id="EV-DUP-003", centre_id=C2)
    assert within.duplicate_of == "EV-DUP-001"
    assert different.duplicate_of is None


def test_missing_s3_configuration_cannot_fallback_to_disk(private_env, monkeypatch):
    monkeypatch.delenv("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID")
    with pytest.raises(RuntimeError, match="KMS"):
        obj.persist_private_evidence(_frame(), "EV-NOKMS", {
            "centre_id": C1, "privacy_transform": "full_frame_blur_due_untrusted_camera"})


def test_production_rejects_json_or_local_storage(private_env, monkeypatch):
    main, _ = private_env
    monkeypatch.setenv("KAUSHALWATCH_ENV", "pilot")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_BACKEND", "local")
    r = TestClient(main.app).get("/api/cases",
                                  headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert r.status_code == 503
    assert "private evidence storage" in r.json()["detail"]
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_BACKEND", "s3")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND", "json")
    r = TestClient(main.app).get("/api/cases",
                                  headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert r.status_code == 503


def test_s3_evidence_does_not_become_public_in_local_demo_mode(private_env, monkeypatch):
    main, fake = private_env
    _create(private_env, evidence_id="EV-LOCAL-DENY")
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    response = TestClient(main.app).get("/evidence/EV-LOCAL-DENY.jpg")
    assert response.status_code == 503
    assert fake.read_requests == []


def test_pilot_requires_valid_kms_configuration_for_sensitive_routes(private_env, monkeypatch):
    main, _ = private_env
    monkeypatch.setenv("KAUSHALWATCH_ENV", "pilot")
    monkeypatch.delenv("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID")
    response = TestClient(main.app).get(
        "/api/cases", headers={"Authorization": "Bearer " + ADMIN_KEY})
    assert response.status_code == 503
    assert response.json()["detail"] == "Private evidence storage is not configured."

def test_evidence_inventory_is_read_only_and_detects_orphans(private_env):
    from app.services.evidence_inventory import audit_private_evidence
    _, fake = private_env
    _create(private_env, evidence_id="EV-INV-001")
    baseline = audit_private_evidence()
    assert baseline["status"] == "consistent"
    assert baseline["counts"]["case_evidence_ids"] == 1
    assert all(v == 0 for v in baseline["findings"].values())
    _create(private_env, evidence_id="EV-INV-002", persist_case=False)
    fake.objects["evidence/v1/DEMO-KA-104/EV-ORPHAN.jpg"] = b"orphan"
    findings = audit_private_evidence()
    assert findings["status"] == "attention"
    assert findings["findings"]["index_without_case"] == 1
    assert findings["findings"]["object_without_index"] == 1
    assert findings["read_only"] and len(fake.objects) == 3


def test_inventory_detects_corrupt_index_and_missing_objects(private_env):
    from app.services.evidence_inventory import audit_private_evidence
    _, fake = private_env
    _create(private_env, evidence_id="EV-INV-MISS")
    fake.objects.clear()
    assert audit_private_evidence()["findings"]["index_without_object"] == 1
    fake.objects["evidence/v1/DEMO-KA-104/EV-INV-MISS.jpg"] = b"returned"
    with psycopg.connect(os.environ["KAUSHALWATCH_DATABASE_URL"]) as db:
        db.execute("UPDATE kw_evidence_objects SET sha256 = %s WHERE evidence_id = %s",
                   ("e" * 64, "EV-INV-MISS"))
    assert audit_private_evidence()["findings"]["mismatched_identity_or_digest"] == 1


def test_inventory_scanning_fails_when_incomplete(private_env):
    from app.services.evidence_inventory import audit_private_evidence
    _, fake = private_env
    _create(private_env, evidence_id="EV-INV-NOIDX")
    with psycopg.connect(os.environ["KAUSHALWATCH_DATABASE_URL"]) as db:
        db.execute("DELETE FROM kw_evidence_objects WHERE evidence_id=%s",
                   ("EV-INV-NOIDX",))
    findings = audit_private_evidence()
    assert findings["findings"]["case_without_index"] == 1
    assert findings["findings"]["object_without_index"] == 1
    fake.objects["evidence/v1/DEMO-KA-104/EV-EXTRA.jpg"] = b"untracked"
    with pytest.raises(RuntimeError, match="audit bound"):
        audit_private_evidence(limit=1)


def test_pilot_readiness_checks_schema_db_and_liveness(private_env, monkeypatch):
    main, _ = private_env
    # Synthetic static-key staging can verify DB/schema health; real pilots
    # additionally require signed OIDC subjects, so cannot claim ready.
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    client = TestClient(main.app)
    response = client.get("/api/ready")
    assert response.status_code == 200, response.text
    assert response.json() == {"ready": True}
    assert client.get("/api/health").status_code == 200
    monkeypatch.setenv("KAUSHALWATCH_ENV", "pilot")
    assert client.get("/api/ready").status_code == 503
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_DATABASE_URL",
                       "postgresql://ci:invalid@127.0.0.1:1/kaushalwatch_ci")
    failing = client.get("/api/ready")
    assert failing.status_code == 503
    assert failing.json() == {"ready": False}
    assert "postgresql://" not in failing.text
    assert client.get("/api/health").status_code == 200


def test_staging_postgres_readiness_refuses_missing_officer_config(private_env, monkeypatch):
    main, _ = private_env
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.delenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON")
    assert TestClient(main.app).get("/api/ready").status_code == 503
