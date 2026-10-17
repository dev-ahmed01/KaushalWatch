"""Phase 3Q numeric-only continuation counterfactual trust-boundary tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_phase3q_numeric_continuity import analyze  # noqa: E402


def _window(kind: str, *, target_index: int = 30,
            sustained: bool = True, edge_denominator_missing: bool = False) -> dict:
    n = 91
    start_frame = 100
    target_frame = start_frame + target_index * 2
    end_event = target_frame + 40
    sharp = [1.0 for _ in range(n)]
    if kind == "defocused":
        for i in range(target_index, n):
            sharp[i] = 0.1
    elif kind == "normal_control":
        if sustained:
            sharp[45] = 0.1   # Single isolated normal-period dip.
    labels = []
    samples = []
    for i in range(n):
        frame = start_frame + i*2
        label = ("normal" if kind == "normal_control"
                 else kind if target_frame <= frame <= end_event else "normal")
        labels.append(label)
        past = sharp[i-15] if i >= 15 else None
        valid = (i >= 15 and past is not None and past > 1e-6
                 and not edge_denominator_missing)
        original = round(sharp[i]/past, 6) if valid else None
        conf = (["SPATIAL_EVIDENCE_NOT_MEASURED", "RAW_SCENE_CUE_NOT_MEASURED"]
                if original is not None else [])
        samples.append({
            "sample_frame": frame,
            "annotation_class_for_posthoc_evaluation_only": label,
            "offset_from_target_start_seconds_for_posthoc_analysis":
                (None if kind == "normal_control" else (frame-target_frame)),
            "comparison_state": (
                "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION" if valid else
                "INSUFFICIENT_PAST_SAMPLE_COVERAGE" if i < 15 else
                "NONINFORMATIVE_PAST_DENOMINATOR_ABSTAIN"
            ),
            "paired_sharpness_ratio": original,
            "sharpness_relative_to_unchanged_fixed_reference": sharp[i],
            "exploratory_drop_0_5": (original <= 0.5 if original is not None else None),
            "quality_hypothesis": "ILLUMINATION_CONFOUNDED",
            "confounds": conf,
        })
    return {
        "kind": kind,
        "start_frame": start_frame,
        "end_frame": start_frame+(n-1)*2,
        "target_event_start_frame": target_frame if kind != "normal_control" else None,
        "target_event_end_frame": end_event if kind != "normal_control" else None,
        "frames_or_media_exported": False,
        "sample_seconds_requested": 2.0,
        "samples": samples,
    }


@pytest.fixture
def report():
    days = {}
    for day in ("day3", "day4"):
        # Exercise missing original combined denominator on one of the days.
        ws = [
            _window("defocused", edge_denominator_missing=(day == "day4")),
            _window("moved", sustained=False),
            _window("normal_control"),
        ]
        days[day] = {
            "status": "PHASE3P_BOUNDED_CAUSAL_DEVELOPMENT_REPLAY_NOT_HELD_OUT",
            "production_qualified": False,
            "reference_is_approved": False,
            "source_is_held_out": False,
            "full_day_detector_replayed": False,
            "scene_raw_review_status_measured": False,
            "spatial_evidence_status_measured": False,
            "automatic_reference_reset_or_recovery": False,
            "video_or_images_exported": False,
            "sample_rate_seconds": 2.0,
            "summary": {
                k: {"selected_windows": 1}
                for k in ("defocused", "moved", "normal_control")
            },
            "windows": ws,
        }
    return {
        "status": "PHASE3P_BOUNDED_TWO_DAY_CAUSAL_NUMERIC_EVIDENCE_ONLY",
        "all_video_frames_replayed": False,
        "automatic_reference_reset_or_recovery": False,
        "media_exported": False,
        "operational_alerts_modified": False,
        "production_qualified": False,
        "days": days,
    }


def test_causal_quality_flags_without_event_label_input(report):
    result = analyze(report)
    assert result["sampled_windows_total"] == 6
    assert result["production_qualified"] is False
    assert result["threshold_tuned_or_selected"] is False
    assert result["original_scene_warning_cues_modified"] is False
    original = result["days"]["day3"]["policies"]["phase3p_original_unmodified"]
    assert original["defocused"]["windows_with_any_candidate_during_target"] == 1
    assert original["defocused"]["median_first_fresh_candidate_s_when_present"] == 0
    assert result["days"]["day4"]["policies"]["phase3p_original_unmodified"]["defocused"][
        "windows_with_any_candidate_during_target"
    ] == 0
    axis = result["days"]["day4"]["policies"]["sharpness_only_numeric"]
    assert axis["defocused"]["windows_with_any_candidate_during_target"] == 1
    assert result["numeric_coverage_all_windows"][
        "sharpness_available_despite_combined_abstention"
    ] > 0


def test_consecutive_confirmation_adds_two_to_four_seconds_delay(report):
    result = analyze(report)
    scores = result["days"]["day3"]["policies"]
    assert scores["sharpness_only_numeric"]["defocused"][
        "first_fresh_candidate_offsets_s"
    ] == [0]
    assert scores["sharpness_2_of_previous_3"]["defocused"][
        "first_fresh_candidate_offsets_s"
    ] == [2]
    assert scores["sharpness_3_consecutive"]["defocused"][
        "first_fresh_candidate_offsets_s"
    ] == [4]


def test_sparse_normal_dip_fails_three_consecutive(report):
    result = analyze(report)
    raw = result["days"]["day3"]["policies"]["sharpness_only_numeric"]
    sustained = result["days"]["day3"]["policies"]["sharpness_3_consecutive"]
    assert raw["normal_control"]["windows_with_any_candidate"] == 1
    assert sustained["normal_control"]["windows_with_any_candidate"] == 0
    assert sustained["normal_control"]["annotated_normal_candidate_active_samples"] == 0


def test_incomplete_previously_unmeasured_evidence_never_certified(report):
    result = analyze(report)
    assert result["camera_source_reference_approved"] is False
    assert result["held_out_test"] is False
    assert result["real_incident_status_or_notification_modified"] is False
    assert result["media_exported"] is False
    assert all(
        w["candidate_scores"]["sharpness_only_numeric"]["candidate_only_never_operational_incident"]
        for w in result["numeric_per_window_scoring"]
    )


def test_original_ratio_tampering_is_detected(report):
    item = report["days"]["day3"]["windows"][0]["samples"][30]
    item["paired_sharpness_ratio"] = 0.9
    item["exploratory_drop_0_5"] = False
    with pytest.raises(ValueError, match="Reconstructed paired ratio"):
        analyze(report)


def test_wrong_unqualified_status_rejected(report):
    report["days"]["day4"]["scene_raw_review_status_measured"] = True
    with pytest.raises(ValueError, match="release/missing-evidence"):
        analyze(report)


def test_nonfinite_sharpness_rejected(report):
    report["days"]["day3"]["windows"][0]["samples"][10][
        "sharpness_relative_to_unchanged_fixed_reference"
    ] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        analyze(report)


def test_invalid_window_denominator_rejected(report):
    report["days"]["day3"]["summary"]["normal_control"]["selected_windows"] = 0
    with pytest.raises(ValueError, match="denominator mismatch"):
        analyze(report)


def test_original_flag_mismatch_rejected(report):
    sample = report["days"]["day3"]["windows"][0]["samples"][30]
    sample["exploratory_drop_0_5"] = False
    with pytest.raises(ValueError, match="Original causal flag"):
        analyze(report)


def test_missing_history_abstains_not_a_normal_report(report):
    result = analyze(report)
    # First 15 samples/window have no past 30-second observation. They are
    # not counted as healthy or recovered and must never trigger a candidate.
    score = result["numeric_per_window_scoring"][0]
    assert score["numeric_coverage"]["sharpness_only_numeric_abstain"] >= 15


def test_cli_writes_new_json_only_and_refuses_overwrite(report, tmp_path):
    original = tmp_path / "phase3p.json"
    output = tmp_path / "phase3q.json"
    original.write_text(json.dumps(report), encoding="utf-8")
    script = ROOT / "scripts" / "analyze_phase3q_numeric_continuity.py"
    subprocess.run(
        [sys.executable, str(script), "--input", str(original),
         "--out", str(output)],
        check=True, capture_output=True, text=True,
    )
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert parsed["status"] == "PHASE3Q_NUMERIC_COUNTERFACTUAL_RESEARCH_NOT_HELD_OUT"
    assert parsed["media_exported"] is False
    assert json.loads(original.read_text(encoding="utf-8")) == report
    retry = subprocess.run(
        [sys.executable, str(script), "--input", str(original),
         "--out", str(output)],
        capture_output=True, text=True,
    )
    assert retry.returncode != 0
    assert "unused" in retry.stderr
