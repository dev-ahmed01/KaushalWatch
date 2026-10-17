"""Actual PostgreSQL + simulated private S3, synthetic fixed-reference offline tests."""
from __future__ import annotations

import io
import os
from uuid import uuid4

import cv2
import numpy as np
import pytest

from app.services.officer_permissions import OfficerPrincipal
from app.services.protected_camera_reference import (
    ProtectedCameraReferenceWorkflow, CameraReferenceConflict,
    CameraReferencePolicyError,
)
from app.services.camera_reference_artifacts import (
    normalize_image, attach_reference_image,
)
import app.services.camera_reference_artifacts as artifacts
from app.services.camera_reference_offline_session import OfflineApprovedReferenceSession


pytestmark = pytest.mark.skipif(
    os.getenv("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci",
    reason="Disposable PostgreSQL CI required; never touch real camera references",
)
CENTRE="DEMO-KA-104"
OP=OfficerPrincipal("ci-offline-proposer","centre_reviewer",frozenset({CENTRE}))
ADMIN=OfficerPrincipal("ci-offline-independent","network_admin",frozenset())
VIEWER=OfficerPrincipal("ci-offline-viewer","centre_viewer",frozenset({CENTRE}))


class S3:
    def __init__(self):
        self.items = {}
    def put_object(self, **kw):
        assert kw["ServerSideEncryption"] == "aws:kms"
        assert kw["IfNoneMatch"] == "*"
        assert (kw["Bucket"],kw["Key"]) not in self.items
        self.items[(kw["Bucket"],kw["Key"])] = kw["Body"]
    def get_object(self, **kw):
        return {"Body":io.BytesIO(self.items[(kw["Bucket"],kw["Key"])])}


@pytest.fixture
def prepared(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow_artifact")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_BUCKET","ci-offline-private-reference")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_REGION","ap-south-1")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_KMS_KEY_ID","alias/ci-reference")
    private = S3()
    monkeypatch.setattr(artifacts,"_client",lambda:private)
    rng=np.random.default_rng(901)
    frame=rng.integers(25,230,size=(144,192,3),dtype=np.uint8)
    ok,encoded=cv2.imencode(".png",frame)
    assert ok
    image=encoded.tobytes()
    sha=normalize_image(image)[2]
    camera="CI-OFFLINE-"+uuid4().hex[:16]
    workflow=ProtectedCameraReferenceWorkflow()
    pending=workflow.propose(
        principal=OP,centre_id=CENTRE,camera_id=camera,expected_revision=0,
        reference_digest=sha,capture_id="ci-verified-source",
        source_review_id="ci-independent-capture-ticket",
    )
    assert pending["state"] == "PENDING_REVIEW"
    attach_reference_image(
        principal=OP,centre_id=CENTRE,camera_id=camera,
        expected_revision=1,content=image,
    )
    return private,workflow,camera,frame


def review(workflow,camera):
    return workflow.review(
        principal=ADMIN,centre_id=CENTRE,camera_id=camera,expected_revision=1,
        independent_review_id="ci-independent-inspection",
        verified_healthy=True,verified_same_view=True,
        compared_independently=True,
    )


def test_unreviewed_reference_never_starts_offline(prepared):
    _,workflow,camera,frame=prepared
    with pytest.raises(CameraReferenceConflict,match="Independently reviewed"):
        OfflineApprovedReferenceSession.open(
            principal=ADMIN,centre_id=CENTRE,camera_id=camera,revision=1
        )
    with pytest.raises(CameraReferencePolicyError,match="network administrator"):
        OfflineApprovedReferenceSession.open(
            principal=VIEWER,centre_id=CENTRE,camera_id=camera,revision=1
        )


def test_fixed_reference_is_used_without_learning_from_first_video_frame(prepared):
    _,workflow,camera,frame=prepared
    review(workflow,camera)
    session=OfflineApprovedReferenceSession.open(
        principal=ADMIN,centre_id=CENTRE,camera_id=camera,revision=1
    )
    assert session.probe.spatial.temporary_reference is not None
    assert session.probe.persistent.temporary_reference is not None
    assert not session.probe.spatial.warmup
    assert not session.probe.persistent.initial_frames
    first=session.observe(frame,1.0)
    assert first["decision"] != "WARMUP"
    assert first["production_integration"] is False
    assert first["attendance_action"] == "NOT_AUTHORIZED"
    assert first["compliance_action"] == "NOT_AUTHORIZED"
    assert first["reference_provenance_independently_verified"] is False
    assert first["reference_sha256"] == workflow.get(
        principal=ADMIN,centre_id=CENTRE,camera_id=camera
    )["reference_digest"]
    assert session.samples == 1


def test_offline_session_stops_on_suspension_and_never_reenrolls(prepared):
    _,workflow,camera,frame=prepared
    review(workflow,camera)
    session=OfflineApprovedReferenceSession.open(
        principal=ADMIN,centre_id=CENTRE,camera_id=camera,revision=1
    )
    session.observe(frame,1)
    before=session.samples
    workflow.suspend(
        principal=ADMIN,centre_id=CENTRE,camera_id=camera,expected_revision=1,
        reason="test reference suspension",
    )
    with pytest.raises(CameraReferenceConflict,match="session closed"):
        session.observe(frame,1)
    assert session.samples==before
    assert session.closed
    with pytest.raises(CameraReferenceConflict,match="closed"):
        session.observe(frame,1)
    with pytest.raises(CameraReferenceConflict):
        OfflineApprovedReferenceSession.open(
            principal=ADMIN,centre_id=CENTRE,camera_id=camera,revision=1
        )


def test_tampered_artifact_denies_initial_binding(prepared):
    private,workflow,camera,frame=prepared
    review(workflow,camera)
    key=next(iter(private.items))
    private.items[key]=b"altered-object"
    with pytest.raises(CameraReferenceConflict,match="integrity"):
        OfflineApprovedReferenceSession.open(
            principal=ADMIN,centre_id=CENTRE,camera_id=camera,revision=1
        )


def test_session_rejects_malformed_frames_without_advancing(prepared):
    _,workflow,camera,frame=prepared
    review(workflow,camera)
    session=OfflineApprovedReferenceSession.open(
        principal=ADMIN,centre_id=CENTRE,camera_id=camera,revision=1
    )
    with pytest.raises(CameraReferencePolicyError):
        session.observe(frame.astype(np.float32),1)
    with pytest.raises(CameraReferencePolicyError):
        session.observe(frame,float("nan"))
    assert session.samples == 0
    assert session.probe.spatial.elapsed==0
    assert session.probe.persistent.elapsed==0
