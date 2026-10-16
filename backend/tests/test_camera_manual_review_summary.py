"""Synthetic-only tests for safe aggregate analysis of manual camera reviews."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from review_uhctd_queue_local import (  # noqa: E402
    read_queue, default_decision, write_decisions,
)
from summarize_uhctd_manual_reviews import aggregate  # noqa: E402


def inputs(tmp_path, *, incomplete=False):
    queue = tmp_path / "targeted_camera_review_queue.csv"
    with queue.open("w", newline="", encoding="utf-8-sig") as output:
        fields = [
            "review_id", "day", "category", "start_seconds", "end_seconds",
            "review_start_seconds", "review_end_seconds",
        ]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for name, day, category, start in (
            ("day3-normal-100", "day3", "carried", 30),
            ("day4-normal-200", "day4", "new_far_from_event", 60),
            ("day4-normal-300", "day4", "new_near_event", 90),
        ):
            writer.writerow({
                "review_id": name, "day": day, "category": category,
                "start_seconds": str(start), "end_seconds": str(start+10),
                "review_start_seconds": str(start-5),
                "review_end_seconds": str(start+15),
            })
    cases = read_queue(queue)
    decisions = {r["review_id"]: default_decision(r) for r in cases}
    for decision in decisions.values():
        decision["review_status"] = "REVIEWED"
    decisions["day3-normal-100"].update({
        "scene_classification": "camera_displacement",
        "visual_evidence_usable": "no",
        "reference_still_valid": "no",
        "reviewer_notes": "SECRET_PII_SENTINEL_NOT_FOR_OUTPUT",
    })
    decisions["day4-normal-200"].update({
        "scene_classification": "unchanged_scene",
        "visual_evidence_usable": "yes",
        "reference_still_valid": "yes",
    })
    decisions["day4-normal-300"].update({
        "scene_classification": "visibility_degraded",
        "visual_evidence_usable": "yes",
        "reference_still_valid": "unknown",
    })
    if incomplete:
        decisions["day4-normal-300"]["review_status"] = "NEEDS_SECOND_REVIEW"
    csv_path = tmp_path / "local_review_decisions.csv"
    write_decisions(csv_path, cases, decisions)
    return queue, csv_path


def test_aggregate_is_grounded_in_labels_without_leaking_notes_or_case_ids(tmp_path):
    queue, reviews = inputs(tmp_path)
    report = aggregate(queue, reviews, require_complete=True)
    assert report["all_cases_marked_reviewed"] is True
    assert report["reviewed"] == 3
    assert report["by_day"]["day4"]["reviewed"] == 2
    assert report["review_hypotheses_only"]["camera_displacement_with_reference_invalid"] == 1
    assert report["review_hypotheses_only"]["normal_looking_usable_with_reference_valid"] == 1
    assert report["review_hypotheses_only"]["visibility_degraded_but_evidence_usable_check"] == 1
    assert report["production_qualified"] is False
    assert len(report["decisions_sha256"]) == 64
    payload = json.dumps(report)
    assert "SECRET_PII_SENTINEL" not in payload
    assert "day3-normal-100" not in payload
    assert "day4-normal-300" not in payload


def test_unresolved_second_review_is_counted_but_optional(tmp_path):
    queue, reviews = inputs(tmp_path, incomplete=True)
    result = aggregate(queue, reviews)
    assert not result["all_cases_marked_reviewed"]
    assert result["reviewed"] == 2
    assert result["needs_second_review"] == 1
    with pytest.raises(ValueError, match="Not all cases"):
        aggregate(queue, reviews, require_complete=True)


def test_missing_review_csv_fails_instead_of_claiming_all_unreviewed(tmp_path):
    queue, reviews = inputs(tmp_path)
    reviews.unlink()
    with pytest.raises(ValueError, match="missing"):
        aggregate(queue, reviews)


def test_csv_case_set_must_match_exact_queue(tmp_path):
    queue, reviews = inputs(tmp_path)
    text = reviews.read_text(encoding="utf-8-sig")
    reviews.write_text(text.replace("day3-normal-100", "day3-normal-999"))
    with pytest.raises(ValueError, match="exactly match"):
        aggregate(queue, reviews)


def test_cli_writes_only_aggregate_json_without_notes(tmp_path):
    queue, reviews = inputs(tmp_path)
    target = tmp_path / "private-aggregate.json"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "summarize_uhctd_manual_reviews.py"),
        "--queue", str(queue), "--reviews", str(reviews),
        "--out", str(target), "--require-complete",
    ], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    stored = json.loads(target.read_text(encoding="utf-8"))
    assert report == stored
    assert report["cases_in_queue"] == 3
    assert report["review_status"]["REVIEWED"] == 3
    assert "SECRET_PII_SENTINEL" not in result.stdout
