"""Synthetic contract: uncertain visual evidence never becomes proven tampering."""
from __future__ import annotations
import cv2
import numpy as np
from app.services.camera_quality import sample, split_evidence_decision

NORMAL={"state":"NO_LARGE_SCENE_DISPLACEMENT_OBSERVED"}
CLEAR={"state":"NO_SIGNIFICANT_SHARPNESS_DROP_OBSERVED"}
LOCAL={"state":"NO_DISTINCT_LOCAL_CHANGE_OBSERVED"}
FREEZE={"state":"NONIDENTICAL_SPARSE_SAMPLES"}


def decision(*,illumination="NO_EXTREME_ILLUMINATION_OBSERVED",
             focus=CLEAR, geometry=NORMAL, coverage=LOCAL, freeze=FREEZE,
             reference=True):
    return split_evidence_decision(
        illumination=illumination,focus=focus,geometry=geometry,
        localized_coverage=coverage,freeze=freeze,
        reference_present=reference,
    )


def test_reference_free_never_calls_scene_healthy_or_malicious():
    d=decision(reference=False)
    assert d["usability"]=="UNKNOWN_NO_REFERENCE"
    assert d["interference_review"]=="UNKNOWN_NO_REFERENCE"
    assert d["hold_attendance_and_practical_claims"] is True
    assert d["malicious_tampering_proven"] is False
    assert d["enforcement_authorized"] is False


def test_defocus_degrades_evidence_without_alleging_interference():
    d=decision(focus={"state":"POSSIBLE_DEFOCUS"})
    assert d["usability"]=="NOT_USABLE_FOR_VISUAL_VERIFICATION"
    assert d["usability_reason"]=="FOCUS_DEGRADED"
    assert d["interference_review"]=="NOT_ESTABLISHED"
    assert d["quality_loss_without_interference_attribution"] is True
    assert d["hold_attendance_and_practical_claims"] is True


def test_dark_without_reference_still_abstains_without_tamper_attribution():
    d=decision(illumination="TOO_DARK_PROXY",reference=False)
    assert d["usability"]=="NOT_USABLE_FOR_VISUAL_VERIFICATION"
    assert d["interference_review"]=="UNKNOWN_NO_REFERENCE"
    assert d["malicious_tampering_proven"] is False


def test_registered_scene_change_only_generates_possible_review():
    d=decision(geometry={"state":"POSSIBLE_SCENE_DISPLACEMENT"})
    assert d["usability"]=="REVIEW_REQUIRED_SCENE_ALIGNMENT"
    assert d["interference_review"]=="POSSIBLE_SCENE_INTERFERENCE_REVIEW"
    assert d["physical_camera_health"]=="UNKNOWN"
    assert d["enforcement_authorized"] is False


def test_local_occlusion_abstains_and_requires_human_review():
    d=decision(coverage={"state":"POSSIBLE_LOCAL_OBSTRUCTION"})
    assert d["usability"]=="NOT_USABLE_FOR_VISUAL_VERIFICATION"
    assert d["interference_review"]=="POSSIBLE_SCENE_INTERFERENCE_REVIEW"
    assert d["malicious_tampering_proven"] is False


def test_static_sparse_frames_cannot_prove_replayed_stream():
    d=decision(freeze={"state":"IDENTICAL_SPARSE_SAMPLES"})
    assert d["sparse_identical_frames_observed"] is True
    assert d["interference_review"]=="NOT_ESTABLISHED"
    assert d["malicious_tampering_proven"] is False


def test_low_confidence_reference_does_not_mean_clear_scene():
    d=decision(geometry={"state":"UNKNOWN_FEW_MATCHES"})
    assert d["usability"]=="UNKNOWN_SCENE_REGISTRATION"
    assert d["hold_attendance_and_practical_claims"] is True


def test_clear_provisional_is_not_a_certified_camera():
    d=decision()
    assert d["usability"]=="PROVISIONALLY_OBSERVABLE"
    assert d["hold_attendance_and_practical_claims"] is False
    assert d["physical_camera_health"]=="UNKNOWN"
    assert d["institutional_accuracy_qualified"] is False


def test_real_opencv_sample_converts_defocus_proxy_into_separate_usable_state():
    # Seeded random texture and strong blur are generated pixels, not footage.
    rng=np.random.default_rng(12)
    reference=rng.integers(0,256,(128,192,3),dtype=np.uint8)
    unfocused=cv2.GaussianBlur(reference,(27,27),8)
    found=sample(unfocused,reference=reference,previous=reference)
    assert found["focus"]["state"]=="POSSIBLE_DEFOCUS"
    assert found["evidence_triage"]["usability"]=="NOT_USABLE_FOR_VISUAL_VERIFICATION"
    assert found["evidence_triage"]["quality_loss_without_interference_attribution"] is True
    assert found["evidence_triage"]["malicious_tampering_proven"] is False


def test_no_reference_sample_exposes_no_officer_accuracy_assertion():
    img=np.zeros((128,192,3),dtype=np.uint8)
    found=sample(img,reference=None,previous=None)
    t=found["evidence_triage"]
    assert t["usability"]=="NOT_USABLE_FOR_VISUAL_VERIFICATION"
    assert t["interference_review"]=="UNKNOWN_NO_REFERENCE"
    assert t["reference_status"]=="ABSENT"
    assert t["physical_camera_health"]=="UNKNOWN"
    assert found["production_qualified"] is False
