"""Phase 3P complete bounded replay: synthetic AVI + hashed Phase3M reports.

This does not read user surveillance data or certify source provenance.
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from run_phase3m_dual_day_research import run_pair  # noqa: E402
from run_phase3p_bounded_causal_quality import run_day  # noqa: E402


def make_synthetic_day(tmp_path: Path, name: str, fps: int, seed: int):
    root = tmp_path / name
    root.mkdir()
    video = root / "video.avi"
    annotations = root / "annotations.csv"
    rng = np.random.default_rng(seed)
    baseline = rng.integers(45, 165, (96, 128, 3), dtype=np.uint8)
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), fps, (128, 96),
    )
    assert writer.isOpened()
    with annotations.open("w", newline="", encoding="utf-8") as stream:
        out = csv.writer(stream)
        for frame_index in range(fps * 111):
            kind = (2 if fps*94 <= frame_index < fps*99 else
                    3 if fps*103 <= frame_index < fps*109 else 0)
            frame = baseline.copy()
            if kind == 2:
                frame = cv2.GaussianBlur(frame, (15, 15), 4)
            elif kind == 3:
                matrix = np.float32([[1, 0, 5], [0, 1, 4]])
                frame = cv2.warpAffine(
                    frame, matrix, (128, 96), borderMode=cv2.BORDER_REFLECT,
                )
            writer.write(frame)
            out.writerow([frame_index+1, kind, 0, 0, 0])
    writer.release()
    return video, annotations


def test_bounded_true_avi_replay_preserves_reference_and_produces_numeric_only(tmp_path):
    day3 = make_synthetic_day(tmp_path, "day3", 3, 11)
    day4 = make_synthetic_day(tmp_path, "day4", 5, 29)
    old = tmp_path / "prior"
    run_pair(
        day3_video=day3[0], day3_annotations=day3[1],
        day4_video=day4[0], day4_annotations=day4[1],
        run_dir=old, sample_seconds=1, preview_seconds=12, run_full=True,
    )
    for name, pair in (("day3", day3), ("day4", day4)):
        evidence = run_day(
            video=pair[0], annotations=pair[1],
            report=old / "full" / (name + ".json"),
            event_count=1, normal_controls=1, sample_seconds=2.0,
        )
        assert evidence["production_qualified"] is False
        assert evidence["reference_is_approved"] is False
        assert evidence["video_or_images_exported"] is False
        assert evidence["scene_raw_review_status_measured"] is False
        assert evidence["spatial_evidence_status_measured"] is False
        assert evidence["summary"]["defocused"]["selected_windows"] == 1
        assert evidence["summary"]["moved"]["selected_windows"] == 1
        assert all(w["frames_or_media_exported"] is False
                   for w in evidence["windows"])
        assert any(
            sample["comparison_state"] == "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION"
            for window in evidence["windows"]
            for sample in window["samples"]
        )
        assert all(
            "SPATIAL_EVIDENCE_NOT_MEASURED" in sample["confounds"]
            for window in evidence["windows"]
            for sample in window["samples"]
            if sample["paired_sharpness_ratio"] is not None
        )
