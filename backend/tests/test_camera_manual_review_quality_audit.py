"""Synthetic reviews only: tests for post-review audit and CLI privacy."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_uhctd_manual_review_quality import inspect_reviews  # noqa: E402


def write_reviews(directory: Path):
    path = directory / "local_review_decisions.csv"
    headers = [
        "review_id", "day", "category", "start_seconds", "end_seconds",
        "review_status", "scene_classification", "visual_evidence_usable",
        "reference_still_valid", "reviewer_notes",
    ]
    records = [
        ("d3-1", "day3", "carried", "0", "20", "REVIEWED",
         "visibility_degraded", "yes", "yes", "NEVER_ECHO_PRIVATE_NOTE"),
        ("d3-2", "day3", "new_far_from_event", "100", "130", "REVIEWED",
         "visibility_degraded", "no", "yes", ""),
        ("d4-1", "day4", "new_near_event", "200", "220", "REVIEWED",
         "unchanged_scene", "no", "yes", ""),
        ("d4-2", "day4", "new_far_from_event", "300", "330", "REVIEWED",
         "unchanged_scene", "no", "yes", ""),
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(records)
    return path


def test_audit_reports_clarifications_without_overriding_original_labels(tmp_path):
    path = write_reviews(tmp_path)
    before = path.read_bytes()
    result, selected = inspect_reviews(path, per_pattern=2)
    assert result["production_qualified"] is False
    assert result["cases"] == 4
    assert result["reviewed"] == 4
    assert result["patterns_needing_clarification"] == {
        "stable_view_unusable_needs_reason": 2,
        "degraded_but_usable_needs_scope": 1,
        "degraded_unusable_reference_check": 1,
    }
    assert result["reference_marked_valid_yes"] == 4
    assert result["reference_independently_verified"] == "NOT_ASSESSED"
    assert len(selected) == 4
    assert path.read_bytes() == before
    assert "NEVER_ECHO" not in json.dumps(result)
    assert "NEVER_ECHO" not in json.dumps(selected)


def test_cli_output_contains_only_aggregate_and_local_optional_queue(tmp_path):
    path = write_reviews(tmp_path)
    out = tmp_path / "audit"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_uhctd_manual_review_quality.py"),
         "--reviews", str(path), "--out", str(out), "--per-pattern", "1"],
        capture_output=True, text=True, check=True,
    )
    assert "NEVER_ECHO_PRIVATE_NOTE" not in proc.stdout
    results = json.loads((out / "review_quality_audit.json").read_text())
    assert results["selected_clarification_cases"] == 3
    with (out / "optional_clarification_queue.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert all(row["independent_review_status"] == "UNREVIEWED" for row in rows)
    assert not (tmp_path / "local_review_decisions.csv").stat().st_size == 0


def test_duplicate_case_ids_fail_closed(tmp_path):
    path = write_reviews(tmp_path)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    lines.append(lines[1])
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="repeated case ID"):
        inspect_reviews(path)


def test_invalid_labels_fail_closed(tmp_path):
    path = write_reviews(tmp_path)
    content = path.read_text(encoding="utf-8-sig")
    path.write_text(content.replace("visibility_degraded", "magic_detector_label", 1))
    with pytest.raises(ValueError, match="Invalid categorical"):
        inspect_reviews(path)


def test_limited_selection_is_explicitly_not_population_prevalence(tmp_path):
    path = write_reviews(tmp_path)
    result, selected = inspect_reviews(path, per_pattern=1)
    assert len(selected) == 3
    assert any("not unbiased" in s for s in result["limitations"])
    with pytest.raises(ValueError, match="per_pattern"):
        inspect_reviews(path, per_pattern=0)
