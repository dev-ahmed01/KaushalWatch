"""Movement-gate forensic tooling tests, using only synthetic image data."""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from diagnose_uhctd_movement import (  # noqa: E402
    gate_metrics, inspect_span, registration_metrics
)


def _textured_scene():
    rng = np.random.default_rng(14)
    gray = rng.integers(70, 180, size=(180, 240), dtype=np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def test_global_translation_produces_geometric_evidence():
    original = _textured_scene()
    matrix = np.float32([[1, 0, 21], [0, 1, 8]])
    moved = cv2.warpAffine(
        original, matrix, (240, 180), borderMode=cv2.BORDER_CONSTANT,
        borderValue=(70, 70, 70),
    )
    evidence = registration_metrics(original, moved)
    assert evidence["geometry_pass"]
    assert evidence["offset_pixels"] > 10
    assert evidence["response"] >= 0.25
    gates = gate_metrics(original, moved, moved)
    assert gates["ungated_geometric_shift"]
    assert gates["gate_neighbor_corr"]


def test_global_exposure_without_displacement_not_geometric_motion():
    original = _textured_scene()
    lighting = cv2.convertScaleAbs(original, alpha=1, beta=18)
    evidence = registration_metrics(original, lighting)
    assert evidence["offset_pixels"] < 3.5
    assert not evidence["geometry_pass"]


def test_one_synthetic_span_produces_frame_level_gate_diagnostics(tmp_path):
    video = tmp_path / "synthetic.avi"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (240, 180)
    )
    assert writer.isOpened()
    baseline = _textured_scene()
    shifted = np.roll(baseline, 24, axis=1)
    try:
        for i in range(30):
            writer.write(baseline if i < 10 else shifted)
    finally:
        writer.release()
    cap = cv2.VideoCapture(str(video))
    assert cap.isOpened()
    try:
        success, reference = cap.read()
        assert success
        columns = [
            "span", "class", "extent", "frame", "time_sec", "after_onset",
            "tamper_alert", "quality_unusable", "reasons",
        ]
        metrics = list(gate_metrics(reference, reference, None))
        columns.extend(
            f"{name}_{key}" for name in ("original", "local") for key in metrics
        )
        path = tmp_path / "diagnostic.csv"
        with path.open("w", newline="") as stream:
            csv_writer = csv.DictWriter(stream, fieldnames=columns)
            csv_writer.writeheader()
            result = inspect_span(
                cap, reference, {
                    "name": "synthetic_moved", "kind": 3,
                    "start": 1, "onset": 11, "end": 30,
                    "extent": "1", "rate": "1",
                }, 10.0, 1, csv_writer
            )
        assert result["samples"] == 30
        assert result["positive_samples"] == 20
        assert result["original_geometry_pass"] > 0
        assert result["original_landmark_samples"] > 0
        with path.open(newline="") as source:
            rows = list(csv.DictReader(source))
        assert "original_landmark_confidence" in rows[0]
        assert any(row["original_landmark_match_status"] for row in rows)
        assert path.stat().st_size > 200
    finally:
        cap.release()
