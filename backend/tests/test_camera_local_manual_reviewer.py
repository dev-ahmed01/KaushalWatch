"""Headless tests for local-only UHCTD case review, without decoding CCTV."""
from __future__ import annotations

import csv
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from review_uhctd_queue_local import (  # noqa: E402
    default_decision, describe, load_decisions, read_queue, write_decisions,
)


def fixture(tmp_path):
    queue = tmp_path / "targeted_camera_review_queue.csv"
    with queue.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=[
            "review_id", "day", "category", "start_seconds",
            "end_seconds", "review_start_seconds", "review_end_seconds",
        ])
        writer.writeheader()
        writer.writerow({
            "review_id": "day3-normal-23215", "day": "day3",
            "category": "carried", "start_seconds": "7738.0",
            "end_seconds": "8636.9", "review_start_seconds": "7728.0",
            "review_end_seconds": "8646.9",
        })
        writer.writerow({
            "review_id": "day4-normal-92081", "day": "day4",
            "category": "new_far_from_event", "start_seconds": "9208.0",
            "end_seconds": "9365.0", "review_start_seconds": "9198.0",
            "review_end_seconds": "9375.0",
        })
    videos = (tmp_path / "day3.avi", tmp_path / "day4.avi")
    for video in videos:
        video.write_bytes(b"placeholder; validate-only intentionally avoids decoding")
    return queue, videos


def test_local_review_roundtrip_preserves_original_queue(tmp_path):
    input_queue, _ = fixture(tmp_path)
    original = input_queue.read_bytes()
    cases = read_queue(input_queue)
    output = tmp_path / "completed-review.csv"
    decisions = {x["review_id"]: default_decision(x) for x in cases}
    first = decisions["day3-normal-23215"]
    first.update({
        "review_status": "REVIEWED",
        "scene_classification": "uncertain",
        "visual_evidence_usable": "unknown",
        "reference_still_valid": "unknown",
        "reviewer_notes": "No identifiable subjects recorded.",
    })
    write_decisions(output, cases, decisions)
    restored = load_decisions(output, cases)
    assert restored == decisions
    assert input_queue.read_bytes() == original
    assert describe(cases, restored)["reviewed"] == 1
    assert not (tmp_path / "completed-review.csv.tmp").exists()


def test_headless_cli_validates_existing_queue_and_local_paths(tmp_path):
    queue, videos = fixture(tmp_path)
    review_output = tmp_path / "review-results.csv"
    proc = subprocess.run([
        sys.executable,
        str(ROOT / "scripts" / "review_uhctd_queue_local.py"),
        "--queue", str(queue),
        "--day3-video", str(videos[0]),
        "--day4-video", str(videos[1]),
        "--reviews-out", str(review_output),
        "--validate-only",
    ], capture_output=True, text=True, check=True)
    value = json.loads(proc.stdout)
    assert value["cases"] == 2
    assert value["reviewed"] == 0
    assert value["by_day"] == {"day3": 1, "day4": 1}
    assert value["status"] == "TARGETED_LOCAL_REVIEW_NOT_INDEPENDENT_VALIDATION"
    assert not review_output.exists()


def test_rejects_invalid_intervals_and_duplicates(tmp_path):
    path, _ = fixture(tmp_path)
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace("7728.0", "9999.0")
    path.write_text(text)
    with pytest.raises(ValueError, match="Nonmonotonic"):
        read_queue(path)


def test_rejects_reviewed_status_without_classification(tmp_path):
    path, _ = fixture(tmp_path)
    cases = read_queue(path)
    decisions = {x["review_id"]: default_decision(x) for x in cases}
    decisions[cases[0]["review_id"]]["review_status"] = "REVIEWED"
    with pytest.raises(ValueError, match="Select a classification"):
        write_decisions(tmp_path / "output.csv", cases, decisions)


def test_prior_review_metadata_mismatch_fails_closed(tmp_path):
    path, _ = fixture(tmp_path)
    cases = read_queue(path)
    decisions = {x["review_id"]: default_decision(x) for x in cases}
    output = tmp_path / "out.csv"
    write_decisions(output, cases, decisions)
    content = output.read_text(encoding="utf-8-sig")
    output.write_text(content.replace("7738.0", "7000.0"))
    with pytest.raises(ValueError, match="metadata changed"):
        load_decisions(output, cases)


def test_same_queue_and_output_not_allowed(tmp_path):
    path, videos = fixture(tmp_path)
    proc = subprocess.run([
        sys.executable,
        str(ROOT / "scripts" / "review_uhctd_queue_local.py"),
        "--queue", str(path),
        "--day3-video", str(videos[0]),
        "--day4-video", str(videos[1]),
        "--reviews-out", str(path),
        "--validate-only",
    ], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "must not overwrite" in proc.stderr



def test_navigation_is_packed_before_preview_even_on_short_screens():
    """Keep the critical next/save controls above the potentially tall image."""
    from review_uhctd_queue_local import launch_gui

    source = inspect.getsource(launch_gui)
    assert source.index("footer.pack(") < source.index("image_label.pack(")
    assert 'text="Next →"' in source
    assert 'text="Save labels"' in source
    assert 'text="Save and close"' in source
    assert source.count("footer.pack(") == 1
