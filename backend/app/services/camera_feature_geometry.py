"""Diagnostic-only landmark evidence for fixed-camera displacement.

Low-confidence matches are UNKNOWN, not proof of an unmoved camera.
Reference images are never automatically updated.
"""
from __future__ import annotations
import cv2
import numpy as np


def landmark_displacement(reference: np.ndarray, current: np.ndarray) -> dict:
    """RANSAC partial affine of spatially distributed ORB landmarks.

    Displacement values are for normalized 480x360 images, not source pixels.
    A positive result is evidence of possible viewpoint shift, not sabotage.
    """
    size = (480, 360)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    def prep(image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        return clahe.apply(cv2.resize(gray, size, interpolation=cv2.INTER_AREA))
    a, b = prep(reference), prep(current)
    orb = cv2.ORB_create(nfeatures=1500, fastThreshold=7, scaleFactor=1.2)
    kp_a, desc_a = orb.detectAndCompute(a, None)
    kp_b, desc_b = orb.detectAndCompute(b, None)
    result = {
        "match_status": "INSUFFICIENT_MATCHES",
        "matches": 0, "inliers": 0, "inlier_ratio": 0.0,
        "landmark_tiles": 0, "landmark_width_fraction": 0.0,
        "landmark_height_fraction": 0.0,
        "destination_tiles": 0,
        "destination_width_fraction": 0.0,
        "destination_height_fraction": 0.0,
        "transform_plausible": False,
        "centre_displacement_px": 0.0, "rotation_deg": 0.0,
        "scale": 1.0, "geometric_shift": False, "confidence": False,
    }
    if desc_a is None or desc_b is None:
        return result
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(desc_a, desc_b, k=2)
    good = [m for pair in pairs if len(pair) == 2
            for m, n in [pair] if m.distance < .78 * n.distance]
    result["matches"] = len(good)
    if len(good) < 12:
        return result
    src = np.float32([kp_a[m.queryIdx].pt for m in good])
    dst = np.float32([kp_b[m.trainIdx].pt for m in good])
    affine, mask = cv2.estimateAffinePartial2D(
        src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.5,
        maxIters=1500, confidence=.98,
    )
    if affine is None or mask is None:
        result["match_status"] = "NO_CONSISTENT_TRANSFORM"
        return result
    included = mask.ravel().astype(bool)
    inliers = src[included]
    dst_inliers = dst[included]
    count = len(inliers)
    ratio = count / len(good)
    tiles = len({(min(2, int(x / 160)), min(2, int(y / 120)))
                 for x, y in inliers})
    width_fraction = float(np.ptp(inliers[:, 0]) / 480) if count else 0.
    height_fraction = float(np.ptp(inliers[:, 1]) / 360) if count else 0.
    dst_tiles = len({(min(2, int(x / 160)), min(2, int(y / 120)))
                     for x, y in dst_inliers})
    dst_width = float(np.ptp(dst_inliers[:, 0]) / 480) if count else 0.
    dst_height = float(np.ptp(dst_inliers[:, 1]) / 360) if count else 0.
    scale = float(np.hypot(affine[0, 0], affine[1, 0]))
    rotation = float(np.degrees(np.arctan2(affine[1, 0], affine[0, 0])))
    centre = np.array([240., 180., 1.])
    movement = float(np.linalg.norm(affine @ centre - centre[:2]))
    plausible = bool(
        np.isfinite(affine).all()
        and np.isfinite([scale, rotation, movement]).all()
        and 0.70 <= scale <= 1.40
        and abs(rotation) <= 30.0
    )
    result.update({
        "inliers": count, "inlier_ratio": round(float(ratio), 4),
        "landmark_tiles": tiles,
        "landmark_width_fraction": round(width_fraction, 4),
        "landmark_height_fraction": round(height_fraction, 4),
        "destination_tiles": dst_tiles,
        "destination_width_fraction": round(dst_width, 4),
        "destination_height_fraction": round(dst_height, 4),
        "transform_plausible": plausible,
        "scale": round(scale, 4) if np.isfinite(scale) else None,
    })
    if not plausible:
        result["match_status"] = "IMPLAUSIBLE_AFFINE_TRANSFORM"
        return result
    confident = bool(
        count >= 12 and ratio >= .30
        and tiles >= 3 and dst_tiles >= 3
        and width_fraction >= .25 and height_fraction >= .25
        and dst_width >= .20 and dst_height >= .20
    )
    result["confidence"] = confident
    if not confident:
        result["match_status"] = "SPARSE_OR_UNRELIABLE_LANDMARKS"
        return result
    shift = movement >= 8. or abs(rotation) >= 2. or abs(scale - 1) >= .05
    result.update({
        "match_status": "MATCHED_GEOMETRY",
        "centre_displacement_px": round(movement, 3),
        "rotation_deg": round(rotation, 3),
        "scale": round(scale, 4),
        "geometric_shift": bool(shift),
    })
    return result
