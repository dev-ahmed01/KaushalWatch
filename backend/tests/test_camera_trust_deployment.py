"""Fail closed on incomplete/unsafe pilot configuration; no real secrets."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.check_camera_trust_deployment import check_environment

def test_empty_production_environment_blocked_no_values_leaked():
    result=check_environment("full",{},probe_db=False)
    assert result["shadow_software_configuration"]=="BLOCKED"
    assert result["safe_to_enable_autonomous_enforcement"] is False
    assert result["checks"]["postgres_camera_schema_v3"]=="NOT_PROBED"
    assert result["physical_camera_health"]=="UNKNOWN"
    assert "password" not in json.dumps(result).lower()

def test_web_and_api_require_protected_oidc():
    baseline={"KAUSHALWATCH_ENV":"pilot","KAUSHALWATCH_STORAGE_BACKEND":"postgres",
        "KAUSHALWATCH_EVIDENCE_BACKEND":"s3",
        "KAUSHALWATCH_DATABASE_URL":"postgresql://demo:do-not-store@localhost/x",
        "KAUSHALWATCH_API_INTERNAL_URL":"http://localhost:8000"}
    x=check_environment("web",baseline)
    assert x["checks"]["protected_web_session"]=="BLOCKED"
    assert x["checks"]["same_origin_proxy"]=="BLOCKED"
    assert x["shadow_software_configuration"]=="BLOCKED"
    y=check_environment("api",{**baseline,
         "KAUSHALWATCH_REVIEW_AUTH_MODE":"token",
         "KAUSHALWATCH_OIDC_GRANTS_JSON":"{}"})
    assert y["checks"]["oidc_officer_identity_selected"]=="BLOCKED"

def test_worker_rejects_nonexistent_private_manifest(tmp_path):
    x=check_environment("worker",{
        "KAUSHALWATCH_ENV":"pilot",
        "KAUSHALWATCH_STORAGE_BACKEND":"postgres",
        "KAUSHALWATCH_EVIDENCE_BACKEND":"s3",
        "KAUSHALWATCH_DATABASE_URL":"postgresql://localhost/test",
        "KAUSHALWATCH_CAMERA_DRIVE_MANIFEST":str(tmp_path/"not-there.json"),
    })
    assert x["checks"]["private_sha_pinned_manifest"]=="BLOCKED"
    assert x["checks"]["centre_source_grants"]=="BLOCKED"


def test_preflight_uses_supplied_env_not_host_process(monkeypatch):
    from app.services.demo_network import DEMO_CENTRES
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.delenv("KAUSHALWATCH_CENTRES_JSON",raising=False)
    real={**DEMO_CENTRES[0],"centre_id":"SITE-KA-001",
          "name":"Real field site","camera_id":"REAL-CAM-01"}
    pilot={"KAUSHALWATCH_ENV":"pilot",
           "KAUSHALWATCH_STORAGE_BACKEND":"postgres",
           "KAUSHALWATCH_DATABASE_URL":"postgresql://localhost/kw",
           "KAUSHALWATCH_CENTRES_JSON":json.dumps({
             "version":"KW_CENTRE_REGISTRY_V1","centres":[real]})}
    assert check_environment("api",pilot)["checks"]["real_centre_registry_provisioned"]=="PASS"
    assert check_environment("api",{**pilot,"KAUSHALWATCH_CENTRES_JSON":""})["checks"]["real_centre_registry_provisioned"]=="BLOCKED"

def test_source_grants_validate_against_given_centre_ids(tmp_path):
    from app.services.camera_sources import permitted_aliases
    import pytest
    from fastapi import HTTPException
    grants=json.dumps({"SITE-KA-001":["camera.avi"]})
    manifest=[{"name":"camera.avi","sha256":"a"*64}]
    assert permitted_aliases("SITE-KA-001",manifest,grants,{"SITE-KA-001"})==["camera.avi"]
    with pytest.raises(HTTPException):
        permitted_aliases("DEMO-KA-104",manifest,grants,{"SITE-KA-001"})
