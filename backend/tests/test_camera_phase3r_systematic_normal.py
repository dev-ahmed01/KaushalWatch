"""Phase 3R normal controls: deterministic selection and non-operational burden."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import run_phase3r_systematic_normal as phase3r  # noqa: E402


def _event(start: int, end: int, kind: int = 2) -> dict:
    return {"start_frame": start, "end_frame": end, "kind": kind}


def test_normal_runs_exact_frame_boundaries():
    labels = np.array([0, 0, 2, 0, 0, 0, 3, 1, 0], dtype=np.uint8)
    assert phase3r._normal_runs(labels) == [(1, 2), (4, 6), (9, 9)]


def test_time_strata_select_only_annotated_normal_even_if_midpoint_is_bad():
    labels = np.zeros(2000, dtype=np.uint8)
    labels[900:960] = 2
    selected, audit = phase3r.choose_controls(
        labels, [_event(901, 960)], fps=1,
        window_seconds=90, time_bins=4, adjacent_each=0,
    )
    assert len(selected) == 4
    assert audit["selected_time_strata"] == 4
    assert audit["unfilled_time_strata"] == 0
    assert all(s["selection"] == "fixed_progress_strata" for s in selected)
    assert all(np.all(labels[s["start_frame"]-1:s["end_frame"]] == 0)
               for s in selected)
    assert all(not phase3r._overlap(a, b)
               for i, a in enumerate(selected) for b in selected[i+1:])
    assert audit["time_strata"][1]["not_day_night_or_wallclock_time"] is True


def test_missing_time_strata_reported_not_silently_resampled():
    labels = np.full(2000, 3, dtype=np.uint8)
    labels[:500] = 0
    selected, audit = phase3r.choose_controls(
        labels, [], fps=1, window_seconds=90, time_bins=4,
        adjacent_each=0,
    )
    assert len(selected) == 1
    assert audit["unfilled_time_strata"] == 3
    assert sum(not b["selected"] for b in audit["time_strata"]) == 3
    assert all("skip_reason" in b for b in audit["time_strata"] if not b["selected"])


def test_event_adjacency_is_normal_label_conditioned_and_disjoint():
    labels = np.zeros(4000, dtype=np.uint8)
    events = [_event(800, 820), _event(1800, 1820),
              _event(3000, 3020)]
    for event in events:
        labels[event["start_frame"]-1:event["end_frame"]] = event["kind"]
    windows, audit = phase3r.choose_controls(
        labels, events, fps=1, window_seconds=90, time_bins=4,
        adjacent_each=3,
    )
    assert len(windows) <= 10
    assert audit["event_adjacency"]["before"]["fully_normal_eligible_candidates"] == 3
    assert audit["event_adjacency"]["after"]["fully_normal_eligible_candidates"] == 3
    for window in windows:
        assert np.all(labels[window["start_frame"]-1:window["end_frame"]] == 0)
    assert all(not phase3r._overlap(a, b)
               for i, a in enumerate(windows) for b in windows[i+1:])


def test_quantile_selection_is_deterministic_and_unique():
    assert phase3r._quantile_indices(24, 4) == [3, 9, 15, 21]
    assert phase3r._quantile_indices(3, 9) == [0, 1, 2]
    assert phase3r._quantile_indices(0, 4) == []
    with pytest.raises(ValueError):
        phase3r._quantile_indices(-1, 4)


def test_no_healthy_control_window_is_not_replaced_by_bad_footage():
    labels = np.ones(2400, dtype=np.uint8)
    selected, audit = phase3r.choose_controls(
        labels, [_event(1, 2400, kind=1)], fps=1,
        window_seconds=90, time_bins=12, adjacent_each=2,
    )
    assert selected == []
    assert audit["selected_windows"] == 0
    assert audit["unfilled_time_strata"] == 12


def test_single_numeric_spike_starts_only_one_unconfirmed_episode():
    step = 2.0
    window = {
        "selection": "test", "control_stratum": "progress_1",
        "start_frame": 1, "end_frame": 181,
        "samples": [],
    }
    for i in range(91):
        current = .10 if i == 40 else 1.0
        previous = .10 if i-15 == 40 else 1.0
        ratio = round(current/previous, 6) if i >= 15 else None
        window["samples"].append({
            "sample_frame": 1+2*i,
            "annotation_class_for_posthoc_evaluation_only": "normal",
            "comparison_state": (
                "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION" if ratio is not None
                else "INSUFFICIENT_PAST_SAMPLE_COVERAGE"
            ),
            "paired_sharpness_ratio": ratio,
            "sharpness_relative_to_unchanged_fixed_reference": current,
            "quality_hypothesis": "NO_SHARPNESS_LOSS_SIGNAL",
            "exploratory_drop_0_5": ratio <= 0.5 if ratio is not None else None,
            "confounds": (
                ["SPATIAL_EVIDENCE_NOT_MEASURED", "RAW_SCENE_CUE_NOT_MEASURED"]
                if ratio is not None else []
            ),
        })
    report = phase3r._summarize_window(window, step)
    assert report["policies"]["phase3p_original_unmodified"]["candidate_episode_starts"] == 1
    assert report["policies"]["sharpness_only_numeric"]["candidate_episode_starts"] == 1
    assert report["policies"]["sharpness_2_of_previous_3"]["candidate_episode_starts"] == 0
    assert report["policies"]["sharpness_3_consecutive"]["candidate_episode_starts"] == 0
    assert report["comparison_states"]["INSUFFICIENT_PAST_SAMPLE_COVERAGE"] == 15
    assert report["camera_image_healthy_verified"] is False
    assert report["production_action_authorized"] is False


def test_any_non_normal_label_inside_report_is_rejected():
    record = {
        "samples": [{
            "annotation_class_for_posthoc_evaluation_only": "defocused",
        }],
    }
    with pytest.raises(ValueError, match="inconsistent decoded sample labels"):
        phase3r._summarize_window(record, 2.0)


def test_run_day_no_candidate_still_reports_empty_sampling_audit(monkeypatch, tmp_path):
    labels = np.full(3000, 3, dtype=np.uint8)
    stored = {"in_memory_development_reference_pixel_sha256": "a"*64}
    info = {"fps": 2, "video_sha256": "v"*64,
            "annotations_sha256": "b"*64}
    reference = np.full((144, 192, 3), 100, dtype=np.uint8)

    monkeypatch.setattr(
        phase3r, "_verify_day",
        lambda *_args, **_kwargs: (info, stored, labels,
                                  [_event(1, 3000, 3)], reference),
    )

    class Cap:
        def isOpened(self):
            return True

        def release(self):
            pass

    monkeypatch.setattr(phase3r.cv2, "VideoCapture", lambda _: Cap())
    monkeypatch.setattr(
        phase3r.VisibilityQualityShadow, "from_bgr",
        lambda frame: object(),
    )
    evidence = phase3r.run_day(
        video=tmp_path / "video.avi",
        annotations=tmp_path / "annotations.csv",
        report=tmp_path / "full.json",
        time_bins=4, adjacent_each=2,
        window_seconds=90, sample_seconds=2,
    )
    assert evidence["selected_window_count"] == 0
    assert evidence["sampling_audit"]["unfilled_time_strata"] == 4
    assert evidence["policies"]["sharpness_3_consecutive"][
        "candidate_episode_starts_on_annotated_normal"
    ] == 0
    assert evidence["full_day_detector_replayed"] is False
    assert evidence["operational_incident_or_reference_mutated"] is False
    assert evidence["source_reference_is_physical_camera_approved"] is False


@pytest.mark.parametrize("bad", [
    {"window_seconds": 30},
    {"time_bins": 1},
    {"time_bins": 33},
    {"adjacent_each": -1},
    {"adjacent_each": 13},
    {"fps": 0},
])
def test_bad_sampling_configuration_rejected(bad):
    labels = np.zeros(3000, dtype=np.uint8)
    options = {"fps": 1, "window_seconds": 90, "time_bins": 4,
               "adjacent_each": 1}
    options.update(bad)
    with pytest.raises(ValueError, match="Invalid bounded"):
        phase3r.choose_controls(labels, [], **options)
