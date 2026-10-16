"""Synthetic-only tests of temporal adjacency and carried review episodes."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from triage_uhctd_normal_recovery import classify  # noqa: E402


def example(folder: Path, *, samples=7, qualified=False):
    folder.mkdir()
    (folder / "continuous_shadow_summary.json").write_text(json.dumps({
        "status": "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT",
        "qualified": qualified,
        "production_integration": False,
        "fps": 10.0,
        "effective_sample_seconds": 1.0,
        "methods": {"fusion": {"normal_review_samples": samples}},
    }))
    with (folder / "continuous_shadow_events.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "start_frame", "end_frame", "method"])
        for method in ("spatial", "global", "fusion"):
            w.writerow(["moved", 10, 50, method])
            w.writerow(["defocused", 500, 540, method])
    with (folder / "continuous_shadow_normal_review_episodes.csv").open(
        "w", newline=""
    ) as f:
        w = csv.writer(f)
        w.writerow([
            "start_frame", "end_frame", "samples", "spatial_cue_samples",
            "global_fallback_samples", "already_alerted_before_normal_span",
        ])
        # Same event boundary, carried over from the movement interval.
        w.writerow([51, 80, 3, 3, 0, True])
        # New warning long after earlier movement, before second event.
        w.writerow([300, 340, 2, 1, 1, False])
        # New warning after second event, spatial+global.
        w.writerow([541, 570, 2, 1, 1, False])
    return folder


def test_classifies_carryover_and_proximity_without_claiming_causation(tmp_path):
    out = classify(example(tmp_path / "day3"), nearby_seconds=60)
    assert out["normal_review_samples"] == 7
    assert out["review_spans"] == 3
    assert out["spans_already_alerted_at_start"] == 1
    assert out["normal_review_samples_in_carried_spans"] == 3
    assert out["spans_started_within_window_after_event"] == 3
    assert out["normal_review_samples_in_nearby_spans"] == 7
    assert out["qualified"] is False
    assert "does not prove" in " ".join(out["notes"])
    assert out["longest_normal_review_spans"][0]["nearest_prior_annotated_event_class"] == "moved"


def test_short_adjacency_window_avoids_attributing_later_normal_warning(tmp_path):
    out = classify(example(tmp_path / "day3"), nearby_seconds=3)
    assert out["spans_started_within_window_after_event"] == 2
    assert out["normal_review_samples_in_nearby_spans"] == 5


def test_source_totals_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="fail to reconcile"):
        classify(example(tmp_path / "day3", samples=10))


def test_qualified_report_rejected(tmp_path):
    with pytest.raises(ValueError, match="unqualified"):
        classify(example(tmp_path / "day3", qualified=True))


def test_missing_episode_file_rejected(tmp_path):
    folder = example(tmp_path / "day3")
    (folder / "continuous_shadow_normal_review_episodes.csv").unlink()
    with pytest.raises(ValueError, match="Missing required numerical"):
        classify(folder)
