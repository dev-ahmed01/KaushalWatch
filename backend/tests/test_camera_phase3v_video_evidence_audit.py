"""Phase3V: local numerical video audit guards and source continuity."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_phase3v_container_video_evidence import audit  # noqa: E402
from prepare_phase3t_blinded_reviews import build_sources, POLICIES  # noqa: E402
from test_camera_phase3t_blinded_reviews import paired_reports  # noqa: E402, F401


def synth_video_report(r, s):
    """Synthetic scalar evidence for source-invariant testing, never real media."""
    merged = build_sources(r, s)
    rows, by_day, pins = [], {}, {}
    for day in ("day3", "day4"):
        original = r["days"][day]
        pins[day] = {
            "video_sha256": original["source_video_sha256"],
            "annotations_sha256": original["source_annotations_sha256"],
            "unapproved_development_reference_sha256":
                original.get("frozen_unapproved_reference_pixel_sha256"),
        }
        by_day[day] = {
            "window_count": len(merged[day]),
            "selected_normal_labeled_hours": len(merged[day]) * 180 / 3600,
            "policy_candidates": {},
        }
        for policy in POLICIES:
            policy_scores = [x["candidate_policies"][policy]
                             for x in merged[day]]
            by_day[day]["policy_candidates"][policy] = {
                "candidate_episode_starts": sum(
                    x["candidate_episode_starts"] for x in policy_scores
                ),
                "candidate_active_samples": sum(
                    x["candidate_active_samples"] for x in policy_scores
                ),
                "windows_with_numeric_candidate": sum(
                    x["candidate_window_has_any_flag"] for x in policy_scores
                ),
                "verified_false_alarms": None,
            }
        for index, control in enumerate(merged[day]):
            start, end = control["start_frame"], control["end_frame"]
            measured = index < 2
            evidence = {
                "status": (
                    "UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH"
                    if measured else "SOURCE_VIDEO_NOT_MOUNTED"
                ),
                "physical_camera_health_verified": False,
                "has_independent_visual_truth": False,
            }
            if measured:
                evidence.update({
                    "sampled_source_frames": 12,
                    "first_sample_frame": start,
                    "last_sample_frame": end,
                    "video_or_frames_exported": False,
                    "camera_tamper_event_proven": False,
                    "scene_incident_or_recovery_changed": False,
                    "approved_camera_reference_used": False,
                    "feature_cutoff_not_production_approved": True,
                    "scene_geometry_proxy_not_camera_displacement_truth": True,
                    "first_frame_laplacian_variance": 9.0,
                    "last_frame_laplacian_variance": 7.0,
                    "min_laplacian_ratio_to_first_window_frame": 0.65,
                    "max_luma_delta_between_sparse_samples": 10.0,
                    "mean_luma_range": 20.0,
                    "geometric_proxy_supported_comparisons": 0,
                    "geometric_proxy_unknown_comparisons": 11,
                    "max_normalized_center_displacement_proxy": None,
                    "derived_sparse_feature_assessment":
                        "NO_LARGE_SPARSE_SHARPNESS_CHANGE_OBSERVED",
                })
            rows.append({
                "id": f"{day}-{start}-{end}",
                "day": day,
                "start_frame": start, "end_frame": end,
                "source_phase": control["source_phase"],
                "stratum": control["stratum_hidden_from_reviewers"],
                "physical_condition_verified": False,
                "independent_ground_truth": False,
                "policies": {
                    name: {
                        "episodes": control["candidate_policies"][name][
                            "candidate_episode_starts"
                        ],
                        "active_samples": control["candidate_policies"][name][
                            "candidate_active_samples"
                        ],
                        "window_with_candidate": control["candidate_policies"][name][
                            "candidate_window_has_any_flag"
                        ],
                    }
                    for name in POLICIES
                },
                "local_video_evidence": evidence,
            })
    return {
        "status": "OFFLINE_DEVELOPMENT_EVIDENCE_ANALYZED_NO_PHYSICAL_TRUTH",
        "source_evidence_sha256": hashlib.sha256(
            (json.dumps(r, sort_keys=True) + "\n" +
             json.dumps(s, sort_keys=True)).encode()
        ).hexdigest(),
        "source_pins": pins,
        "by_day": by_day,
        "priority_queue": rows,
        "number_of_windows": len(rows),
        "selected_normal_labeled_hours": len(rows)*180/3600,
        "production_qualified": False,
        "independent_camera_authentication": False,
        "false_alarm_rate_known": False,
        "incident_recovery_authorized": False,
        "recordings_available_in_workspace": True,
    }


def test_two_day_synthetic_coverage_and_legacy_budget_label(paired_reports):
    r, s = paired_reports
    report = synth_video_report(r, s)
    result = audit(report, r, s)
    assert result["selected_windows"] == 40
    assert result["windows_with_scalar_video_features"] == 4
    assert result["windows_without_scalar_video_features"] == 36
    assert result["legacy_windows_mislabeled_video_not_mounted_despite_sampler_budget"] == 36
    assert result["production_qualified"] is False
    assert result["source_video_sha_recomputed_during_this_report_audit"] is False
    assert result["field_false_alert_rate_established"] is False


@pytest.mark.parametrize("mutation,expected", [
    ("wrong_checksum", "checksum"),
    ("fake_physical_truth", "physical"),
    ("fake_field_rate", "physical"),
    ("wrong_source", "Pinned"),
    ("wrong_candidate_count", "Numeric candidate"),
    ("duplicate_case", "duplicate"),
    ("extra_frame", "frame bounds"),
    ("bad_luma", "luma"),
    ("missing_geometry", "Unknown geometry"),
    ("wrong_sparse_label", "Exploratory"),
])
def test_corrupt_or_overclaimed_video_evidence_fails_closed(
    paired_reports, mutation, expected
):
    r, s = paired_reports
    report = synth_video_report(r, s)
    entry = report["priority_queue"][0]
    video = entry["local_video_evidence"]
    if mutation == "wrong_checksum":
        report["source_evidence_sha256"] = "0"*64
    elif mutation == "fake_physical_truth":
        report["independent_camera_authentication"] = True
    elif mutation == "fake_field_rate":
        report["false_alarm_rate_known"] = True
    elif mutation == "wrong_source":
        report["source_pins"]["day3"]["video_sha256"] = "0"*64
    elif mutation == "wrong_candidate_count":
        entry["policies"]["sharpness_3_consecutive"]["episodes"] += 1
    elif mutation == "duplicate_case":
        report["priority_queue"][1] = deepcopy(entry)
    elif mutation == "extra_frame":
        video["sampled_source_frames"] = 1000
    elif mutation == "bad_luma":
        video["mean_luma_range"] = 900.0
    elif mutation == "missing_geometry":
        video["geometric_proxy_unknown_comparisons"] = 0
    elif mutation == "wrong_sparse_label":
        video["derived_sparse_feature_assessment"] = (
            "SUBSTANTIAL_SPARSE_SHARPNESS_CHANGE_POSSIBLE"
        )
    with pytest.raises(ValueError, match=expected):
        audit(report, r, s)


def test_no_video_cannot_claim_source_mounted(paired_reports):
    r, s = paired_reports
    report = synth_video_report(r, s)
    for item in report["priority_queue"]:
        item["local_video_evidence"] = {
            "status": "SOURCE_VIDEO_NOT_MOUNTED",
            "physical_camera_health_verified": False,
            "has_independent_visual_truth": False,
        }
    with pytest.raises(ValueError, match="availability contradiction"):
        audit(report, r, s)


def test_new_budget_skip_status_accepted_without_fake_video(paired_reports):
    r, s = paired_reports
    report = synth_video_report(r, s)
    for item in report["priority_queue"]:
        if item["local_video_evidence"]["status"] == "SOURCE_VIDEO_NOT_MOUNTED":
            item["local_video_evidence"]["status"] = (
                "NOT_SELECTED_FOR_BOUNDED_VIDEO_SAMPLING"
            )
    checked = audit(report, r, s)
    assert checked["windows_without_scalar_video_features"] == 36
    assert checked[
        "legacy_windows_mislabeled_video_not_mounted_despite_sampler_budget"
    ] == 0
