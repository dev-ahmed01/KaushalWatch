"""Two-day Phase 3L gate: complete evidence only, no cherry-picked wins."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from compare_phase3l_dual_day import compare
from app.services.camera_counterfactual_shadow import OfflineCandidateComparison


def mock_report(tmp_path, name, *, movement_photometric=False, video_hash="a"):
    scorer=OfflineCandidateComparison(fps=1.0)
    for n in range(1,41):
        label=3 if 12<=n<=23 else 0
        raw=2<=n<=5 or 15<=n<=20
        photometric=(2<=n<=5 or (label==3 and movement_photometric))
        diag={
            "hypotheses":["PHOTOMETRIC_SHIFT_COMPATIBLE" if photometric else "CAUSE_UNRESOLVED"],
            "translation_preset_sweep":{
                "conservative":{"candidate_global_translation_supported":label==3}
            },
        }
        scorer.annotation(n,label)
        scorer.observation(n,label,raw_review=raw,evidence_status="SUFFICIENT_TILES",
                           cause=diag,sample_seconds=1)
    comp=scorer.result(full=True)
    frozen=comp["candidate_comparisons"]["frozen_baseline"]
    data={
        "status":"FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT",
        "production_qualified":False,"production_integration":False,
        "evaluated_frames":40,"total_frames":40,
        "video_sha256":video_hash*64,
        "normal_review_fraction":frozen["normal_review_fraction"],
        "raw_camera_review_fraction_by_class":{"normal":frozen["normal_review_fraction"]},
        "fresh_event_review_counts":{
            k:frozen["events"][k]["fresh_review_events"]
            for k in ("covered","defocused","moved")
        },
        "counterfactual_scene_gate_comparison":comp,
    }
    path=tmp_path/(name+".json")
    path.write_text(json.dumps(data))
    return path


def test_dual_day_unchanged_incidents_only_development_signals(tmp_path):
    d3=mock_report(tmp_path,"day3",video_hash="a")
    d4=mock_report(tmp_path,"day4",video_hash="b")
    report=compare(d3,d4)
    assert report["status"]=="PHASE3L_TWO_RECORDING_DEVELOPMENT_GATE_NOT_HELD_OUT"
    assert report["recommended_for_production"] is None
    candidate=report["candidate_results"]["photometric_defer"]
    assert candidate["status"]=="UNQUALIFIED_DEVELOPMENT_SIGNAL_REQUIRES_INDEPENDENT_VALIDATION"
    assert candidate["authorized_for_deployment"] is False
    assert candidate["day_results"]["day3"]["fresh_review_events_by_class"]["moved"]==1


def test_missing_movement_in_one_day_blocks_candidate_regardless_of_second_day(tmp_path):
    d3=mock_report(tmp_path,"day3",movement_photometric=True,video_hash="a")
    d4=mock_report(tmp_path,"day4",video_hash="b")
    report=compare(d3,d4)
    blocked=report["candidate_results"]["photometric_defer"]
    assert blocked["status"]=="BLOCKED_KNOWN_EVENT_REGRESSION_IN_DEVELOPMENT"
    assert blocked["day_results"]["day3"]["lost_baseline_fresh_events"]["moved"]==1
    assert blocked["day_results"]["day4"]["lost_baseline_fresh_events"]["moved"]==0


def test_previews_not_accepted_as_two_day_evidence(tmp_path):
    d3=mock_report(tmp_path,"day3",video_hash="a")
    d4=mock_report(tmp_path,"day4",video_hash="b")
    data=json.loads(d3.read_text())
    data["total_frames"]=100
    d3.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="incomplete"):
        compare(d3,d4)


def test_two_names_same_video_hash_are_not_independent_recordings(tmp_path):
    d3=mock_report(tmp_path,"day3",video_hash="a")
    d4=mock_report(tmp_path,"day4",video_hash="a")
    with pytest.raises(ValueError,match="distinct pinned videos"):
        compare(d3,d4)


def test_tampered_original_normal_fraction_rejected(tmp_path):
    d3=mock_report(tmp_path,"day3",video_hash="a")
    d4=mock_report(tmp_path,"day4",video_hash="b")
    data=json.loads(d3.read_text())
    data["raw_camera_review_fraction_by_class"]["normal"]=0.999
    d3.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="frozen baseline"):
        compare(d3,d4)
