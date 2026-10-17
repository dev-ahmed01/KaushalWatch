"""Actual protected FastAPI middleware integration for reference routes.

No DB, real officer-token->principal mapping, centre scope and method policy.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

import app.camera_reference_routes as routes
from app.main import app
from app.services.protected_camera_reference import _actor

BASE="/api/centres/DEMO-KA-104/camera-reference"
KEY_ADMIN="CI_Staging_Network_Admin_Token_0123456789abcdef"
KEY_REVIEWER="CI_Staging_Centre_Reviewer_Token_0123456789abcdef"
KEY_VIEWER="CI_Staging_Centre_Viewer_Token_0123456789abcdef"
KEY_OTHER="CI_Staging_Other_Centre_Token_0123456789abcdef"
PAYLOAD={
    "reference_digest":"a"*64, "capture_id":"ci-capture",
    "source_review_id":"ci-source", "expected_revision":0,
}


class StubWorkflow:
    calls=[]
    def get(self, **kwargs):
        self.calls.append(("get",kwargs["principal"].actor,kwargs["camera_id"]))
        return {"state":"UNENROLLED","revision":0,"production_binding":False}
    def propose(self, **kwargs):
        _actor(kwargs["principal"],kwargs["centre_id"],"centre_reviewer")
        self.calls.append(("propose",kwargs["principal"].actor,kwargs["camera_id"]))
        return {"state":"PENDING_REVIEW","revision":1,"production_binding":False}
    def review(self, **kwargs):
        _actor(kwargs["principal"],kwargs["centre_id"],"network_admin")
        self.calls.append(("review",kwargs["principal"].actor,kwargs["camera_id"]))
        return {"state":"REVIEWED_NOT_BOUND","revision":1,"production_binding":False}


@pytest.fixture
def client(monkeypatch):
    StubWorkflow.calls=[]
    monkeypatch.setattr(routes,"ProtectedCameraReferenceWorkflow",StubWorkflow)
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","token")
    tokens={
        "staging-admin":KEY_ADMIN, "staging-reviewer":KEY_REVIEWER,
        "staging-viewer":KEY_VIEWER, "staging-other":KEY_OTHER,
    }
    principals={
        "staging-admin":{"role":"network_admin","centres":[]},
        "staging-reviewer":{"role":"centre_reviewer","centres":["DEMO-KA-104"]},
        "staging-viewer":{"role":"centre_viewer","centres":["DEMO-KA-104"]},
        "staging-other":{"role":"centre_reviewer","centres":["DEMO-KA-112"]},
    }
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",json.dumps(tokens))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",json.dumps(principals))
    with TestClient(app) as test:
        yield test


def auth(key):
    return {"Authorization":"Bearer "+key}


def test_actual_middleware_denies_anonymous_and_off_centre(client):
    assert client.get(BASE).status_code==401
    assert client.get(BASE,headers=auth(KEY_OTHER)).status_code==404
    assert client.post(BASE+"/propose",json=PAYLOAD,headers=auth(KEY_OTHER)).status_code==404
    assert not StubWorkflow.calls


def test_actual_middleware_readonly_role_and_strict_body(client):
    assert client.get(BASE,headers=auth(KEY_VIEWER)).status_code==200
    assert client.post(BASE+"/propose",json=PAYLOAD,headers=auth(KEY_VIEWER)).status_code==403
    assert client.post(BASE+"/propose",json={**PAYLOAD,"actor":"staging-admin"},
        headers=auth(KEY_REVIEWER)).status_code==422
    assert client.post(BASE+"/propose",json=PAYLOAD,headers=auth(KEY_REVIEWER)).status_code==200
    assert StubWorkflow.calls[-1]==("propose","staging-reviewer","LAB-CAM-01")


def test_approval_requires_different_role_even_after_authentication(client):
    body={
        "expected_revision":1,"independent_review_id":"independent-1",
        "verified_healthy":True,"verified_same_view":True,"compared_independently":True,
    }
    assert client.post(BASE+"/review",json=body,headers=auth(KEY_REVIEWER)).status_code==403
    approved=client.post(BASE+"/review",json=body,headers=auth(KEY_ADMIN))
    assert approved.status_code==200
    assert approved.json()["production_binding"] is False
    assert StubWorkflow.calls[-1]==("review","staging-admin","LAB-CAM-01")


def test_disabled_feature_rejects_authenticated_sessions(client,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","off")
    assert client.get(BASE,headers=auth(KEY_ADMIN)).status_code==404
    assert client.post(BASE+"/propose",json=PAYLOAD,headers=auth(KEY_REVIEWER)).status_code==404
