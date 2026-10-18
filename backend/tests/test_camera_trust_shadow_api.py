"""Synthetic route authorization and source-pin checks; no actual media."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app.main as main
from app.services import camera_trust_store as store

CENTRE="DEMO-KA-104"
OTHER="DEMO-KA-112"
TOKENS={
    "admin-key":"KWCameraSyntheticAdmin_abcdefghijklmnopqrstuvwxyz123456",
    "review-key":"KWCameraSyntheticReview_abcdefghijklmnopqrstuvwxyz123456",
    "view-key":"KWCameraSyntheticViewer_abcdefghijklmnopqrstuvwxyz123456",
}
GRANTS={
    "admin-key":{"role":"network_admin","centres":[]},
    "review-key":{"role":"centre_reviewer","centres":[CENTRE]},
    "view-key":{"role":"centre_viewer","centres":[CENTRE]},
}
def headers(actor):
    return {"Authorization":"Bearer "+TOKENS[actor]}

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",json.dumps(TOKENS))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",json.dumps(GRANTS))
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setattr(store,"list_cameras",lambda centre_id: [])
    return TestClient(main.app)

def test_authentication_scope_and_read_only_mutations(client):
    url=f"/api/centres/{CENTRE}/camera-trust"
    assert client.get(url).status_code==401
    response=client.get(url,headers=headers("review-key"))
    assert response.status_code==200
    assert response.json()["release_gate"]=="NOT_PRODUCTION_QUALIFIED"
    assert response.json()["operational_mutation_enabled"] is False
    assert client.get(f"/api/centres/{OTHER}/camera-trust",
                      headers=headers("view-key")).status_code==404
    assert client.post(url+"/cameras",headers=headers("view-key"),
                       json={"label":"Test camera","source_alias":"synthetic.avi"}).status_code==403
    assert client.get(url,headers={"Authorization":"Bearer invalid"}).status_code==401

def test_postgres_must_be_explicitly_selected(client,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","json")
    assert client.get(f"/api/centres/{CENTRE}/camera-trust",
                      headers=headers("admin-key")).status_code==503

def test_unpinned_alias_denied_in_authorized_context(client,monkeypatch,tmp_path):
    manifest=tmp_path/"sources.json"
    manifest.write_text(json.dumps({"version":"KWTRUST_DRIVE_ASSETS_V1",
                                    "files":[{"name":"camera.avi","id":"A"*25,"group":"full-videos"}]}))
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_DRIVE_MANIFEST",str(manifest))
    response=client.post(f"/api/centres/{CENTRE}/camera-trust/cameras",
                      headers=headers("review-key"),
                      json={"label":"Synthetic camera","source_alias":"camera.avi"})
    assert response.status_code==422
    assert "token" not in response.text.lower()

def test_invalid_record_id_returns_not_found_without_sql():
    with pytest.raises(Exception) as exc:
        store._valid_id("../../etc/passwd")
    assert getattr(exc.value,"status_code",None)==404

def test_audit_hash_stability():
    value={"camera_id":"test","sequence":1,"actor":"officer","event":"test",
          "payload":{"k":"v"},"previous_sha256":"0"*64}
    assert store._json_hash(value)==store._json_hash(dict(reversed(list(value.items()))))
