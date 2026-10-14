"""Landmark movement candidates tested on synthetic scenes, not UHCTD media."""
import cv2
import numpy as np

from app.services.camera_feature_geometry import landmark_displacement


def _reference():
    return np.random.default_rng(20261009).integers(
        70, 180, size=(180, 240, 3), dtype=np.uint8
    )


def test_coherent_camera_translation_produces_confident_shift():
    base = _reference()
    moved = cv2.warpAffine(
        base, np.float32([[1, 0, 21], [0, 1, 8]]),
        (240, 180), borderValue=(70, 70, 70)
    )
    feature = landmark_displacement(base, moved)
    assert feature["confidence"]
    assert feature["geometric_shift"]
    assert feature["inliers"] >= 12
    assert feature["landmark_tiles"] >= 3
    assert feature["centre_displacement_px"] > 30


def test_brightness_change_with_unchanged_camera_geometry():
    base = _reference()
    brighter = cv2.convertScaleAbs(base, alpha=1, beta=18)
    feature = landmark_displacement(base, brighter)
    assert feature["confidence"]
    assert not feature["geometric_shift"]
    assert feature["centre_displacement_px"] < 2


def test_partial_edge_obstruction_does_not_look_like_global_shift():
    base = _reference()
    patched = base.copy()
    patched[:70, :100] = np.random.default_rng(7).integers(
        30, 230, size=(70, 100, 3), dtype=np.uint8
    )
    feature = landmark_displacement(base, patched)
    assert not feature["geometric_shift"]


def test_blank_low_texture_frame_has_unknown_geometry_not_stable_verdict():
    base = _reference()
    dim = np.full_like(base, 64)
    feature = landmark_displacement(base, dim)
    assert feature["match_status"] == "INSUFFICIENT_MATCHES"
    assert not feature["confidence"]
    assert not feature["geometric_shift"]



def test_degenerate_affine_never_counts_as_confident_movement(monkeypatch):
    """Reject a collapsed RANSAC result even with enough apparent inliers."""
    real = cv2.estimateAffinePartial2D

    def collapsed(src, dst, **kwargs):
        # Pretend every candidate matched, but map all positions to one pixel.
        affine = np.float64([[0.0003, 0, 200], [0, 0.0003, 120]])
        mask = np.ones((len(src), 1), dtype=np.uint8)
        return affine, mask

    monkeypatch.setattr(cv2, "estimateAffinePartial2D", collapsed)
    try:
        feature = landmark_displacement(_reference(), _reference())
    finally:
        monkeypatch.setattr(cv2, "estimateAffinePartial2D", real)
    assert not feature["confidence"]
    assert not feature["geometric_shift"]
    assert feature["match_status"] == "IMPLAUSIBLE_AFFINE_TRANSFORM"
    assert feature["scale"] < 0.01


def test_spatially_collapsed_destination_does_not_yield_shift(monkeypatch):
    real = cv2.estimateAffinePartial2D

    def pretend(src, dst, **kwargs):
        # Deliberately create tiny destination landmark coverage.
        mask = np.ones((len(src), 1), dtype=np.uint8)
        dst[:] = np.float32([200.0, 120.0])
        return np.float64([[1.0, 0, 15.0], [0, 1.0, 5.0]]), mask

    monkeypatch.setattr(cv2, "estimateAffinePartial2D", pretend)
    try:
        feature = landmark_displacement(_reference(), _reference())
    finally:
        monkeypatch.setattr(cv2, "estimateAffinePartial2D", real)
    assert not feature["confidence"]
    assert not feature["geometric_shift"]
