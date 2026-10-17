"""Actual protected FastAPI + disposable PostgreSQL + fake S3 image workflow.

All pixels are synthetic. No live network/object storage endpoint is called.
"""
from __future__ import annotations

import io
import json
import os
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.services.camera_reference_artifacts as artifacts

pytestmark = pytest.mark.skipif(
    os.getenv("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci",
    reason="Requires explicitly isolated PostgreSQL CI database",
)

CENTRE = "DEMO-KA-104"
BASE = f"/api/centres/{CENTRE}/camera-reference"
TOKENS = {
    "ref-camera-op": "CI_Phase3H_Operator_Token_0123456789abcdef",
    "ref-camera-admin": "CI_Phase3H_Admin_Token_0123456789abcdef",
    "ref-camera-viewer": "CI_Phase3H_Viewer_Token_0123456789abcdef",
    "ref-camera-other": "CI_Phase3H_Other_Token_0123456789abcdef",
}


class FakeS3:
    def __init__(self):
        self.storage = {}
    def put_object(self, **kwargs):
        assert kwargs["IfNoneMatch"] == "*"
        assert kwargs["ServerSideEncryption"] == "aws:kms"
        assert kwargs["SSEKMSKeyId"] == "alias/reference-ci"
        identity = (kwargs["Bucket"],kwargs["Key"])
        assert identity not in self.storage
        self.storage[identity] = kwargs["Body"]
    def get_object(self, **kwargs):
        return {"Body":io.BytesIO(self.storage[kwargs["Bucket"],kwargs["Key"]])}


def auth(actor: str) -> dict:
    return {"Authorization":"Bearer "+TOKENS[actor]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","token")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow_artifact")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_BUCKET","ci-locked-reference-image-store")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_S3_REGION","ap-south-1")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_KMS_KEY_ID","alias/reference-ci")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",json.dumps(TOKENS))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",json.dumps({
        "ref-camera-op":{"role":"centre_reviewer","centres":[CENTRE]},
        "ref-camera-admin":{"role":"network_admin","centres":[]},
        "ref-camera-viewer":{"role":"centre_viewer","centres":[CENTRE]},
        "ref-camera-other":{"role":"centre_reviewer","centres":["DEMO-KA-112"]},
    }))
    fake = FakeS3()
    monkeypatch.setattr(artifacts,"_client",lambda:fake)
    with TestClient(app) as c:
        yield c,fake


def test_protected_image_proposal_preview_review_suspension(client):
    api,s3=client
    synthetic = np.empty((96,128,3), dtype=np.uint8)
    synthetic[:,:,0] = np.arange(128, dtype=np.uint8)
    synthetic[:,:,1] = np.arange(96,dtype=np.uint8)[:,None]
    synthetic[:,:,2] = 130
    ok,png = cv2.imencode(".png",synthetic)
    assert ok
    image=png.tobytes()
    params={
        "expected_revision":0,"capture_id":"capture-"+uuid4().hex[:12],
        "source_review_id":"source-"+uuid4().hex[:12],
    }
    assert api.post(BASE+"/propose-image",params=params,content=image,
                    headers={"Content-Type":"image/png"}).status_code==401
    assert api.post(BASE+"/propose-image",params=params,content=image,
                    headers={**auth("ref-camera-viewer"),"Content-Type":"image/png"}).status_code==403
    assert api.post(BASE+"/propose-image",params=params,content=image,
                    headers={**auth("ref-camera-other"),"Content-Type":"image/png"}).status_code==404
    proposal=api.post(BASE+"/propose-image",params=params,content=image,
                      headers={**auth("ref-camera-op"),"Content-Type":"image/png"})
    assert proposal.status_code==200,proposal.text
    payload=proposal.json()
    assert payload["state"]=="PENDING_REVIEW"
    assert payload["artifact_attached"] is True
    assert payload["actual_reference_verified"] is False
    assert payload["production_binding"] is False
    assert len(s3.storage)==1
    assert api.get(BASE+"/frame",params={"expected_revision":1},
                   headers=auth("ref-camera-viewer")).status_code==403
    image_response=api.get(BASE+"/frame",params={"expected_revision":1},
                           headers=auth("ref-camera-admin"))
    assert image_response.status_code==200,image_response.text[:100]
    assert image_response.headers["cache-control"].startswith("private, no-store")
    decoded=cv2.imdecode(np.frombuffer(image_response.content,dtype=np.uint8),
                         cv2.IMREAD_COLOR)
    np.testing.assert_array_equal(decoded,synthetic)
    review={
        "expected_revision":1,"independent_review_id":"independent-"+uuid4().hex[:12],
        "verified_healthy":True,"verified_same_view":True,
        "compared_independently":True,
    }
    assert api.post(BASE+"/review",json=review,headers=auth("ref-camera-op")).status_code==403
    accepted=api.post(BASE+"/review",json=review,headers=auth("ref-camera-admin"))
    assert accepted.status_code==200,accepted.text
    assert accepted.json()["state"]=="REVIEWED_NOT_BOUND"
    assert accepted.json()["production_binding"] is False
    suspended=api.post(BASE+"/suspend",
         json={"expected_revision":1,"reason":"Inspect suspect viewpoint"},
         headers=auth("ref-camera-admin"))
    assert suspended.status_code==200,suspended.text
    assert api.get(BASE+"/frame",params={"expected_revision":1},
                   headers=auth("ref-camera-admin")).status_code==409


def test_disabled_and_malformed_image_requests_never_write(client,monkeypatch):
    api,s3=client
    params={"expected_revision":0,"capture_id":"a","source_review_id":"b"}
    denied=api.post(BASE+"/propose-image",params=params,content=b"not-image",
                    headers={**auth("ref-camera-op"),"Content-Type":"application/json"})
    assert denied.status_code==415
    over_limit=api.post(BASE+"/propose-image",params=params,
        content=b"x"*(artifacts.MAX_UPLOAD_BYTES+1),
        headers={**auth("ref-camera-op"),"Content-Type":"image/png"})
    assert over_limit.status_code==413
    assert not s3.storage
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow")
    assert api.post(BASE+"/propose-image",params=params,content=b"x",
                    headers={**auth("ref-camera-op"),"Content-Type":"image/png"}).status_code==404
    assert api.get(BASE+"/frame",params={"expected_revision":1},
                   headers=auth("ref-camera-admin")).status_code==404
