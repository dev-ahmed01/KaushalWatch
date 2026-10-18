"""Phase 3T: independent blinded review manifest integrity and no-leak tests."""
from __future__ import annotations

import csv
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_phase3t_blinded_reviews import (  # noqa: E402
    DAYS, POLICIES, FIELDS, build_sources, prepare, write,
)


def _window(n: int, *, positive: bool) -> dict:
    policies = {}
    for policy in POLICIES:
        starts = (2 if positive else 0)
        active = (8 if positive else 0)
        policies[policy] = {
            "candidate_episode_starts": starts,
            "candidate_active_samples": active,
            "candidate_window_has_any_flag": positive,
            "not_verified_false_alerts": True,
            "no_incident_created_or_closed": True,
        }
    return {
        "start_frame": 1000 * n,
        "end_frame": 1000 * n + 539,
        "sampled_positions": 90,
        "approx_sampled_time_seconds": 180.0,
        "control_stratum": (
            f"before_event_{n}" if n > 16 else f"progress_{n:02d}"
        ),
        "selection": (
            "phase3s_pre_event_label_only" if n > 16
            else "fixed_progress_strata"
        ),
        "camera_image_healthy_verified": False,
        "media_exported": False,
        "production_action_authorized": False,
        "confounds": {
            "RAW_SCENE_CUE_NOT_MEASURED": 75,
            "SPATIAL_EVIDENCE_NOT_MEASURED": 75,
            "ILLUMINATION_UNRESOLVED": 10,
        },
        "policies": policies,
    }


@pytest.fixture
def paired_reports():
    r = {
        "status": "PHASE3R_TWO_DAY_SYSTEMATIC_NORMAL_RESEARCH_ONLY",
        "development_reused": True,
        "production_qualified": False,
        "held_out_validation": False,
        "false_alert_rate_established": False,
        "operational_scene_warnings_modified": False,
        "media_exported": False,
        "automatic_reference_reenrollment_or_recovery": False,
        "days": {},
    }
    s = {
        "status": "PHASE3S_TWO_DAY_BALANCED_NORMAL_PRE_EVENT_RESEARCH_ONLY",
        "development_evidence_not_held_out": True,
        "prior_phase3r_evidence_reused_without_duplicate_window_evaluation": True,
        "production_qualified": False,
        "media_exported": False,
        "operational_scene_cues_modified": False,
        "camera_physical_reference_approved": False,
        "incident_recovery_or_reference_rotation": False,
        "days": {},
    }
    for day in DAYS:
        day3 = day == "day3"
        old = [_window(i, positive=(i in ({1,2,8,9,10,11,12,15} if day3 else {4})))
               for i in range(1, 17)]
        new = [_window(i, positive=(i == 18 and not day3))
               for i in range(17, 21)]
        sha_video = "a" * 64 if day3 else "b" * 64
        sha_annotations = "c" * 64 if day3 else "d" * 64
        r["days"][day] = {
            "status": "PHASE3R_SYSTEMATIC_NORMAL_RESEARCH_NOT_HELD_OUT",
            "source_video_sha256": sha_video,
            "source_annotations_sha256": sha_annotations,
            "source_reference_is_physical_camera_approved": False,
            "scene_raw_review_status_measured": False,
            "spatial_evidence_status_measured": False,
            "selected_window_count": 16,
            "sample_rate_seconds": 2.0,
            "windows": old,
        }
        s["days"][day] = {
            "status": "PHASE3S_BALANCED_PRE_EVENT_NUMERIC_RESEARCH_ONLY",
            "source_video_sha256": sha_video,
            "source_annotations_sha256": sha_annotations,
            "physical_camera_reference_approved": False,
            "raw_scene_cues_or_spatial_evidence_measured": False,
            "prior_phase3r_selected_windows": 16,
            "prior_phase3r_original_numeric_windows_rereplayed": False,
            "new_pre_event_windows": 4,
            "new_pre_event_numeric_windows": new,
            "sampling_audit": {
                "all_controls_normal_label_only_not_independently_verified_healthy": True
            },
            "policy_comparison": {},
        }
        for policy in POLICIES:
            first = sum(w["policies"][policy]["candidate_episode_starts"]
                        for w in old)
            added = sum(w["policies"][policy]["candidate_episode_starts"]
                        for w in new)
            s["days"][day]["policy_comparison"][policy] = {
                "existing_normal_labeled_candidate_episode_starts": first,
                "new_pre_event_normal_labeled_candidate_episode_starts": added,
                "combined_development_sample_candidate_episode_starts": first + added,
                "selected_normal_sample_episode_count_not_false_alert_rate": True,
            }
    return r, s


def test_all_selected_model_positive_cases_are_blinded(paired_reports):
    r, s = paired_reports
    bundle = prepare(r, s)
    audit = bundle["selection_audit"]
    assert audit["total_source_windows"] == 40
    assert audit["sampled_video_windows_selected_for_manual_review"] == 20
    assert len(bundle["review_cases"]) == len(bundle["sealed_policy_metadata"]) == 20
    assert audit["by_day"]["day3"][
        "three_consecutive_candidate_bearing_cases_hidden_from_reviewers"
    ] == 8
    assert audit["by_day"]["day4"][
        "three_consecutive_candidate_bearing_cases_hidden_from_reviewers"
    ] == 2
    assert bundle["source_footage_exported"] is False
    assert bundle["review_completed"] is False
    assert bundle["production_qualified"] is False
    for case in bundle["review_cases"]:
        assert set(case) == {"case_id", "video_alias", "start_frame", "end_frame"}
        assert "score" not in case
        assert "candidate" not in case


def test_blinded_review_sets_are_identical_between_two_reviewers(paired_reports, tmp_path):
    r,s=paired_reports
    result=prepare(r,s)
    exported=write(result,tmp_path)
    assert len(exported)==3
    one=tmp_path/"reviewer_01.csv"
    two=tmp_path/"reviewer_02.csv"
    assert one.read_bytes()==two.read_bytes()
    with one.open(newline="",encoding="utf-8") as handle:
        rows=list(csv.DictReader(handle))
    assert len(rows)==20
    assert set(rows[0])==set(FIELDS)
    assert all(not row["visible_focus_loss_yes_no_uncertain"] for row in rows)
    assert all(not row["reviewer_confidence_low_medium_high"] for row in rows)
    assert all("model" not in col.lower() and "candidate" not in col.lower()
               for col in FIELDS)
    sealed=json.loads((tmp_path/"SEALED_DO_NOT_SHARE_with_reviewers.json").read_text())
    assert "review_cases" not in sealed
    assert "candidate_policies" in next(iter(sealed["sealed_policy_metadata"].values()))
    assert set(row["case_id"] for row in rows)==set(sealed["sealed_policy_metadata"])
    with pytest.raises(ValueError,match="Refuse to overwrite"):
        write(result,tmp_path)


def test_source_sha_mismatch_fails_closed(paired_reports):
    r,s=paired_reports
    s["days"]["day4"]["source_video_sha256"]="e"*64
    with pytest.raises(ValueError,match="SHA256"):
        prepare(r,s)


def test_quality_ground_truth_cannot_be_fake_certified(paired_reports):
    r,s=paired_reports
    r["days"]["day4"]["windows"][0]["camera_image_healthy_verified"]=True
    with pytest.raises(ValueError,match="false camera health"):
        prepare(r,s)


def test_wrong_model_summary_rejected(paired_reports):
    r,s=paired_reports
    s["days"]["day3"]["policy_comparison"][
        "sharpness_3_consecutive"]["combined_development_sample_candidate_episode_starts"]+=1
    with pytest.raises(ValueError,match="summary mismatch"):
        prepare(r,s)


def test_old_new_overlap_rejected(paired_reports):
    r,s=paired_reports
    s["days"]["day3"]["new_pre_event_numeric_windows"][0]["start_frame"]=1000
    s["days"]["day3"]["new_pre_event_numeric_windows"][0]["end_frame"]=1539
    with pytest.raises(ValueError,match="Overlapping"):
        prepare(r,s)


def test_missing_unknown_raw_scene_evidence_refused(paired_reports):
    r,s=paired_reports
    s["days"]["day4"]["new_pre_event_numeric_windows"][0]["confounds"]={}
    with pytest.raises(ValueError,match="cannot be treated as healthy"):
        prepare(r,s)


def test_budget_is_bounded_and_selection_repeatable(paired_reports):
    r,s=paired_reports
    a=prepare(r,s,per_day=10)
    b=prepare(r,s,per_day=10)
    assert a["review_cases"]==b["review_cases"]
    c=prepare(r,s,per_day=6)
    assert len(c["review_cases"])==12
    assert c["selection_audit"]["unbiased_false_alarm_sample"] is False
    with pytest.raises(ValueError,match="Review budget"):
        prepare(r,s,per_day=21)


def test_missing_output_dir_fails_without_write(paired_reports, tmp_path):
    r,s=paired_reports
    result=prepare(r,s)
    with pytest.raises(ValueError,match="directory must already exist"):
        write(result,tmp_path/"missing")


def test_unsafe_source_release_gate_rejected(paired_reports):
    r,s=paired_reports
    s["camera_physical_reference_approved"]=True
    with pytest.raises(ValueError,match="unsafe source gate"):
        prepare(r,s)
