"""Real centre registry must be provisioned before protected pilot traffic."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
from fastapi import HTTPException

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.demo_network import DEMO_CENTRES,provisioned_centres,provisioned_centre_ids,centre_rows
from app.services.camera_sources import permitted_aliases

def real_centre(cid="SITE-KA-001"):
    return {**DEMO_CENTRES[0],"centre_id":cid,
            "name":"Bengaluru pilot centre","camera_id":"SITE-CAM-01"}

def configure(monkeypatch,*rows):
    monkeypatch.setenv("KAUSHALWATCH_ENV","pilot")
    monkeypatch.setenv("KAUSHALWATCH_CENTRES_JSON",json.dumps({
        "version":"KW_CENTRE_REGISTRY_V1","centres":list(rows)}))

def test_protected_cannot_fall_back_to_demo(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","pilot")
    monkeypatch.delenv("KAUSHALWATCH_CENTRES_JSON",raising=False)
    with pytest.raises(HTTPException) as e:provisioned_centres()
    assert e.value.status_code==503

def test_local_demo_unchanged(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.delenv("KAUSHALWATCH_CENTRES_JSON",raising=False)
    assert len(provisioned_centres())==len(DEMO_CENTRES)

def test_provisioned_centre_is_used_by_reports_and_source_grants(monkeypatch):
    configure(monkeypatch,real_centre())
    assert provisioned_centre_ids()=={"SITE-KA-001"}
    assert len(centre_rows([]))==1
    assert centre_rows([])[0]["centre_id"]=="SITE-KA-001"
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON",
                       json.dumps({"SITE-KA-001":["real.avi"]}))
    manifest=[{"name":"real.avi","sha256":"a"*64}]
    assert permitted_aliases("SITE-KA-001",manifest)==["real.avi"]
    with pytest.raises(HTTPException) as e:
        permitted_aliases("DEMO-KA-104",manifest)
    assert e.value.status_code==404

def test_duplicate_demo_invalid_extra_fields_rejected(monkeypatch):
    cases=[[real_centre("DEMO-KA-104")],
           [real_centre(),real_centre()],
           [{**real_centre(),"unexpected":"invalid"}],
           [{**real_centre(),"trainees":True}],
           [{**real_centre(),"camera_id":"../private"}]]
    for entries in cases:
        configure(monkeypatch,*entries)
        with pytest.raises(HTTPException) as e:provisioned_centres()
        assert e.value.status_code==503
