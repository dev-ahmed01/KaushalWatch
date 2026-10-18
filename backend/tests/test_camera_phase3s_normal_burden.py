"""Phase3S: invariant tests for numeric audit and repaired pre-event sampling."""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_phase3s_normal_burden as triage  # noqa: E402
import run_phase3s_missing_pre_controls as repairs  # noqa: E402

POLICIES = triage.POLICIES


def make_window(*, start=100, end=279, name="progress_01_of_12", episodes=2):
    policies = {}
    for policy in POLICIES:
        e = episodes
        policies[policy] = {
            "candidate_episode_starts": e,
            "candidate_active_samples": 3*e,
            "longest_candidate_contiguous_samples": 3 if e else 0,
            "candidate_window_has_any_flag": bool(e),
            "not_verified_false_alerts": True,
            "no_incident_created_or_closed": True,
        }
    return {
        "start_frame": start, "end_frame": end,
        "control_stratum": name, "selection": "fixed_progress_strata",
        "sampled_positions": 90,
        "comparison_states": {
            "INSUFFICIENT_PAST_SAMPLE_COVERAGE": 15,
            "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION": 75,
        },
        "confounds": {
            "SPATIAL_EVIDENCE_NOT_MEASURED": 75,
            "RAW_SCENE_CUE_NOT_MEASURED": 75,
            "ILLUMINATION_UNRESOLVED": 50,
        },
        "camera_image_healthy_verified": False,
        "media_exported": False,
        "production_action_authorized": False,
        "policies": policies,
    }


@pytest.fixture
def numeric_report():
    days = {}
    for day in ("day3", "day4"):
        w = make_window(episodes=2 if day == "day3" else 1)
        episodes = w["policies"]["sharpness_3_consecutive"]["candidate_episode_starts"]
        days[day] = {
            "status": "PHASE3R_SYSTEMATIC_NORMAL_RESEARCH_NOT_HELD_OUT",
            "production_qualified": False,
            "source_is_held_out": False,
            "normal_annotation_is_independent_health_truth": False,
            "source_reference_is_physical_camera_approved": False,
            "scene_raw_review_status_measured": False,
            "spatial_evidence_status_measured": False,
            "full_day_detector_replayed": False,
            "images_or_video_exported": False,
            "operational_incident_or_reference_mutated": False,
            "sample_rate_seconds": 2.0,
            "approx_annotated_normal_sample_hours": 0.05,
            "selected_window_count": 1,
            "sampled_numeric_positions": 90,
            "sampling_audit": {
                "selected_windows": 1, "selected_time_strata": 1,
                "no_random_or_unbiased_sampling_claim": True,
                "normal_labeled_not_authenticated_camera_healthy": True,
                "unfilled_time_strata": 11,
                "event_adjacency": {
                    "before": {"selected_nonoverlapping": 0,
                               "rejected_overlap": 4},
                    "after": {"selected_nonoverlapping": 0,
                              "rejected_overlap": 0},
                },
            },
            "policies": {
                policy: {
                    "candidate_episode_starts_on_annotated_normal": episodes,
                    "candidate_active_samples_on_annotated_normal": 3*episodes,
                    "control_windows_with_any_candidate": 1,
                    "candidate_burden_is_conditional_on_selected_controls_only": True,
                } for policy in POLICIES
            },
            "windows": [w],
        }
    return {
        "status": "PHASE3R_TWO_DAY_SYSTEMATIC_NORMAL_RESEARCH_ONLY",
        "automatic_reference_reenrollment_or_recovery": False,
        "held_out_validation": False,
        "media_exported": False,
        "operational_scene_warnings_modified": False,
        "production_qualified": False,
        "false_alert_rate_established": False,
        "development_reused": True,
        "days": days,
    }


def test_numeric_manifest_reports_strata_and_no_false_alarm_claim(numeric_report):
    result = triage.analyze(numeric_report)
    assert result["totals"]["sharpness_3_consecutive"][
        "selected_window_candidate_episode_starts"] == 3
    assert result["days"]["day3"]["sampling_audit"]["pre_event_selected"] == 0
    assert result["days"]["day3"]["sampling_audit"]["pre_event_predeclared_skipped_overlap"] == 4
    manifest = result["days"]["day3"]["candidate_window_triage"]
    assert len(manifest) == 1
    assert manifest[0]["start_frame"] == 100
    assert manifest[0]["not_an_adjudicated_false_alert"] is True
    assert result["full_day_false_alert_rate_established"] is False
    assert result["operator_incidents_changed"] is False


def test_numeric_reporting_must_match_each_window(numeric_report):
    numeric_report["days"]["day4"]["policies"][
        "sharpness_3_consecutive"]["candidate_episode_starts_on_annotated_normal"] = 44
    with pytest.raises(ValueError, match="Summary candidate counts"):
        triage.analyze(numeric_report)


def test_unqualified_sources_fail_closed(numeric_report):
    numeric_report["days"]["day3"]["source_reference_is_physical_camera_approved"] = True
    with pytest.raises(ValueError, match="Research-only gate mismatch"):
        triage.analyze(numeric_report)


def test_overlapping_windows_are_rejected_for_double_counting(numeric_report):
    x = numeric_report["days"]["day3"]
    x["windows"].append(deepcopy(x["windows"][0]))
    x["selected_window_count"] = 2
    x["sampling_audit"]["selected_windows"] = 2
    x["sampling_audit"]["selected_time_strata"] = 2
    x["sampled_numeric_positions"] = 180
    x["approx_annotated_normal_sample_hours"] = 0.1
    with pytest.raises(ValueError, match="Duplicate or overlapping"):
        triage.analyze(numeric_report)


def test_invalid_evidence_state_and_true_camera_health_rejected(numeric_report):
    x = numeric_report["days"]["day3"]["windows"][0]
    x["comparison_states"] = {"KNOWN_HEALTHY": 90}
    with pytest.raises(ValueError, match="Unexpected evidence state"):
        triage.analyze(numeric_report)


def test_no_warning_window_does_not_generate_a_review_request(numeric_report):
    x = numeric_report["days"]["day4"]
    x["windows"][0] = make_window(episodes=0)
    for policy in POLICIES:
        x["policies"][policy]["candidate_episode_starts_on_annotated_normal"] = 0
        x["policies"][policy]["candidate_active_samples_on_annotated_normal"] = 0
        x["policies"][policy]["control_windows_with_any_candidate"] = 0
    report = triage.analyze(numeric_report)
    assert report["days"]["day4"]["candidate_window_triage"] == []


def _events():
    return [
        {"kind":2,"start_frame":n,"end_frame":n+30}
        for n in (900, 1800, 2700, 3600, 4500, 5400, 6300, 7200)
    ]


def _labels():
    labels=np.zeros(8200,dtype=np.uint8)
    for ev in _events():
        labels[ev["start_frame"]-1:ev["end_frame"]]=ev["kind"]
    return labels


def test_pre_event_selector_repairs_collided_quantiles_without_scores():
    labels = _labels()
    events = _events()
    # Mimic original control coverage blocking four pre-event quantile
    # slots, but leave several other pre-event windows eligible.
    old = [
        {"start_frame":events[i]["start_frame"]-90,
         "end_frame":events[i]["start_frame"]-1}
        for i in (0,2,4,6)
    ]
    windows,audit=repairs.select_missing_pre_event_controls(
        labels,events,old,fps=1,window_seconds=90,take=4)
    assert len(windows)==4
    assert audit["selected_new_pre_event_windows"]==4
    assert audit["existing_windows_retained_without_reprocessing"]==4
    assert audit["no_model_score_driven_window_selection"] is True
    assert all(np.all(labels[w["start_frame"]-1:w["end_frame"]]==0) for w in windows)
    assert all(not repairs._overlap(a,b) for a in windows for b in old)
    assert all(not repairs._overlap(a,b) for i,a in enumerate(windows) for b in windows[i+1:])


def test_impossible_pre_event_controls_are_not_fabricated():
    labels=np.ones(1000,dtype=np.uint8)
    selected,audit=repairs.select_missing_pre_event_controls(
        labels,[{"kind":1,"start_frame":400,"end_frame":500}],[],
        fps=1,window_seconds=90,take=4)
    assert selected==[]
    assert audit["selected_new_pre_event_windows"]==0
    assert audit["unfilled_pre_event_targets"]==4


def test_previous_bad_normal_window_refused():
    with pytest.raises(ValueError,match="not all annotated normal"):
        repairs.select_missing_pre_event_controls(
            _labels(),_events(),
            [{"start_frame":900,"end_frame":1000}],
            fps=1,window_seconds=90,take=4)


@pytest.mark.parametrize("options", [
    {"fps":0}, {"window_seconds":30}, {"take":13}, {"take":-1}
])
def test_invalid_selection_parameters_refused(options):
    arguments={"fps":1,"window_seconds":90,"take":4}
    arguments.update(options)
    with pytest.raises(ValueError,match="Invalid bounded"):
        repairs.select_missing_pre_event_controls(
            _labels(),_events(),[],**arguments)
