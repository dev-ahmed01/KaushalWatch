"""Synthetic numeric-only regression tests for the ranked continuous failure map."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from report_uhctd_continuous_failure_map import summarize_one  # noqa: E402


def fixture(directory: Path, *, unbalanced=False, missing_hourly=False):
    directory.mkdir()
    report = {
        "status": "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT",
        "qualified": False,
        "production_integration": False,
        "effective_sample_seconds": 1.0,
        "methods": {"fusion": {
            "normal_review_samples": 4,
            "normal_review_fraction": 0.2,
            "new_normal_review_episodes_per_normal_hour": 3.0,
        }},
        "normal_review_hours": [
            {
                "hour_from_recording_start": 0,
                "normal_samples": 10, "spatial_review_samples": 2,
                "fusion_review_samples": 2,
                "fusion_from_spatial_samples": 2,
                "fusion_from_global_fallback_samples": 0,
                "global_quality_limited_samples": 1,
                "unknown_low_texture_samples": 1, "new_fusion_review_episodes": 1,
            },
            {
                "hour_from_recording_start": 1,
                "normal_samples": 10, "spatial_review_samples": 1,
                "fusion_review_samples": 3 if unbalanced else 2,
                "fusion_from_spatial_samples": 1,
                "fusion_from_global_fallback_samples": 1,
                "global_quality_limited_samples": 0,
                "unknown_low_texture_samples": 1, "new_fusion_review_episodes": 1,
            },
        ],
    }
    if missing_hourly:
        report.pop("normal_review_hours")
    (directory / "continuous_shadow_summary.json").write_text(json.dumps(report))
    with (directory / "continuous_shadow_normal_review_episodes.csv").open(
        "w", newline=""
    ) as out:
        writer = csv.writer(out)
        writer.writerow([
            "start_frame", "end_frame", "samples",
            "spatial_cue_samples", "global_fallback_samples",
            "start_seconds", "end_seconds", "already_alerted_before_normal_span",
        ])
        writer.writerow([5, 6, 2, 2, 0, 4, 5, False])
        writer.writerow([3605, 3606, 2, 1, 1, 3604, 3605, True])
    return directory


def test_ranked_map_reconciles_hour_bins_episodes_and_sources(tmp_path):
    result = summarize_one(fixture(tmp_path / "sample"), top=2)
    assert result["annotation_normal_review_samples"] == 4
    assert result["fusion_spatial_source_samples"] == 3
    assert result["fusion_global_fallback_samples"] == 1
    assert result["normal_review_spans"] == 2
    assert result["carried_from_prior_label_spans"] == 1
    assert [x["hour_from_start"] for x in result["top_hours_by_review_sample_volume"]] == [0, 1]
    assert [x["hour_from_start"] for x in result["top_hours_by_new_review_episodes"]] == [0, 1]
    assert len(result["longest_normal_review_spans"]) == 2


def test_rejects_inconsistent_hourly_totals(tmp_path):
    with pytest.raises(ValueError, match="Inconsistent per-hour"):
        summarize_one(fixture(tmp_path / "sample", unbalanced=True))


def test_rejects_older_summary_without_hour_trace(tmp_path):
    with pytest.raises(ValueError, match="rerun updated evaluator"):
        summarize_one(fixture(tmp_path / "sample", missing_hourly=True))


def test_fails_if_episode_evidence_missing(tmp_path):
    path = fixture(tmp_path / "sample")
    (path / "continuous_shadow_normal_review_episodes.csv").unlink()
    with pytest.raises(ValueError, match="Missing extended continuous report"):
        summarize_one(path)
