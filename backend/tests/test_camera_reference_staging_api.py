"""Security-focused synthetic tests of Phase 3G staging-only API contract."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

import app.camera_reference_routes as routes
from app.services.officer_permissions import OfficerPrincipal


CENTRE="DEMO-KA-104"
BASE="/api/centres/"+CENTRE+"/camera-reference"
REVIEWER=OfficerPrincipal("centre-officer","centre_reviewer",frozenset({CENTRE}))
ADMIN=OfficerPrincipal("network-officer","network_admin",frozenset())
VIEWER=OfficerPrincipal("viewer","centre_viewer",frozenset({CENTRE}))
OTHER=OfficerPrincipal("another-centre","centre_reviewer",frozenset({"DEMO-KA-112"}))


class FakeWorkflow:
    calls = []
    def get(self, **kwargs):
        self.calls.append(("read", kwargs))
        return {"centre_id":kwargs["centre_id"],"camera_id":kwargs["camera_id"],
                "state":"UNENROLLED","revision":0,"production_binding":False,
                "actual_reference_verified":False}
    def propose(self, **kwargs):
        from app.services.protected_camera_reference import _actor
        _actor(kwargs["principal"], kwargs["centre_id"], "centre_reviewer")
        self.calls.append(("propose",kwargs))
        return {"state":"PENDING_REVIEW","revision":1,"production_binding":False,
                "actual_reference_verified":False}
    def review(self, **kwargs):
        from app.services.protected_camera_reference import _actor
        _actor(kwargs["principal"], kwargs["centre_id"], "network_admin")
        self.calls.append(("review",kwargs))
        return {"state":"REVIEWED_NOT_BOUND","revision":1,
                "production_binding":False,"actual_reference_verified":False}
    def suspend(self, **kwargs):
        from app.services.protected_camera_reference import _actor
        _actor(kwargs["principal"], kwargs["centre_id"], "network_admin")
        self.calls.append(("suspend",kwargs))
        return {"state":"SUSPENDED","revision":1,
                "production_binding":False,"actual_reference_verified":False}


@pytest.fixture
def app(monkeypatch):
    FakeWorkflow.calls=[]
    monkeypatch.setattr(routes, "ProtectedCameraReferenceWorkflow", FakeWorkflow)
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","token")
    api=FastAPI()
    principal=[None]
    @api.middleware("http")
    async def simulate_pre_authenticated_principal(request: Request, call_next):
        if principal[0] is not None:
            request.state.officer_principal=principal[0]
        return await call_next(request)
    api.include_router(routes.router)
    api.state.stub_principal=principal
    return api


def test_feature_disabled_for_all_demo_or_nonstaging_environments(app, monkeypatch):
    app.state.stub_principal[0]=ADMIN
    with TestClient(app) as client:
        monkeypatch.delenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW")
        assert client.get(BASE).status_code==404
        monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow")
        monkeypatch.setenv("KAUSHALWATCH_ENV","development")
        assert client.get(BASE).status_code==404
        monkeypatch.setenv("KAUSHALWATCH_ENV","production")
        assert client.get(BASE).status_code==404
    assert FakeWorkflow.calls==[]


def test_no_client_supplied_actor_can_replace_verified_session(app):
    with TestClient(app) as client:
        response=client.get(BASE,headers={"X-Officer-Actor":"network-officer"})
        assert response.status_code==401
        response=client.post(BASE+"/propose",json={
            "reference_digest":"a"*64,"capture_id":"c1",
            "source_review_id":"s1","expected_revision":0,"actor":"network-officer",
        })
        assert response.status_code==401
    assert FakeWorkflow.calls==[]


def test_centre_scope_does_not_leak_reference(app):
    app.state.stub_principal[0]=OTHER
    with TestClient(app) as client:
        assert client.get(BASE).status_code==404
        assert client.post(BASE+"/propose",json={
            "reference_digest":"a"*64,"capture_id":"c1",
            "source_review_id":"s1","expected_revision":0,
        }).status_code==404
        assert client.get("/api/centres/UNKNOWN/camera-reference").status_code==404
    assert FakeWorkflow.calls==[]


def test_viewer_gets_read_only_reference(app):
    app.state.stub_principal[0]=VIEWER
    with TestClient(app) as client:
        value=client.get(BASE)
        assert value.status_code==200
        assert value.json()["production_binding"] is False
        response=client.post(BASE+"/propose",json={
            "reference_digest":"a"*64,"capture_id":"c1",
            "source_review_id":"s1","expected_revision":0,
        })
        assert response.status_code==403
    assert [item[0] for item in FakeWorkflow.calls]==["read"]


def test_proposal_does_not_accept_actor_or_role_from_body(app):
    app.state.stub_principal[0]=REVIEWER
    with TestClient(app) as client:
        assert client.post(BASE+"/propose",json={
            "reference_digest":"a"*64,"capture_id":"capture",
            "source_review_id":"review","expected_revision":0,
            "actor":"network-officer","role":"network_admin",
        }).status_code==422
        assert client.post(BASE+"/propose",json={
            "reference_digest":"a"*64,"capture_id":"capture",
            "source_review_id":"review","expected_revision":0,
        }).status_code==200
    assert len(FakeWorkflow.calls)==1
    assert FakeWorkflow.calls[0][1]["principal"]==REVIEWER
    assert FakeWorkflow.calls[0][1]["camera_id"]=="LAB-CAM-01"


def test_review_and_suspension_use_session_role_not_supplied_role(app):
    app.state.stub_principal[0]=ADMIN
    with TestClient(app) as client:
        response=client.post(BASE+"/review",json={
            "expected_revision":1,"independent_review_id":"review-2",
            "verified_healthy":True,"verified_same_view":True,
            "compared_independently":True,
        })
        assert response.status_code==200
        assert response.json()["state"]=="REVIEWED_NOT_BOUND"
        assert response.json()["production_binding"] is False
        assert client.post(BASE+"/suspend",json={
            "expected_revision":1,"reason":"needs verification",
        }).status_code==200
    assert [c[0] for c in FakeWorkflow.calls]==["review","suspend"]
    assert all(c[1]["principal"]==ADMIN for c in FakeWorkflow.calls)


def test_real_domain_role_gate_denies_viewer_writes():
    from app.services.protected_camera_reference import _actor, CameraReferencePolicyError
    with pytest.raises(CameraReferencePolicyError,match="role"):
        _actor(VIEWER,CENTRE,"centre_reviewer")
    with pytest.raises(CameraReferencePolicyError,match="role"):
        _actor(REVIEWER,CENTRE,"network_admin")
    assert _actor(ADMIN,CENTRE,"network_admin")=="network-officer"
