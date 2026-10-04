import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.activity_evidence import (
    TemporalActivityGate,
    inset_box,
    roi_motion_fraction,
    worker_motion_fraction,
)


def test_roi_motion_fraction_static_scene_is_zero():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    score = roi_motion_fraction(frame, frame.copy(), (10, 10, 90, 90))
    assert score == pytest.approx(0.0)


def test_roi_motion_fraction_detects_local_change():
    first = np.zeros((100, 100, 3), dtype=np.uint8)
    second = first.copy()
    cv2.rectangle(second, (30, 30), (60, 60), (255, 255, 255), -1)

    score = roi_motion_fraction(
        first,
        second,
        (10, 10, 90, 90),
        pixel_delta_threshold=18,
    )

    assert score > 0.05


def test_worker_motion_is_not_diluted_by_large_work_cell():
    first = np.zeros((200, 200, 3), dtype=np.uint8)
    second = first.copy()

    # Simulate motion local to a worker-sized area.
    cv2.rectangle(second, (25, 25), (55, 85), (255, 255, 255), -1)

    large_zone_score = roi_motion_fraction(
        first,
        second,
        (0, 0, 200, 200),
        pixel_delta_threshold=18,
    )

    worker_score = worker_motion_fraction(
        first,
        second,
        [(20, 20, 60, 90)],
        pixel_delta_threshold=18,
        inset_ratio=0.0,
    )

    assert worker_score > large_zone_score
    assert worker_score > 0.20


def test_worker_motion_requires_worker_boxes():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert worker_motion_fraction(frame, frame.copy(), []) == 0.0


def test_inset_box_reduces_boundary_area():
    assert inset_box((0, 0, 100, 200), inset_ratio=0.1) == (10, 20, 90, 180)


def test_activity_gate_requires_worker_and_motion():
    gate = TemporalActivityGate(
        window_frames=5,
        motion_fraction_threshold=0.02,
        required_positive_ratio=0.6,
    )

    for _ in range(5):
        decision = gate.update(worker_present=False, motion_fraction=0.20)

    assert not decision.active

    gate.reset()

    for _ in range(5):
        decision = gate.update(worker_present=True, motion_fraction=0.0)

    assert not decision.active


def test_activity_gate_confirms_sustained_worker_motion():
    gate = TemporalActivityGate(
        window_frames=5,
        motion_fraction_threshold=0.02,
        required_positive_ratio=0.6,
    )

    sequence = [0.03, 0.04, 0.0, 0.05, 0.0]

    for value in sequence:
        decision = gate.update(worker_present=True, motion_fraction=value)

    assert decision.active
    assert decision.positive_ratio == pytest.approx(0.6)


def test_activity_gate_rejects_short_burst():
    gate = TemporalActivityGate(
        window_frames=5,
        motion_fraction_threshold=0.02,
        required_positive_ratio=0.6,
    )

    sequence = [0.10, 0.10, 0.0, 0.0, 0.0]

    for value in sequence:
        decision = gate.update(worker_present=True, motion_fraction=value)

    assert not decision.active
    assert decision.positive_ratio == pytest.approx(0.4)
