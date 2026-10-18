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
