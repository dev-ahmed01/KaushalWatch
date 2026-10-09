"""Synthetic-only review contact sheet tests (no surveillance footage)."""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from export_uhctd_movement_review import (  # noqa: E402
    contact_sheet, read_frame, review_frame_numbers
)


def test_review_frames_include_clean_context_and_post_onset():
    span = {"name": "moved", "start": 101, "onset": 161, "end": 520}
    picks = review_frame_numbers(span, 3)
    assert len(picks) == 6
    assert picks[0] < picks[1] < span["onset"]
    assert picks[2] > span["onset"]
    assert picks[-1] <= span["end"]


def test_normal_review_frames_in_bounds():
    span = {"name": "normal", "start": 201, "onset": None, "end": 470}
    picks = review_frame_numbers(span, 3)
    assert len(picks) == 6
    assert picks[0] == 201
    assert picks[-1] <= 470


def test_contact_sheet_reads_only_selected_frames(tmp_path):
    video = tmp_path / "toy.avi"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (80, 60)
    )
    assert writer.isOpened()
    try:
        for i in range(90):
            frame = np.full((60, 80, 3), i, dtype=np.uint8)
            cv2.rectangle(frame, (5, 5), (45, 48), (i + 20, 130, 155), 2)
            writer.write(frame)
    finally:
        writer.release()
    cap = cv2.VideoCapture(str(video))
    assert cap.isOpened()
    try:
        span = {"name": "moved", "start": 1, "onset": 40, "end": 90}
        sheet, frames = contact_sheet(cap, span, 10, 120, 100)
        assert sheet.shape == (200, 360, 3)
        assert len(frames) == 6
        assert frames[0]["frame"] >= 1
        assert frames[-1]["frame"] <= 90
        assert read_frame(cap, 5).shape == (60, 80, 3)
    finally:
        cap.release()
