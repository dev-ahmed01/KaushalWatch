"""Bounded Phase3P offline sampler: deterministic selection, numeric-only outputs."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import run_phase3p_bounded_causal_quality as runner  # noqa: E402
from app.services.camera_causal_temporal_quality_shadow import CausalTemporalQualityShadow

PIN = "a" * 64


def _events(kind, begins, span=100):
    return [
        {"kind": kind, "start_frame": n, "end_frame": n+span}
        for n in begins
    ]


def test_evenly_spaced_selection_is_stable_and_keeps_short_lists_complete():
    all_events = _events(2, [100, 200, 300])
    assert [x["start_frame"] for x in runner._sample_events(
        all_events, kind=2, count=6
    )] == [100, 200, 300]
    all_events = _events(2, [100 + 100*i for i in range(24)])
    chosen = runner._sample_events(all_events, kind=2, count=6)
    assert len(chosen) == 6
    assert len(set(x["start_frame"] for x in chosen)) == 6


def test_windows_fixed_by_annotations_not_detector_outputs():
    labels = np.zeros(10000, dtype=np.uint8)
    events = _events(2, [1000, 2500]) + _events(3, [5000, 7000])
    for item in events:
        labels[item["start_frame"]-1:item["end_frame"]] = item["kind"]
    windows, skipped = runner._window_specs(
        labels, events, fps=10, count_per_kind=2, normal_control_windows=2,
    )
    selected = [w for w in windows if w["kind"] != "normal_control"]
    assert len(selected) == 4
    assert sum(w["kind"] == "defocused" for w in selected) == 2
    assert sum(w["kind"] == "moved" for w in selected) == 2
    assert len(windows) == 4 + 2 - len(skipped)
    for win in windows:
        if win["kind"] == "normal_control":
            assert np.all(labels[win["start_frame"]-1:win["end_frame"]] == 0)


def test_sparse_actual_video_window_treated_as_scene_unknown(monkeypatch):
    class FakeQuality:
        def inspect(self, frame):
            idx = int(frame[0, 0, 0])
            # Synthetic camera: absolute quality goes down after second 30
            sharpness = 0.10 if idx >= 30 else 1.0
            return {
                "status": "OFFLINE_UNCALIBRATED_VISIBILITY_AXES",
                "quality_hypothesis": "NO_SHARPNESS_LOSS_SIGNAL",
                "relative_sharpness": sharpness,
                "relative_edge_fraction": sharpness,
                "relative_contrast": 1.0,
                "production_integration": False,
                "automatic_recovery": False,
                "blur_or_defocus_proven": False,
                "image_usable_verified": False,
                "detector_review_suppressed": False,
            }

    def fake_frame(cap, n, expected_shape):
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        frame[0, 0, 0] = n-1
        return frame

    monkeypatch.setattr(runner, "_read_exact_frame", fake_frame)
    labels = np.zeros(140, dtype=np.uint8)
    labels[30:90] = 2
    spec = {
        "kind": "defocused", "start_frame": 1, "end_frame": 100,
        "target_event_start_frame": 31, "target_event_end_frame": 90,
        "selection": "predeclared_event_quantiles",
    }
    result = runner._replay_window(
        object(), spec, info={"fps": 1, "height": 4, "width": 4},
        pin=PIN, labels=labels, visibility=FakeQuality(),
        sample_seconds=1.0,
    )
    assert len(result["samples"]) == 100
    at_30 = result["samples"][30]
    assert at_30["annotation_class_for_posthoc_evaluation_only"] == "defocused"
    assert at_30["offset_from_target_start_seconds_for_posthoc_analysis"] == 0
    assert at_30["paired_sharpness_ratio"] == 0.1
    assert "RAW_SCENE_CUE_NOT_MEASURED" in at_30["confounds"]
    assert "SPATIAL_EVIDENCE_NOT_MEASURED" in at_30["confounds"]
    assert result["observer_summary"]["production_qualified"] is False
    assert result["frames_or_media_exported"] is False


def test_unavailable_raw_review_and_spatial_evidence_remain_unknown():
    observer = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        from app.services.camera_causal_temporal_quality_shadow import QUALITY_HYPOTHESES
        assert "NO_SHARPNESS_LOSS_SIGNAL" in QUALITY_HYPOTHESES
        doc = {
            "status": "OFFLINE_UNCALIBRATED_VISIBILITY_AXES",
            "quality_hypothesis": "NO_SHARPNESS_LOSS_SIGNAL",
            "relative_sharpness": 1.0, "relative_edge_fraction": 1.0,
            "relative_contrast": 1.0, "production_integration": False,
            "automatic_recovery": False, "blur_or_defocus_proven": False,
            "image_usable_verified": False, "detector_review_suppressed": False,
        }
        r = observer.observe(
            time_s=t, reference_pixel_sha256=PIN, features=doc,
            spatial_evidence_status="NOT_MEASURED", raw_scene_review=None,
        )
    assert r["raw_scene_review_seen"] is None
    assert r["paired_numeric_ratios"]["sharpness"] == 1.0
    assert "RAW_SCENE_CUE_NOT_MEASURED" in r["confounds"]
    assert r["scene_warning_suppressed"] is False


def test_frame_level_scene_evidence_must_not_be_fabricated_bool():
    observer = CausalTemporalQualityShadow(PIN)
    doc = {
        "status": "OFFLINE_UNCALIBRATED_VISIBILITY_AXES",
        "quality_hypothesis": "NO_SHARPNESS_LOSS_SIGNAL",
        "relative_sharpness": 1.0, "relative_edge_fraction": 1.0,
        "relative_contrast": 1.0, "production_integration": False,
        "automatic_recovery": False, "blur_or_defocus_proven": False,
        "image_usable_verified": False, "detector_review_suppressed": False,
    }
    with pytest.raises(ValueError, match="spatial evidence"):
        observer.observe(
            time_s=0, reference_pixel_sha256=PIN, features=doc,
            spatial_evidence_status="UNVERIFIED", raw_scene_review="false",
        )
