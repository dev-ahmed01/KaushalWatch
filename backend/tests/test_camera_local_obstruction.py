"""Synthetic tests for the experimental localized-obstruction cue."""
import cv2
import numpy as np

from app.services.camera_local_obstruction import localized_occlusion_candidate
from app.services.camera_trust import CameraTrustState, assess_camera


def _scene() -> np.ndarray:
    frame = np.full((240, 320, 3), 110, dtype=np.uint8)
    cv2.rectangle(frame, (120, 50), (200, 190), (230, 190, 40), 2)
    for y in range(0, 240, 10):
        cv2.line(frame, (0, y), (320, y), (80, 80, 80), 1)
    return frame


def _partial_cover(frame: np.ndarray) -> np.ndarray:
    covered = frame.copy()
    rng = np.random.default_rng(5)
    covered[:85, :125] = rng.integers(20, 245, (85, 125, 3), dtype=np.uint8)
    return covered


def test_partial_edge_overlay_is_detected_and_clearing_it_recovers():
    base = _scene()
    covered = _partial_cover(base)
    state = CameraTrustState()
    assessments = [
        assess_camera(base, state=state, sample_seconds=1/3)
        for _ in range(3)
    ]
    for i in range(12):
        image = covered.copy()
        image[-1, -1, 0] = i % 3  # normal minor compression/background variation
        assessments.append(assess_camera(image, state=state, sample_seconds=1/3))
    assert any(item.tamper_suspected for item in assessments[-7:])
    assert any("obstructed" in reason for reason in assessments[-1].reasons)
    for i in range(9):
        restored = base.copy()
        restored[-1, -1, 0] = i % 3
        assessments.append(assess_camera(restored, state=state, sample_seconds=1/3))
    assert not assessments[-1].tamper_suspected


def test_small_moving_object_not_called_edge_obstruction():
    base = _scene()
    state = CameraTrustState()
    assessments = [assess_camera(base, state=state, sample_seconds=1/3)]
    for x in range(0, 121, 12):
        moving = base.copy()
        cv2.rectangle(moving, (x, 80), (x + 45, 220), (250, 0, 80), -1)
        assessments.append(assess_camera(moving, state=state, sample_seconds=1/3))
    assert not any(item.tamper_suspected for item in assessments)


def test_global_exposure_changes_are_not_local_obstruction():
    base = _scene()
    for offset in (-70, -30, 20):
        changed = np.clip(
            base.astype(np.int16) + offset, 0, 255
        ).astype(np.uint8)
        assert not localized_occlusion_candidate(base, changed, changed)


def test_local_change_without_persistent_previous_frame_is_not_enough():
    base = _scene()
    covered = _partial_cover(base)
    assert not localized_occlusion_candidate(base, covered, None)
    assert not localized_occlusion_candidate(base, covered, base)


def test_widespread_cctv_day_night_appearance_drift_not_localized():
    base = _scene()
    dark = cv2.GaussianBlur(
        cv2.convertScaleAbs(base, alpha=0.35, beta=0), (31, 31), 7
    )
    assert not localized_occlusion_candidate(base, dark, dark)
