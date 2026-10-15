"""Privacy-safe Phase 3C public baseline diagnostics; no accuracy claims."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.run_real_public_video_pipeline import (  # noqa: E402
    public_annotation_diagnostic,
    temporal_diagnostic,
)


def _sample(raw=None, confirmed=None, smoothed=None, *,
            frame=10, warm=True, trusted=True, eligible=True):
    return {
        "frame_index": frame, "second": frame / 5,
        "camera_trusted": trusted, "warmup_complete": warm,
        "detector_eligible": eligible, "raw_count": raw,
        "candidate_count": 0 if eligible else None,
        "confirmed_count": confirmed, "registered_count": 0 if eligible else None,
        "smoothed_count": smoothed,
        "decoded_frame_sha256": "should-never-be-exported",
        "track_id": 9999,
    }


def test_empty_or_withheld_samples_never_become_zero_occupancy_evidence():
    report = temporal_diagnostic([
        _sample(frame=0, raw=None, confirmed=None, smoothed=None,
                warm=False, eligible=False),
    ])
    assert report["classification"] == "no_eligible_post_warmup_samples"
    assert report["peak_raw_count"] is None
    assert report["eligible_post_warmup_samples"] == 0
    assert "decoded_frame_sha256" not in str(report)
    assert "track_id" not in str(report)
    assert report["sampling_trace"][0]["raw_count"] is None


def test_stage_attribution_distinguishes_detector_tracking_and_smoothing():
    assert temporal_diagnostic([_sample(0, 0, 0)])["classification"] == (
        "no_raw_detections_in_eligible_samples")
    assert temporal_diagnostic([_sample(1, 0, 0)])["classification"] == (
        "raw_detections_without_confirmed_tracks")
    assert temporal_diagnostic([_sample(1, 1, 0)])["classification"] == (
        "confirmed_tracks_without_positive_smoothed_occupancy")
    result = temporal_diagnostic([_sample(2, 1, 1)])
    assert result["classification"] == "positive_smoothed_occupancy_observed"
    assert result["peak_raw_count"] == 2
    assert result["peak_confirmed_count"] == 1
    assert result["post_warmup_smoothed_positive_samples"] == 1


def test_public_annotation_overlap_does_not_convert_missing_spans_to_truth(tmp_path):
    truth = tmp_path / "epfl-unit-fixture.txt"
    truth.write_text('1 0 0 10 10 4 0 0 0 "PERSON"\n'
                     '1 0 0 10 10 6 0 0 0 "PERSON"\n')
    samples = [
        _sample(None, None, None, frame=0, warm=False, eligible=False),
        _sample(1, 0, 0, frame=4),
        _sample(2, 1, 1, frame=6),
    ]
    result = public_annotation_diagnostic(truth, samples)
    assert result["first_annotated_person_frame"] == 4
    assert result["last_annotated_person_frame"] == 6
    assert result["sampled_frames_in_annotated_person_range"] == 2
    assert result["sampled_frames_with_person_boxes"] == 2
    assert result["post_warmup_samples_with_person_boxes"] == 2
    assert result["annotation_sha256"]
    assert "independently verified empty" in result["interpretation"]
