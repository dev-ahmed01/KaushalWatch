"""Synthetic private-reference images with real disposable PostgreSQL records.

No test data is sent to real S3; a local fake captures conditional KMS writes.
"""
from __future__ import annotations

import io
import os
from uuid import uuid4

import cv2
import numpy as np
import pytest

from app.services.officer_permissions import OfficerPrincipal
from app.services.postgres_store import connection
from app.services.protected_camera_reference import (
    CameraReferenceConflict, ProtectedCameraReferenceWorkflow,
)
import app.services.camera_reference_artifacts as artifact

pytestmark = pytest.mark.skipif(
    os.getenv("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci",
    reason="Only run reference-artifact integration against disposable PostgreSQL CI",
)
CENTRE = "DEMO-KA-104"
PROPOSER = OfficerPrincipal("ci-image-operator","centre_reviewer",frozenset({CENTRE}))
REVIEWER = OfficerPrincipal("ci-image-admin","network_admin",frozenset())
VIEWER = OfficerPrincipal("ci-image-viewer","centre_viewer",frozenset({CENTRE}))
STRANGER = OfficerPrincipal("ci-other","centre_reviewer",frozenset({"DEMO-KA-112"}))


class FakeS3:
    def __init__(self):
        self.objects={}
        self.uploads=[]
    def put_object(self, **kwargs):
        assert kwargs["IfNoneMatch"] == "*"
        assert kwargs["ServerSideEncryption"] == "aws:kms"
        assert kwargs["SSEKMSKeyId"] == "alias/ci-camera-reference"
        assert kwargs["CacheControl"] == "private, no-store"
        key=(kwargs["Bucket"],kwargs["Key"])
        assert key not in self.objects
        self.objects[key]=kwargs["Body"]
        self.uploads.append(kwargs)
    def get_object(self, **kwargs):
        return {"Body":io.BytesIO(self.objects[(kwargs["Bucket"],kwargs["Key"])])}


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow_artifact")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_BUCKET","private-ci-camera-references")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_REGION","ap-south-1")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_KMS_KEY_ID","alias/ci-camera-reference")
    client=FakeS3()
    monkeypatch.setattr(artifact,"_client",lambda:client)
    return client,ProtectedCameraReferenceWorkflow()


def sample():
    frame=np.zeros((96,128,3),dtype=np.uint8)
    frame[:,:,0]=np.arange(128,dtype=np.uint8)[None,:]
    frame[:,:,1]=np.arange(96,dtype=np.uint8)[:,None]
    frame[:,:,2]=160
    ok,png=cv2.imencode(".png",frame)
    assert ok
    return png.tobytes(),frame


def registered(workflow,content):
    camera="CI-REF-"+uuid4().hex[:20]
    _,_,pixel_sha,_=artifact.normalize_image(content)
    proposal=workflow.propose(
        principal=PROPOSER,centre_id=CENTRE,camera_id=camera,
        reference_digest=pixel_sha,capture_id="capture-ci",
        source_review_id="source-ci",expected_revision=0,
    )
    return camera,proposal


def test_private_reference_attach_verify_review_and_revoke(store):
    client, workflow = store
    data,frame=sample()
    camera,proposal=registered(workflow,data)
    assert proposal["artifact_attached"] is False
    with pytest.raises(CameraReferenceConflict,match="Matching private"):
        workflow.review(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
            expected_revision=1,independent_review_id="second-review",
            verified_healthy=True,verified_same_view=True,
            compared_independently=True,
        )
    saved=artifact.attach_reference_image(
        principal=PROPOSER,centre_id=CENTRE,camera_id=camera,
        expected_revision=1,content=data,
    )
    assert saved["attached"] is True
    assert saved["production_binding"] is False
    assert saved["provenance_verified"] is False
    assert client.uploads[0]["Key"].startswith(
        "camera-references/v1/DEMO-KA-104/"+camera+"/r1/"
    )
    assert workflow.get(principal=VIEWER,centre_id=CENTRE,camera_id=camera)["artifact_attached"]
    retrieved,encoded=artifact.verified_reference_frame(
        principal=REVIEWER,centre_id=CENTRE,camera_id=camera,expected_revision=1,
    )
    np.testing.assert_array_equal(retrieved,frame)
    assert encoded==client.uploads[0]["Body"]
    with pytest.raises(artifact.CameraReferencePolicyError):
        artifact.verified_reference_frame(
            principal=VIEWER,centre_id=CENTRE,camera_id=camera,expected_revision=1,
        )
    with pytest.raises(artifact.CameraReferencePolicyError):
        artifact.verified_reference_frame(
            principal=STRANGER,centre_id=CENTRE,camera_id=camera,expected_revision=1,
        )
    reviewed=workflow.review(
        principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
        expected_revision=1,independent_review_id="second-review",
        verified_healthy=True,verified_same_view=True,
        compared_independently=True,
    )
    assert reviewed["state"]=="REVIEWED_NOT_BOUND"
    assert reviewed["actual_reference_verified"] is False
    workflow.suspend(
        principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
        expected_revision=1,reason="Reference has been suspended",
    )
    with pytest.raises(CameraReferenceConflict,match="not in a reviewable state"):
        artifact.verified_reference_frame(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,expected_revision=1,
        )


def test_private_artifact_is_one_time_and_fingerprint_checked(store):
    client, workflow=store
    data,frame=sample()
    camera,proposal=registered(workflow,data)
    altered=frame.copy()
    altered[5,5,0]^=1
    ok,png=cv2.imencode(".png",altered)
    assert ok
    with pytest.raises(CameraReferenceConflict,match="SHA-256 mismatch"):
        artifact.attach_reference_image(
            principal=PROPOSER,centre_id=CENTRE,camera_id=camera,
            expected_revision=1,content=png.tobytes(),
        )
    assert not client.objects
    artifact.attach_reference_image(
        principal=PROPOSER,centre_id=CENTRE,camera_id=camera,expected_revision=1,content=data,
    )
    with pytest.raises(CameraReferenceConflict,match="already attached"):
        artifact.attach_reference_image(
            principal=PROPOSER,centre_id=CENTRE,camera_id=camera,expected_revision=1,content=data,
        )
    with connection() as db:
        with pytest.raises(Exception,match="artifact index cannot be changed"):
            db.execute(
                "DELETE FROM kw_camera_reference_artifacts "
                "WHERE centre_id=%s AND camera_id=%s",(CENTRE,camera),
            )


def test_s3_corruption_blocks_independent_review_and_preview(store):
    client, workflow=store
    data,_=sample()
    camera,_=registered(workflow,data)
    artifact.attach_reference_image(
        principal=PROPOSER,centre_id=CENTRE,camera_id=camera,expected_revision=1,content=data,
    )
    key=next(iter(client.objects))
    client.objects[key]=client.objects[key]+b"malicious-trailing-bytes"
    with pytest.raises(CameraReferenceConflict,match="integrity"):
        artifact.verified_reference_frame(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,expected_revision=1,
        )
    with pytest.raises(CameraReferenceConflict,match="integrity"):
        workflow.review(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
            expected_revision=1,independent_review_id="review-untrusted",
            verified_healthy=True,verified_same_view=True,
            compared_independently=True,
        )
    assert workflow.get(principal=REVIEWER,centre_id=CENTRE,camera_id=camera)["state"] == "PENDING_REVIEW"


@pytest.mark.parametrize("data",[
    b"","definitely-not-an-image",b"\xff\xd8\xffnot-jpeg",
    b"x"*(2*1024*1024+1),
])
def test_malformed_or_excessive_images_rejected(data):
    with pytest.raises(artifact.CameraReferencePolicyError):
        artifact.normalize_image(data)


def test_digest_includes_dimensions_and_pixels():
    data,frame=sample()
    _,_,sha1,_=artifact.normalize_image(data)
    assert sha1==artifact.pixel_digest(frame)
    changed=frame.copy()
    changed[0,0,0]^=1
    assert artifact.pixel_digest(changed)!=sha1
