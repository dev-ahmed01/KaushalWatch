"""Synthetic-only held-out evaluation; does not assert field accuracy."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from evaluation.camera_trust_holdout import (
    InvalidEvaluation, blocked_status, evaluate, hash_json,
)

def fixture():
    cases=[]; predictions=[]
    for i,cls in enumerate(("normal","covered","defocused","moved")):
        cid=f"synthetic-case-{i:03d}"
        digest=f"{i+1:064x}"
        cases.append({
            "case_id":cid,"site_id":f"site-{i:03d}","camera_id":f"cam-{i:03d}",
            "source_sha256":digest,"label":cls,"duration_seconds":10.0,
            "stratum":"daytime",
            "independent_labeler_id":f"labeler-{i:03d}",
            "source_custodian_id":f"custodian-{i:03d}",
            "inference_operator_id":f"operator-{i:03d}",
            "custody_record_id":f"external-ledger-{i:03d}",
            "label_adjudicated_at":"2026-09-01T10:00:00+00:00",
            "label_blinded_to_predictions":True,"independent_capture":True,
        })
        samples=[{"requested_frame0":n*2,"decoded_frame0":n*2,
                  "candidate_for_human_review":bool(cls!="normal" and n==2),
                  "physical_camera_health":"UNKNOWN","production_qualified":False}
                 for n in range(4)]
        predictions.append({"case_id":cid,"report":{
            "schema":"CAMERA_TRUST_SHADOW_SAMPLE_V1",
            "source_sha256":digest,"physical_camera_health":"UNKNOWN",
            "production_qualified":False,"auto_incident_mutations":0,
            "frame_images_or_video_exported":False,
            "sampling":"SPARSE_RANDOM_ACCESS_NOT_FULL_VIDEO_DECODE",
            "source_frame_count_reported":10,"fps_reported":1,
            "sampled_frames":4,"requested_samples":4,
            "failed_positions":[],"possible_review_samples":int(cls!="normal"),
            "authorized_reference_file_present":True,"samples":samples,
        }})
    labels={"schema":"KW_CAMERA_INDEPENDENT_LABELS_V1",
            "labels_frozen_at":"2026-09-02T00:00:00Z",
            "evaluation_policy_sha256":"e"*64,
            "split":"untouched_external_holdout","cases":cases}
    return labels,{"schema":"KW_CAMERA_SHADOW_PREDICTIONS_V1",
                   "labels_sha256":hash_json(labels),"predictions":predictions}

def test_diagnostic_cohorts_report_uncertainty_but_never_qualify():
    labels,pred=fixture()
    r=evaluate(labels,pred)
    assert r["source_case_count"]==4 and r["distinct_sites"]==4
    assert r["cohort_diagnostic"]["positive_clip_candidate_rate"]==1.0
    assert r["cohort_diagnostic"]["normal_clip_candidate_rate"]==0.0
    assert r["cohort_diagnostic"]["independently_labeled_normal_video_hours"]==round(10/3600,6)
    assert r["requested_samples"]==16 and r["decoded_samples"]==16
    assert r["qualified_for_autonomous_enforcement"] is False
    assert r["false_alarms_per_camera_hour_established"] is False
    assert r["label_independence_cryptographically_verified"] is False
    assert r["field_release"].startswith("BLOCKED")
    assert blocked_status()["field_release"].startswith("BLOCKED")

def test_source_mismatch_fails_closed():
    labels,pred=fixture()
    pred["predictions"][0]["report"]["source_sha256"]="f"*64
    with pytest.raises(InvalidEvaluation,match="Source digest"):
        evaluate(labels,pred)

def test_missing_prediction_fails_closed():
    labels,pred=fixture()
    pred["predictions"].pop()
    with pytest.raises(InvalidEvaluation,match="differ in count"):
        evaluate(labels,pred)

def test_false_field_claim_fails_closed():
    labels,pred=fixture()
    pred["predictions"][0]["report"]["production_qualified"]=True
    with pytest.raises(InvalidEvaluation,match="unsupported"):
        evaluate(labels,pred)

def test_nonblinded_or_conflicted_labeler_fails_closed():
    labels,pred=fixture()
    labels["cases"][0]["label_blinded_to_predictions"]=False
    pred["labels_sha256"]=hash_json(labels)
    with pytest.raises(InvalidEvaluation,match="blinded"):
        evaluate(labels,pred)
    labels["cases"][0]["label_blinded_to_predictions"]=True
    labels["cases"][0]["independent_labeler_id"]="operator-000"
    pred["labels_sha256"]=hash_json(labels)
    with pytest.raises(InvalidEvaluation,match="distinct"):
        evaluate(labels,pred)

def test_incomplete_video_positions_are_not_silently_filled():
    labels,pred=fixture()
    r=pred["predictions"][0]["report"]
    r["samples"].pop();r["sampled_frames"]=3;r["failed_positions"]=[6]
    outcome=evaluate(labels,pred)
    assert outcome["incomplete_cases"]==1
    assert outcome["decoded_samples"]==15
    assert outcome["qualified_for_autonomous_enforcement"] is False
    assert any("undecoded" in b for b in outcome["release_blockers"])

def test_nuisance_proxy_is_not_field_false_alarms_per_hour():
    labels,pred=fixture()
    r=pred["predictions"][0]["report"]
    r["samples"][1]["candidate_for_human_review"]=True
    r["possible_review_samples"]=1
    outcome=evaluate(labels,pred)
    assert outcome["cohort_diagnostic"]["normal_clip_candidate_rate"]==1.0
    assert outcome["false_alarms_per_camera_hour_established"] is False
    assert "false_alarm_rate" not in outcome

def test_export_db_boundary_filters_all_extra_payload_fields(monkeypatch):
    labels,pred=fixture()
    case=labels["cases"][0]
    case["case_id"]="11111111-1111-4111-8111-111111111111"
    labels["cases"]=[case]
    payload=pred["predictions"][0]["report"]
    payload["image_b64"]="PRIVATE_IMAGE"
    payload["source_alias"]="OTHER_CENTRE_SOURCE"
    payload["samples"][0]["raw_image"]="PRIVATE_FRAME"
    from scripts import export_camera_trust_holdout as exporter
    class Connection:
        def execute(self,query,args):
            assert "kw_camera_observations" in query and "::uuid[]" in query
            return self
        def fetchall(self):
            return [{"job_id":case["case_id"],"camera_id":case["camera_id"],
                     "centre_id":case["site_id"],"source_sha256":case["source_sha256"],
                     "status":"succeeded","payload":payload}]
    class Context:
        def __enter__(self):return Connection()
        def __exit__(self,*args):return False
    monkeypatch.setattr(exporter,"connection",lambda:Context())
    snap=exporter.make_snapshot(labels)
    assert snap["labels_sha256"]==hash_json(labels)
    result=snap["predictions"][0]["report"]
    assert "image_b64" not in result and "source_alias" not in result
    assert "raw_image" not in result["samples"][0]

def test_no_file_status_cli_is_explicitly_blocked():
    script=Path(__file__).resolve().parents[2]/"scripts/evaluate_camera_trust_holdout.py"
    output=subprocess.run([sys.executable,str(script),"--status"],
                          capture_output=True,text=True,check=True)
    result=json.loads(output.stdout)
    assert result["field_release"]=="BLOCKED_NO_EXTERNAL_HOLDOUT_SUBMITTED"
