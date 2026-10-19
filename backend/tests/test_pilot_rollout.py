"""Pilot preflight never prints secrets or bypasses external field acceptance."""
from __future__ import annotations
import json
import stat
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.check_pilot_rollout import evaluate,write_receipt,load_private

def test_absent_inputs_always_block_field_activation():
    result=evaluate({})
    assert result["software_preflight"]=="BLOCKED"
    assert result["checks"]["real_https_readiness"]=="NOT_PROBED"
    assert result["checks"]["immutable_release_lock_format"]=="NOT_SUBMITTED"
    assert result["checks"]["signed_independent_field_dossier"]=="NOT_SUBMITTED"
    assert result["eligible_to_request_external_pilot_signoff"] is False
    assert result["autonomous_enforcement_authorized"] is False
    assert result["external_operator_approval_recorded"] is False
    assert result["physical_camera_health"]=="UNKNOWN"

def test_insecure_real_http_and_secrets_are_rejected_and_redacted():
    result=evaluate({"KAUSHALWATCH_DATABASE_URL":"postgresql://admin:PRIVATE-DO-NOT-ECHO@localhost/db"},
                    api="http://insecure.example",web="https://console.example")
    assert result["checks"]["real_https_readiness"]=="BLOCKED"
    assert "PRIVATE-DO-NOT-ECHO" not in json.dumps(result)
    assert "insecure.example" not in json.dumps(result)

def test_self_declared_fake_field_data_cannot_pass_ed25519():
    invalid={"schema":"KW_CAMERA_FIELD_REVIEW_V1","policy":{},"measurements":{},
             "signatures":{"source_custodian":"bogus"}}
    result=evaluate({},field_bundle=invalid,trusted_public_keys={})
    assert result["checks"]["signed_independent_field_dossier"]=="BLOCKED"
    assert result["field_evidence"]=="BLOCKED_OR_NOT_SUBMITTED"

def test_private_receipt_is_exclusive_permissioned_and_outside_repo(tmp_path):
    receipt=tmp_path/"pilot.json"
    write_receipt(receipt,evaluate({}))
    assert stat.S_IMODE(receipt.stat().st_mode)==0o600
    assert json.loads(receipt.read_text())["software_preflight"]=="BLOCKED"
    with pytest.raises(FileExistsError):write_receipt(receipt,{})
    with pytest.raises(ValueError):write_receipt(ROOT/"pilot-secret.json",{})

def test_field_loader_is_bounded_and_object_only(tmp_path):
    data=tmp_path/"not-object.json";data.write_text("[]")
    with pytest.raises(ValueError):load_private(data)
    with pytest.raises(ValueError):load_private(tmp_path/"missing.json")

def test_cli_safe_status_no_credentials_required():
    result=subprocess.run([sys.executable,str(ROOT/"scripts/check_pilot_rollout.py"),"--status"],
        capture_output=True,text=True,cwd=ROOT,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)["pilot_activation"]=="BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"


def test_all_technical_checks_only_make_external_review_eligible(monkeypatch):
    import scripts.check_pilot_rollout as module
    monkeypatch.setattr(module,"check_environment",lambda *args,**kwargs:{"checks":{
        "real_centre_registry_provisioned":"PASS",
        "postgres_camera_schema_v3":"PASS",
        "external_custody_and_field_accuracy":"NOT_VERIFIED"}})
    monkeypatch.setattr(module,"run_check",lambda *args,**kwargs:{
        "passed":True,"status":"public_preflight_passed"})
    monkeypatch.setattr(module,"signed_dossier",lambda *args,**kwargs:{
        "manual_review_readiness":module.FIELD_READY})
    result=module.evaluate({},api="https://api.example.org",web="https://web.example.org",
                           probe_db=True,field_bundle={"schema":"synthetic"},
                           trusted_public_keys={"mock":"mock"},
                           release_lock={
                               "schema":"KW_PILOT_RELEASE_LOCK_V1",
                               "source_commit":"a"*40,
                               "images":{"api":"registry.example/kw-api@sha256:"+"1"*64,
                                         "web":"registry.example/kw-web@sha256:"+"2"*64},
                               "database":{"required_migrations":[1,2,3],
                                           "apply":"separate_approved_migration_only_role",
                                           "verify":"scripts/migrate_postgres.py --check"},
                               "rollback":{"on_failed_readiness":"halt_traffic_and_request_operator_review",
                                           "database_rollback":"manual_restore_from_verified_isolated_backup_only"}},
                           expected_release_commit="a"*40)
    assert result["eligible_to_request_external_pilot_signoff"] is True
    assert result["software_preflight"]=="CHECKS_PASS"
    assert result["pilot_activation"]=="BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert result["autonomous_enforcement_authorized"] is False
    assert result["physical_camera_health"]=="UNKNOWN"
    assert "external_custody_and_field_accuracy" in result["external_evidence_not_independently_verified"]
