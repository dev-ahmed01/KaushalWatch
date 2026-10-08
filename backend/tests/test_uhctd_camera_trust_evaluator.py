"""Test the held-out evaluator on fully synthetic annotations and footage."""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_uhctd_camera_trust import score_recording


def test_uhctd_evaluator_aligns_frames_and_distinguishes_preview(tmp_path):
    video = tmp_path / "test.avi"
    labels = tmp_path / "labels.csv"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (80, 60)
    )
    assert writer.isOpened()
    base = np.full((60, 80, 3), 100, dtype=np.uint8)
    cv2.rectangle(base, (10, 10), (50, 40), (240, 240, 240), 2)
    try:
        for i in range(40):
            writer.write(base if i < 20 else np.zeros_like(base))
    finally:
        writer.release()
    with labels.open("w", newline="") as stream:
        writer_csv = csv.writer(stream)
        for i in range(40):
            writer_csv.writerow([i+1, 0 if i < 20 else 1, 0, 0, 0])
    full, events = score_recording(
        video, labels, sample_seconds=0.2, verbose=False
    )
    assert full["evaluation_status"] == "COMPLETE_UNTOUCHED_RECORDING"
    assert full["sampled_confusion"]["tp"] + full["sampled_confusion"]["fn"] == 10
    assert len(events) == 1
    assert events[0]["class"] == "covered"
    preview, _ = score_recording(
        video, labels, sample_seconds=0.2, preview_seconds=1.0,
        verbose=False,
    )
    assert preview["evaluation_status"] == "PREVIEW_ONLY_NOT_HELD_OUT_VALIDATION"
    assert preview["evaluated_frames"] == 10
