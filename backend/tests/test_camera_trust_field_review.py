"""Signed independent field package has no autonomous deployment path."""
from __future__ import annotations
import base64
import copy
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from evaluation.camera_trust_field_review import (
    REQUIRED_ROLES,FieldReviewError,blocked,canonical,signed_dossier
)

def signed_fixture():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    policy={
        "policy_sha256":"a"*64,"policy_frozen_at":"2026-05-01T00:00:00Z",
        "min_sites":2,"min_cameras":3,"min_normal_camera_hours":48,
        "min_events_per_class":2,
        "min_event_recall_by_class":{"covered":.8,"defocused":.8,"moved":.8},
        "max_false_alerts_per_100_camera_hours":5,
        "max_p95_latency_seconds":20,
    }
    measurements={
        "started_at":"2026-06-01T00:00:00Z","ended_at":"2026-06-12T00:00:00Z",
        "normal_camera_hours":100,
        "false_alert_episodes":2,
        "events_by_class":{"covered":{"events":2,"detected":2},
                           "defocused":{"events":2,"detected":2},
                           "moved":{"events":2,"detected":2}},
        "latencies_seconds":[1,2,3,5,7,8],
        "sites":["synthetic-site-A","synthetic-site-B"],
        "cameras":["synthetic-cam-A","synthetic-cam-B","synthetic-cam-C"],
        "source_custody_attested":True,
        "blind_independent_adjudication":True,
        "no_automatic_enforcement":True,
        "external_annotation_reference_sha256":"b"*64,
    }
    bundle={"schema":"KW_CAMERA_FIELD_REVIEW_V1",
            "policy":policy,"measurements":measurements,"signatures":{}}
    payload=b"KW_CAMERA_FIELD_REVIEW_V1\x00"+canonical({
        "schema":bundle["schema"],"policy":policy,"measurements":measurements})
    keys={}
    for role in REQUIRED_ROLES:
        private=Ed25519PrivateKey.generate()
        pub=private.public_key().public_bytes(serialization.Encoding.Raw,
                                              serialization.PublicFormat.Raw)
        keys[role]=base64.b64encode(pub).decode()
        bundle["signatures"][role]=base64.b64encode(private.sign(payload)).decode()
    return bundle,keys

def test_three_valid_signatures_do_not_certify_physical_custody():
    b,k=signed_fixture()
    r=signed_dossier(b,k)
    assert r["manual_review_readiness"]=="EVIDENCE_READY_FOR_INDEPENDENT_MANUAL_REVIEW"
    assert r["false_alerts_per_100_camera_hours"]==2
    assert all(v==1.0 for v in r["class_event_recall"].values())
    assert r["external_attestations_verified"] is True
    assert r["autonomous_enforcement_authorized"] is False
    assert r["physical_truth_cryptographically_proven"] is False
    assert blocked()["manual_review_readiness"]=="BLOCKED_NO_EXTERNALLY_SIGNED_FIELD_DOSSIER"

def test_modified_metrics_invalidate_all_signatures():
    b,k=signed_fixture()
    b["measurements"]["false_alert_episodes"]=8
    with pytest.raises(FieldReviewError,match="signature invalid"):
        signed_dossier(b,k)

def test_untrusted_key_or_role_collision_rejected():
    b,k=signed_fixture()
    bad=dict(k);bad["independent_adjudicator"]=k["source_custodian"]
    with pytest.raises(FieldReviewError,match="distinct keys|signature invalid"):
        signed_dossier(b,bad)

def test_policy_below_minimum_is_rejected_even_if_signed():
    b,k=signed_fixture()
    b["policy"]["min_sites"]=1
    with pytest.raises(FieldReviewError,match="signature invalid"):
        signed_dossier(b,k)

def test_numeric_threshold_failure_never_releases():
    b,k=signed_fixture()
    # Re-sign modified package so the metric evaluation is tested, not just crypto.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    b["measurements"]["false_alert_episodes"]=12
    payload=b"KW_CAMERA_FIELD_REVIEW_V1\x00"+canonical({
        "schema":b["schema"],"policy":b["policy"],"measurements":b["measurements"]})
    k={}
    for role in REQUIRED_ROLES:
        private=Ed25519PrivateKey.generate()
        k[role]=base64.b64encode(private.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        b["signatures"][role]=base64.b64encode(private.sign(payload)).decode()
    r=signed_dossier(b,k)
    assert r["manual_review_readiness"]=="EVIDENCE_BELOW_SIGNED_POLICY"
    assert r["checks"]["nuisance_episode_rate"] is False
    assert r["autonomous_enforcement_authorized"] is False
