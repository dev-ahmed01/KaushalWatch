"""Counterfactual candidate tests: lower nuisance is never enough if events drop."""
from __future__ import annotations

import pytest

from app.services.camera_counterfactual_shadow import (
    CANDIDATES, CandidateGate, OfflineCandidateComparison,
)


def cause(*, photometric=False, localized=False, translate=False):
    features=[]
    if photometric:
        features.append("PHOTOMETRIC_SHIFT_COMPATIBLE")
    if localized:
        features.append("LOCAL_FOREGROUND_OR_OCCLUSION_COMPATIBLE")
    return {
        "hypotheses": features or ["CAUSE_UNRESOLVED"],
        "translation_preset_sweep":{
            "conservative":{"candidate_global_translation_supported":translate}
        },
    }


def compare(items, *, fps=1.0, full=True):
    evaluator=OfflineCandidateComparison(fps=fps)
    for frame, (label, raw, features, status) in enumerate(items,1):
        evaluator.annotation(frame,label)
        evaluator.observation(
            frame,label,raw_review=raw,cause=features,
            evidence_status=status,sample_seconds=1/fps,
        )
    return evaluator.result(full=full)


def test_nuisance_reduced_with_no_observed_moved_event_loss_not_certified():
    # Photometric normal episode at frames 3-5 and confirmed movement
    # event at 12-16; one genuine appearance change stays.
    rows=[]
    for n in range(1,31):
        kind=3 if 11<=n<=20 else 0
        alert=(3<=n<=5 or 12<=n<=16)
        rows.append((kind,alert,cause(photometric=n<=5), "SUFFICIENT_TILES"))
    result=compare(rows)
    base=result["candidate_comparisons"]["frozen_baseline"]
    guarded=result["candidate_comparisons"]["photometric_defer"]
    assert base["normal_review_fraction"]>guarded["normal_review_fraction"]
    assert guarded["events"]["moved"]["fresh_review_events"]==1
    assert guarded["raw_normal_fraction_reduction_vs_baseline"]>0
    assert guarded["interpretation"]=="DEVELOPMENT_NO_EVENT_LOSS_OBSERVED_NOT_QUALIFIED"
    assert guarded["authorized_for_deployment"] is False
    assert result["deployable_candidate_selected"] is None


def test_false_improvement_that_misses_movement_is_blocked():
    rows=[]
    for n in range(1,31):
        label=3 if 11<=n<=20 else 0
        review=(2<=n<=5 or 13<=n<=17)
        rows.append((label,review,cause(photometric=review), "SUFFICIENT_TILES"))
    data=compare(rows)["candidate_comparisons"]
    original=data["frozen_baseline"]
    candidate=data["photometric_defer"]
    assert original["events"]["moved"]["fresh_review_events"]==1
    assert candidate["events"]["moved"]["fresh_review_events"]==0
    assert candidate["normal_review_fraction"]<original["normal_review_fraction"]
    assert candidate["lost_baseline_fresh_event_start_frames"]["moved"]==[11]
    assert candidate["interpretation"]=="BLOCKED_KNOWN_EVENT_REGRESSION"


def test_any_review_loss_blocks_even_without_fresh_onset():
    # A review cue is already active when an annotated event begins.
    rows=[]
    for n in range(1,22):
        label=1 if 9<=n<=16 else 0
        raw=6<=n<=14
        rows.append((label,raw,cause(photometric=label==1), "SUFFICIENT_TILES"))
    data=compare(rows)["candidate_comparisons"]
    assert data["frozen_baseline"]["events"]["covered"]["fresh_review_events"]==0
    assert data["photometric_defer"]["events"]["covered"]["any_review_events"]==0
    assert data["photometric_defer"]["lost_baseline_any_review_event_start_frames"]["covered"]==[9]
    assert data["photometric_defer"]["interpretation"]=="BLOCKED_KNOWN_EVENT_REGRESSION"


def test_phase_only_candidate_loses_covered_alert_and_is_blocked():
    items=[]
    for n in range(1,35):
        label=1 if 10<=n<=25 else 0
        raw=(12<=n<=22)
        items.append((label,raw,cause(translate=False), "SUFFICIENT_TILES"))
    scores=compare(items)["candidate_comparisons"]
    assert scores["coherent_translation_only"]["events"]["covered"]["fresh_review_events"]==0
    assert scores["coherent_translation_only"]["interpretation"]=="BLOCKED_KNOWN_EVENT_REGRESSION"


def test_unknown_low_texture_global_alert_is_never_suppressed_by_any_candidate():
    for policy in CANDIDATES:
        gate=CandidateGate(policy)
        kept=gate.observe(
            raw_review=True,evidence_status="UNKNOWN_LOW_TEXTURE",
            cause=cause(photometric=True,localized=True),sample_seconds=1,
        )
        assert kept is True
        assert gate.unknown_raw_reviews_preserved==1
        assert gate.altered_raw_review_samples==0


def test_sustained_raw_rule_cannot_use_cue_gaps_as_evidence():
    gate=CandidateGate("sustained_raw_20s")
    for _ in range(19):
        assert gate.observe(raw_review=True,evidence_status="SUFFICIENT_TILES",
                            cause=cause(),sample_seconds=1) is False
    assert gate.observe(raw_review=True,evidence_status="SUFFICIENT_TILES",
                        cause=cause(),sample_seconds=1) is True
    assert gate.observe(raw_review=False,evidence_status="SUFFICIENT_TILES",
                        cause=cause(),sample_seconds=1) is False
    assert gate.elapsed_raw_seconds==0


def test_preview_has_no_qualified_comparison_even_when_no_event_loss():
    items=[(0,i%2==0,cause(photometric=True),"SUFFICIENT_TILES")
           for i in range(1,18)]
    result=compare(items,full=False)
    assert result["status"]=="PREVIEW_ONLY_COUNTERFACTUAL_NOT_COMPARABLE"
    for data in result["candidate_comparisons"].values():
        assert data["interpretation"]=="PREVIEW_ONLY_NOT_COMPARABLE"
        assert data["authorized_for_deployment"] is False


@pytest.mark.parametrize("invalid",[
    {"raw_review":"true","evidence_status":"SUFFICIENT_TILES","cause":cause(),"sample_seconds":1},
    {"raw_review":True,"evidence_status":"WARMUP","cause":cause(),"sample_seconds":1},
    {"raw_review":True,"evidence_status":"SUFFICIENT_TILES","cause":{},"sample_seconds":1},
    {"raw_review":True,"evidence_status":"SUFFICIENT_TILES","cause":cause(),"sample_seconds":0},
    {"raw_review":True,"evidence_status":"SUFFICIENT_TILES","cause":cause(),"sample_seconds":float("nan")},
])
def test_invalid_or_missing_evidence_rejected(invalid):
    gate=CandidateGate("photometric_defer")
    with pytest.raises(ValueError):
        gate.observe(**invalid)
    assert gate.altered_raw_review_samples==0


def test_annotation_reordering_refused():
    evaluator=OfflineCandidateComparison(fps=3)
    with pytest.raises(ValueError,match="continuous"):
        evaluator.annotation(2,0)


def test_no_candidate_can_introduce_new_detector_review():
    gate=CandidateGate("photometric_defer")
    assert gate.observe(raw_review=False,evidence_status="SUFFICIENT_TILES",
                        cause=cause(),sample_seconds=1) is False
