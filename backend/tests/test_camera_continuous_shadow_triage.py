"""Synthetic numerical fixtures for offline continuous shadow failure triage."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from triage_uhctd_continuous_shadow import summarize  # noqa: E402


def make_report(root: Path, *, status="COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"):
    root.mkdir()
    result = {
        "status": status,
        "qualified": False,
        "production_integration": False,
        "reference_basis": "first_10_seconds_dataset_annotated_normal_not_officer_approved",
        "evaluated_frames": 120,
        "normal_annotated_hours": 0.01,
        "low_texture_unknown_by_class": {"normal": 5},
        "methods": {},
    }
    for name in ("spatial", "global", "fusion"):
        result["methods"][name] = {
            "normal_review_fraction": 0.1,
            "normal_review_samples": 5,
            "normal_samples": 50,
            "new_normal_review_episodes_per_normal_hour": 100.0,
            "new_normal_review_episodes": 1,
            "per_class": {
                kind: {
                    "events": 1 if kind == "moved" else 0,
                    "fresh_alert_events": 0,
                    "events_preexisting_alert": 0,
                }
                for kind in ("covered", "defocused", "moved")
            },
        }
    summary = root / "continuous_shadow_summary.json"
    summary.write_text(json.dumps(result))
    with (root / "continuous_shadow_events.csv").open("w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["class", "start_frame", "end_frame", "method",
                    "preexisting_at_onset", "fresh_review", "fresh_delay_seconds"])
        for method in ("spatial", "global", "fusion"):
            w.writerow(["moved", 61, 90, method, False, False, ""])
    return summary


def test_triage_preserves_original_metrics_and_missed_events(tmp_path):
    a = make_report(tmp_path / "day3")
    b = make_report(tmp_path / "day4")
    report = summarize(a, b)
    assert report["production_qualified"] is False
    assert report["datasets"]["day3"]["by_method"]["fusion"]["normal_review_fraction"] == 0.1
    missed = report["datasets"]["day4"]["missed_or_preexisting_events"]["fusion"]
    assert len(missed) == 1
    assert missed[0]["start_frame"] == 61
    assert missed[0]["fresh_review"] is False
    assert "not be inferred" in " ".join(report["datasets"]["day3"]["limitations"])


def test_preview_summary_is_not_full_day_evidence(tmp_path):
    preview = make_report(tmp_path / "day3", status="PREVIEW_ONLY_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT")
    full = make_report(tmp_path / "day4")
    with pytest.raises(ValueError, match="Complete continuous"):
        summarize(preview, full)


def test_missing_event_csv_fails_closed(tmp_path):
    a = make_report(tmp_path / "day3")
    b = make_report(tmp_path / "day4")
    (b.parent / "continuous_shadow_events.csv").unlink()
    with pytest.raises(ValueError, match="Missing event CSV"):
        summarize(a, b)
