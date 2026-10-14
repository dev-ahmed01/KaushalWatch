"""Offline shadow result triage; only synthetic CSV/images are used."""
import csv
import json
import sys

import cv2
import numpy as np
import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from triage_uhctd_persistent_results import (
    analyse, false_review_sheet, load_rows, triage,
)


def _inputs(tmp_path):
    samples = tmp_path / "samples.csv"
    summary = tmp_path / "summary.json"
    rows = []
    metas = []
    for name, kind, frame_start in (
        ("moved_1", 3, 100), ("normal_control_1", 0, 500),
        ("normal_control_2", 0, 900),
    ):
        onset = frame_start+60 if kind else None
        active = []
        for index in range(150):
            frame = frame_start+index
            # One 20-second normal foreground change, against >30-sec move.
            flagged = kind == 3 and index >= 60 or (
                kind == 0 and name.endswith("1") and 40 <= index < 100
            )
            if flagged:
                seconds = sum(
                    (kind == 3 and i >= 60 or
                     kind == 0 and name.endswith("1") and 40 <= i < 100)
                    for i in range(max(0,index-100), index+1)
                ) / 3
            else:
                seconds = 0.0
            record = {
                "span": name, "frame": frame,
                "time_seconds": (frame-1)/3,
                "post_onset": str(kind == 3 and frame >= onset),
                "scene_correlation": .45 if flagged else .95,
                "low_similarity": str(flagged),
                "changed_seconds": seconds,
                "persistent_review": str(seconds >= 12),
            }
            rows.append(record)
            active.append(record)
        metas.append({
            "span": name, "kind": kind, "onset": onset,
            "review_samples": sum(z["persistent_review"] == "True" for z in active),
        })
    with samples.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary.write_text(json.dumps({
        "evaluation_status": "PHASE10_SHADOW_DEVELOPMENT_NOT_HELD_OUT",
        "fps": 3.0, "effective_sample_seconds": 1/3,
        "model_commit": "synthetic", "rows": metas,
    }))
    return summary, samples


def test_offline_counterfactual_is_labelled_not_validation(tmp_path):
    summary_path, samples_path = _inputs(tmp_path)
    result = triage(summary_path, samples_path, tmp_path / "result")
    assert result["status"].startswith("POST_HOC")
    assert result["normal_review_samples"] > 0
    row_12 = next(x for x in result["threshold_sensitivity"]
                  if x["confirmation_seconds"] == 12)
    row_22 = next(x for x in result["threshold_sensitivity"]
                  if x["confirmation_seconds"] == 22)
    assert row_12["normal_controls_with_false_review"] == 1
    assert row_22["normal_controls_with_false_review"] == 0
    assert row_22["moved_events_with_new_review"] == 1
    assert (tmp_path / "result" / "shadow_false_review_triage.json").is_file()


def test_rejects_summary_samples_mismatch(tmp_path):
    summary_path, samples_path = _inputs(tmp_path)
    summary = json.loads(summary_path.read_text())
    summary["rows"].pop()
    with pytest.raises(ValueError, match="different span sets"):
        analyse(summary, load_rows(samples_path))


def test_visual_contact_sheet_is_local_and_has_six_key_frames(tmp_path):
    video = tmp_path / "v.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 3,
                             (120, 90))
    assert writer.isOpened()
    try:
        for i in range(150):
            frame = np.full((90, 120, 3), 120+i//10, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()
    _, csvfile = _inputs(tmp_path)
    samples = load_rows(csvfile)["normal_control_1"]
    # Test frame numbers are 500+, while the synthetic AVI is 150 frames:
    # transform sample IDs to match source frames.
    for i, item in enumerate(samples):
        item["frame"] = i+1
    cap = cv2.VideoCapture(str(video))
    try:
        sheet, picks = false_review_sheet(cap, samples, width=120,
                                          cell_height=90)
        assert sheet.shape == (180, 360, 3)
        assert len(picks) == 6
        assert min(picks) >= 1
        assert max(picks) <= 150
    finally:
        cap.release()
