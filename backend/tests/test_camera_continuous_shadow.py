"""Synthetic-only tests for continuous (non-resetting) camera shadow diagnostics."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_uhctd_continuous_shadow import evaluate  # noqa: E402


def make_source(tmp_path, segments=((0, 60), (3, 105), (0, 60)),
                *, truncate_annotations=False, bad_start=False):
    video = tmp_path / "synthetic.avi"
    labels = tmp_path / "labels.csv"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 3, (240, 180)
    )
    assert writer.isOpened()
    rng = np.random.default_rng(20261017)
    normal = rng.integers(65, 185, (180, 240, 3), dtype=np.uint8)
    moved = np.roll(normal, 50, axis=1)
    frame_no = 0
    with labels.open("w", encoding="utf-8", newline="") as output:
        csv_writer = csv.writer(output)
        try:
            for kind, length in segments:
                for _ in range(length):
                    frame_no += 1
                    writer.write(moved if kind else normal)
                    if not truncate_annotations or frame_no != sum(n for _, n in segments):
                        csv_writer.writerow([
                            frame_no, 3 if bad_start and frame_no == 1 else kind,
                            "0.5", 0, 0,
                        ])
        finally:
            writer.release()
    return video, labels


def test_continuous_full_run_creates_movement_review_without_promotion(tmp_path):
    video, labels = make_source(tmp_path)
    result = evaluate(video, labels, sample_seconds=1.0)
    assert result["status"] == "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"
    assert not result["qualified"]
    assert not result["production_integration"]
    assert result["total_source_frames"] == 225
    assert result["frame_labels"]["moved"] == 105
    assert result["methods"]["fusion"]["per_class"]["moved"]["events"] == 1
    assert result["methods"]["fusion"]["per_class"]["moved"]["fresh_alert_events"] == 1
    assert len(result["events"]) == 3
    assert len(result["normal_review_hours"]) == 1
    assert result["normal_review_hours"][0]["normal_samples"] > 0
    assert sum(row["fusion_review_samples"] for row in result["normal_review_hours"]) == result["methods"]["fusion"]["normal_review_samples"]
    assert sum(row["samples"] for row in result["normal_review_episodes"]) == result["methods"]["fusion"]["normal_review_samples"]
    assert "SHA" not in result["source_video_sha256"]
    assert len(result["source_video_sha256"]) == 64
    assert all(row["method"] != "tamper" for row in result["events"])


def test_normal_low_texture_is_unknown_not_stable_or_detected(tmp_path):
    video = tmp_path / "flat.avi"
    labels = tmp_path / "flat.csv"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 3, (80, 80)
    )
    assert writer.isOpened()
    with labels.open("w", newline="", encoding="utf-8") as output:
        csv_writer = csv.writer(output)
        try:
            for index in range(1, 91):
                writer.write(np.full((80, 80, 3), 65, dtype=np.uint8))
                csv_writer.writerow([index, 0, 0, 0, 0])
        finally:
            writer.release()
    result = evaluate(video, labels, sample_seconds=1.0)
    assert result["low_texture_unknown_by_class"]["normal"] > 0
    assert result["methods"]["fusion"]["normal_review_samples"] == 0
    assert result["normal_review_episodes"] == []
    assert result["methods"]["fusion"]["per_class"]["moved"]["events"] == 0
    assert result["methods"]["fusion"]["new_normal_review_episodes_per_normal_hour"] == 0


def test_short_preview_is_explicitly_not_complete(tmp_path):
    video, labels = make_source(tmp_path)
    result = evaluate(video, labels, sample_seconds=1.0, preview_seconds=12)
    assert result["status"].startswith("PREVIEW_ONLY_")
    assert result["evaluated_frames"] == 36
    assert not result["qualified"]


def test_malformed_annotations_fail_closed(tmp_path):
    video, labels = make_source(tmp_path, truncate_annotations=True)
    with pytest.raises(ValueError, match="Annotation missing"):
        evaluate(video, labels)


def test_reference_requires_initial_annotated_normal(tmp_path):
    video, labels = make_source(tmp_path, bad_start=True)
    with pytest.raises(ValueError, match="Initial 10-second reference"):
        evaluate(video, labels, preview_seconds=15)


def test_interval_must_be_positive(tmp_path):
    video, labels = make_source(tmp_path)
    with pytest.raises(ValueError, match="Sample interval"):
        evaluate(video, labels, sample_seconds=0.0)


def test_cli_writes_numeric_outputs_without_video_or_images(tmp_path):
    video, labels = make_source(tmp_path)
    out = tmp_path / "numbers-only"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "evaluate_uhctd_continuous_shadow.py"),
         "--video", str(video), "--annotations", str(labels),
         "--out", str(out), "--sample-seconds", "1"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(completed.stdout)
    assert parsed["qualified"] is False
    assert sorted(p.name for p in out.iterdir()) == [
        "continuous_shadow_events.csv",
        "continuous_shadow_normal_review_episodes.csv",
        "continuous_shadow_summary.json"
    ]
    data = json.loads((out / "continuous_shadow_summary.json").read_text())
    assert data["qualified"] is False
    with (out / "continuous_shadow_events.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert set(row["method"] for row in rows) == {"spatial", "global", "fusion"}
    with (out / "continuous_shadow_normal_review_episodes.csv").open(newline="") as stream:
        episodes = list(csv.DictReader(stream))
    assert len(episodes) == data["normal_review_episodes_count"]
