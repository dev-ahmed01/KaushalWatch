"""Phase3W full-coverage research cue concordance: synthetic invariant tests."""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_phase3w_full_coverage_concordance import summarize  # noqa: E402
from test_camera_phase3v_video_evidence_audit import (  # noqa: E402
    synth_video_report, paired_reports,
)


def full_synthetic_report(r, s):
    """Convert ONLY synthetic 20/day selection to full scalar coverage."""
    report = synth_video_report(r, s)
    baseline = next(x["local_video_evidence"] for x in report["priority_queue"]
                    if x["local_video_evidence"]["status"] ==
                    "UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH")
    for index, item in enumerate(report["priority_queue"]):
        win = deepcopy(baseline)
        win["first_sample_frame"] = item["start_frame"]
        win["last_sample_frame"] = item["end_frame"]
        is_candidate = item["policies"]["sharpness_3_consecutive"]["window_with_candidate"]
        if index in (0, 1, 2, 3, 18):
            win["min_laplacian_ratio_to_first_window_frame"] = 0.3
            win["derived_sparse_feature_assessment"] = (
                "SUBSTANTIAL_SPARSE_SHARPNESS_CHANGE_POSSIBLE"
            )
        item["local_video_evidence"] = win
    report["recordings_available_in_workspace"] = True
    report["video_feature_coverage"] = {
        "selected_windows": 40, "measured_windows": 40,
        "unmeasured_windows": 0, "sampled_video_frames": 480,
        "full_selected_window_coverage": True,
        "sampling_is_development_not_physical_truth": True,
    }
    return report


def test_all_forty_windows_are_disjoint_research_categories(paired_reports):
    r, s = paired_reports
    data = full_synthetic_report(r, s)
    result = summarize(data, r, s)
    assert result["status"] == "PHASE3W_FULL_COVERAGE_RESEARCH_CUES_NOT_PHYSICAL_TRUTH"
    assert result["per_day"]["day3"]["measured_windows"] == 20
    assert result["per_day"]["day4"]["measured_windows"] == 20
    assert sum(result["overall_concordance"].values()) == 40
    assert result["geometry"]["windows_with_unknown_correspondence"] == 40
    assert result["cutoff_is_approved_or_held_out"] is False
    assert result["time_aligned_per_sample_comparison"] is False
    assert result["normal_annotation_is_verified_healthy_image"] is False
    assert result["physical_camera_tampering_proven"] is False
    assert result["field_false_alarm_rate_established"] is False
    assert result["production_qualified"] is False
    assert result["model_tuned_or_alert_policy_changed"] is False
    assert result["media_or_camera_frames_exported"] is False


def test_full_coverage_missing_control_is_rejected(paired_reports):
    r, s = paired_reports
    data = full_synthetic_report(r, s)
    data["priority_queue"][0]["local_video_evidence"]["status"] = "SOURCE_VIDEO_NOT_MOUNTED"
    with pytest.raises(ValueError, match="Full 40 selected"):
        summarize(data, r, s)


def test_misrepresented_full_coverage_rejected(paired_reports):
    r, s = paired_reports
    data = full_synthetic_report(r, s)
    data["video_feature_coverage"]["sampled_video_frames"] = 240
    with pytest.raises(ValueError, match="480-frame"):
        summarize(data, r, s)


def test_duplicate_control_range_rejected(paired_reports):
    r, s = paired_reports
    data = full_synthetic_report(r, s)
    data["priority_queue"][0] = deepcopy(data["priority_queue"][1])
    with pytest.raises(ValueError, match="duplicate"):
        summarize(data, r, s)


def test_unknown_geometry_must_remain_unknown(paired_reports):
    r, s = paired_reports
    data = full_synthetic_report(r, s)
    data["priority_queue"][0]["local_video_evidence"][
        "geometric_proxy_unknown_comparisons"
    ] = 0
    with pytest.raises(ValueError, match="Unknown geometry"):
        summarize(data, r, s)


def test_source_pin_mismatch_rejected(paired_reports):
    r, s = paired_reports
    data = full_synthetic_report(r, s)
    data["source_pins"]["day3"]["video_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Pinned"):
        summarize(data, r, s)


def test_old_bounded_report_cannot_be_misrepresented_as_same_20(paired_reports):
    r, s = paired_reports
    full = full_synthetic_report(r, s)
    old = synth_video_report(r, s)
    # Synthetic older report samples only 2 windows/day (4 total)
    # whereas the real Phase3V prior report has 10/day.
    with pytest.raises(ValueError, match="former bounded 20-window"):
        summarize(full, r, s, old)
