"""Phase 3O offline paired numeric quality regression and trust-boundary tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_phase3o_event_transitions import analyze  # noqa: E402


STAGES = (
    "before_start", "onset", "after_onset_30", "event_end",
    "after_end_30", "after_end_120",
)


def _event(kind: str, start: int, ratio: float, *, confounded=False):
    result = []
    for idx, stage in enumerate(STAGES):
        current = ratio if stage in ("onset", "after_onset_30", "event_end") else 1.0
        hypothesis = (
            "ILLUMINATION_CONFOUNDED" if confounded
            else "NO_SHARPNESS_LOSS_SIGNAL"
        )
        result.append({
            "target_event_class": kind,
            "target_event_start_frame": start,
            "target_event_end_frame": start + 100,
            "stage": stage,
            "sample_frame": start - 10 if stage == "before_start" else start + idx,
            "actual_annotation_class_at_sample": (
                "normal" if stage in ("before_start", "after_end_30",
                                       "after_end_120") else kind
            ),
            "relative_sharpness": current,
            "relative_edge_fraction": current,
            "relative_contrast": 0.9,
            "quality_hypothesis": hypothesis,
            "baseline_event_any_review": kind == "moved",
            "baseline_event_fresh_review": kind == "moved",
        })
    return result


@pytest.fixture
def numeric_report():
    days = {}
    for day in ("day3", "day4"):
        samples = _event("defocused", 100, 0.20, confounded=True)
        samples += _event("moved", 300, 0.85)
        days[day] = {
            "status": "PHASE3N_TARGETED_UNAPPROVED_REFERENCE_DEVELOPMENT_ONLY",
            "production_qualified": False,
            "physical_reference_verified": False,
            "source_is_held_out": False,
            "frames_images_or_crops_exported": False,
            "complete_video_replayed": False,
            "same_unnapproved_in_video_reference_as_phase3m": True,
            "sampled_target_frames": len(samples),
            "sampled_positions": samples,
        }
    return {
        "status": "PHASE3N_TWO_DAY_TARGETED_VISIBILITY_NOT_HELD_OUT",
        "production_qualified": False,
        "media_exported": False,
        "automatic_recovery_or_reference_reset": False,
        "full_day_repeated": False,
        "days": days,
    }


def test_paired_defocus_and_moved_stay_separate(numeric_report):
    result = analyze(numeric_report)
    assert result["production_qualified"] is False
    assert result["thresholds_calibrated"] is False
    assert result["held_out_evaluation"] is False
    assert result["detector_or_scene_reviews_modified"] is False
    assert result["automatic_recovery_or_reference_reset"] is False
    assert result["media_exported"] is False
    defocus = result["pooled"]["defocused"]
    moved = result["pooled"]["moved"]
    assert defocus["sampled_events"] == 2
    assert moved["sampled_events"] == 2
    assert defocus["anchor_illumination_confound_events"] == 2
    assert defocus["baseline_any_scene_review_events"] == 0
    assert moved["baseline_fresh_scene_review_events"] == 2
    assert defocus["stage_ratios"]["after_onset_30"]["median_sharpness_ratio"] == 0.2
    assert moved["stage_ratios"]["after_onset_30"]["median_sharpness_ratio"] == 0.85
    assert defocus["stage_ratios"]["after_onset_30"]["exploratory_sharpness_decline_counts"]["0.5"] == 2
    assert moved["stage_ratios"]["after_onset_30"]["exploratory_sharpness_decline_counts"]["0.5"] == 0


def test_unapproved_illumination_confound_still_retains_numeric_axis(numeric_report):
    result = analyze(numeric_report)
    assert result["pooled"]["defocused"]["hypothesis_at_30s"] == {
        "ILLUMINATION_CONFOUNDED": 2
    }
    assert result["pooled"]["defocused"]["stage_ratios"]["after_onset_30"]["valid_paired_events"] == 2
    assert result["reference_approved"] is False
    assert result["independent_ground_truth"] is False


def test_annotation_nonnormal_anchor_forces_abstention(numeric_report):
    item = numeric_report["days"]["day3"]["sampled_positions"][0]
    item["actual_annotation_class_at_sample"] = "covered"
    result = analyze(numeric_report)
    day = result["days"]["day3"]["summary"]["defocused"]["stage_ratios"]["after_onset_30"]
    assert day["valid_paired_events"] == 0
    assert day["abstained_events"] == 1
    assert day["median_sharpness_ratio"] is None


def test_actual_stage_mismatch_forces_abstention(numeric_report):
    item = numeric_report["days"]["day4"]["sampled_positions"][2]
    item["actual_annotation_class_at_sample"] = "normal"
    result = analyze(numeric_report)
    day = result["days"]["day4"]["summary"]["defocused"]["stage_ratios"]["after_onset_30"]
    assert day["valid_paired_events"] == 0


@pytest.mark.parametrize("field", [
    "production_qualified", "media_exported", "full_day_repeated",
    "automatic_recovery_or_reference_reset",
])
def test_refuses_source_promoted_or_media_exported(numeric_report, field):
    numeric_report[field] = True
    with pytest.raises(ValueError, match="Phase3N source"):
        analyze(numeric_report)


def test_duplicate_event_stage_rejected(numeric_report):
    day = numeric_report["days"]["day3"]
    day["sampled_positions"].append(deepcopy(day["sampled_positions"][0]))
    day["sampled_target_frames"] += 1
    with pytest.raises(ValueError, match="duplicate event stage"):
        analyze(numeric_report)


def test_nonfinite_ratio_rejected(numeric_report):
    numeric_report["days"]["day3"]["sampled_positions"][2]["relative_sharpness"] = float("nan")
    with pytest.raises(ValueError, match="relative_sharpness"):
        analyze(numeric_report)


def test_inconsistent_baseline_event_review_rejected(numeric_report):
    numeric_report["days"]["day3"]["sampled_positions"][3]["baseline_event_any_review"] = True
    with pytest.raises(ValueError, match="inconsistent event metadata"):
        analyze(numeric_report)


def test_cli_outputs_numeric_only_and_never_overwrites_input(numeric_report, tmp_path):
    source = tmp_path / "phase3n.json"
    target = tmp_path / "results" / "phase3o.json"
    source.write_text(json.dumps(numeric_report), encoding="utf-8")
    script = ROOT / "scripts" / "analyze_phase3o_event_transitions.py"
    subprocess.run(
        [sys.executable, str(script), "--input", str(source), "--out", str(target)],
        check=True, capture_output=True, text=True,
    )
    results = json.loads(target.read_text(encoding="utf-8"))
    assert results["status"] == "PHASE3O_PAIRED_TRANSITION_DESCRIPTIVE_RESEARCH_ONLY"
    assert len(results["event_ratios_numeric_only"]) == 4
    assert results["media_exported"] is False
    assert json.loads(source.read_text(encoding="utf-8")) == numeric_report
    attempt = subprocess.run(
        [sys.executable, str(script), "--input", str(source), "--out", str(target)],
        capture_output=True, text=True,
    )
    assert attempt.returncode != 0
    assert "unused" in attempt.stderr


def test_only_numeric_event_identifiers_and_metadata_exported(numeric_report):
    result = analyze(numeric_report)
    text = json.dumps(result).lower()
    assert "data:image" not in text
    assert "base64" not in text
    assert "frame_crop" not in text
    assert result["production_integration"] is False
