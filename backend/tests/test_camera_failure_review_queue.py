"""Synthetic numeric-only tests for local Camera Trust review queue selection."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_uhctd_failure_review_queue import create_queue  # noqa: E402


def fixture(path: Path, *, unqualified=False, wrong_count=False):
    path.mkdir()
    summary = {
        "status": "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT",
        "qualified": unqualified,
        "production_integration": False,
        "fps": 3.0,
        "effective_sample_seconds": 1.0,
        "methods": {
            "fusion": {"normal_review_samples": 82 if wrong_count else 81}
        },
        "normal_review_hours": [
            {
                "hour_from_recording_start": 0,
                "fusion_review_samples": 72,
                "new_fusion_review_episodes": 4,
            },
            {
                "hour_from_recording_start": 1,
                "fusion_review_samples": 9,
                "new_fusion_review_episodes": 7,
            },
        ],
    }
    (path / "continuous_shadow_summary.json").write_text(json.dumps(summary))
    with (path / "continuous_shadow_events.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["class", "start_frame", "end_frame", "method"])
        for method in ("spatial", "global", "fusion"):
            writer.writerow(["covered", 30, 60, method])
            writer.writerow(["moved", 300, 330, method])

    episodes = [
        (61, 120, 20, 20, 0, True),
        (150, 200, 12, 10, 2, False),
        (500, 600, 30, 30, 0, False),
        (700, 900, 10, 0, 10, False),
        (11000, 11015, 5, 5, 0, False),
        (11200, 11211, 4, 2, 2, False),
    ]
    with (path / "continuous_shadow_normal_review_episodes.csv").open(
        "w", newline=""
    ) as out:
        writer = csv.writer(out)
        writer.writerow([
            "start_frame", "end_frame", "samples", "spatial_cue_samples",
            "global_fallback_samples", "already_alerted_before_normal_span",
        ])
        writer.writerows(episodes)
    return path


def test_queue_selects_distinct_carryover_near_and_far_cases(tmp_path):
    a = fixture(tmp_path / "day3")
    b = fixture(tmp_path / "day4")
    rows, metadata = create_queue(a, b, per_category=1, churn_hours=1)
    assert metadata["selected_cases"] == len(rows)
    assert metadata["qualified"] is False
    assert metadata["day_summaries"]["day3"]["total_normal_review_samples"] == 81
    assert set(item["category"] for item in rows) == {
        "carried", "new_near_event", "new_far_from_event"
    }
    assert len({row["review_id"] for row in rows}) == len(rows)
    assert any(row["selection"] == "high_churn_hour" for row in rows)
    assert all(row["review_status"] == "UNREVIEWED" for row in rows)
    assert all(row["review_start_seconds"] >= 0 for row in rows)
    assert all(row["review_end_seconds"] > row["review_start_seconds"] for row in rows)


def test_no_churn_extra_when_disabled(tmp_path):
    a = fixture(tmp_path / "day3")
    b = fixture(tmp_path / "day4")
    rows, _ = create_queue(a, b, per_category=1, churn_hours=0)
    assert len(rows) == 6


def test_rejects_nonqualified_data_masquerading_as_qualified(tmp_path):
    a = fixture(tmp_path / "day3", unqualified=True)
    b = fixture(tmp_path / "day4")
    with pytest.raises(ValueError, match="nonqualified"):
        create_queue(a, b)


def test_reports_fail_when_episode_samples_do_not_reconcile(tmp_path):
    a = fixture(tmp_path / "day3", wrong_count=True)
    b = fixture(tmp_path / "day4")
    with pytest.raises(ValueError, match="do not reconcile"):
        create_queue(a, b)


def test_requires_numeric_episodes(tmp_path):
    a = fixture(tmp_path / "day3")
    b = fixture(tmp_path / "day4")
    (a / "continuous_shadow_normal_review_episodes.csv").unlink()
    with pytest.raises(ValueError, match="Missing numerical report"):
        create_queue(a, b)


def test_invalid_selection_counts_fail(tmp_path):
    a = fixture(tmp_path / "day3")
    b = fixture(tmp_path / "day4")
    with pytest.raises(ValueError, match="Selection counts"):
        create_queue(a, b, per_category=0)
