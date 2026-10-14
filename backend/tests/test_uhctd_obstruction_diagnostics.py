"""Targeted UHCTD diagnostics use labels only to select normal windows."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from diagnose_uhctd_obstruction import (  # noqa: E402
    annotation_runs,
    choose_normal_windows,
    diagnose,
)


def test_choose_normal_windows_never_covers_tampering():
    runs = [(0, 1, 149), (1, 150, 180), (0, 181, 400), (2, 401, 430),
            (0, 431, 750)]
    selected = choose_normal_windows(
        runs, total_frames=750, fps=10, n_windows=3,
        duration_seconds=5, margin_seconds=1
    )
    assert len(selected) == 3
    for window in selected:
        assert any(cls == 0 and low <= window["start_frame"]
                   and high >= window["end_frame"] for cls, low, high in runs)


def test_label_mismatch_fails_fast(tmp_path):
    labels = tmp_path / "annotations.csv"
    labels.write_text("1,0,0,0,0\n3,0,0,0,0\n")
    with pytest.raises(ValueError, match="Unexpected annotation"):
        annotation_runs(labels)


def test_diagnostic_does_not_export_frames_and_compares_paired_references(tmp_path):
    video = tmp_path / "synthetic.avi"
    annotations = tmp_path / "annotations.csv"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (120, 90)
    )
    assert writer.isOpened()
    with annotations.open("w", newline="") as handle:
        out = csv.writer(handle)
        try:
            for frame_no in range(1, 241):
                frame = np.full((90, 120, 3), 100, dtype=np.uint8)
                cv2.rectangle(frame, (20, 10), (60, 75), (245, 245, 245), 2)
                cv2.putText(frame, str(frame_no % 10), (5, 50),
                            cv2.FONT_HERSHEY_PLAIN, 1.2, (35, 35, 35), 2)
                if frame_no > 100:
                    frame = cv2.convertScaleAbs(frame, alpha=1, beta=60)
                writer.write(frame)
                out.writerow([frame_no, 0, 0, 0, 0])
        finally:
            writer.release()
    summary = diagnose(
        video, annotations, tmp_path / "result", windows=1,
        duration_seconds=3, margin_seconds=1, sample_seconds=0.2
    )
    assert summary["kind"].startswith("TARGETED_NORMAL_WINDOW")
    assert summary["total_sampled_frames_per_mode"] == 15
    assert (tmp_path / "result" / "obstruction_samples.csv").is_file()
    assert (tmp_path / "result" / "obstruction_windows.csv").is_file()
    assert (tmp_path / "result" / "obstruction_diagnostics_summary.json").is_file()
    assert sorted(p.suffix for p in (tmp_path / "result").iterdir()) == [
        ".csv", ".csv", ".json"
    ]
    assert summary["initial_reference"]["samples"] == 15
    assert summary["local_reference"]["samples"] == 15


def test_insufficient_normal_windows_is_explicit_failure():
    with pytest.raises(ValueError, match="Only 1"):
        choose_normal_windows(
            [(0, 1, 100)], total_frames=100, fps=10,
            n_windows=2, duration_seconds=2, margin_seconds=1
        )
