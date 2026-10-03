from __future__ import annotations
import cv2
import numpy as np
from app.models import CameraTrust


def _gray(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame


def blur_score(frame: np.ndarray) -> float:
    return float(cv2.Laplacian(_gray(frame), cv2.CV_64F).var())


def luminance(frame: np.ndarray) -> float:
    return float(_gray(frame).mean())


def frame_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_small = cv2.resize(_gray(a), (64, 64)).astype(np.float32)
    b_small = cv2.resize(_gray(b), (64, 64)).astype(np.float32)
    diff = np.mean(np.abs(a_small - b_small))
    return max(0.0, min(1.0, 1.0 - diff / 255.0))


def scene_shift_score(reference: np.ndarray, current: np.ndarray) -> float:
    orb = cv2.ORB_create(nfeatures=250)
    kp1, des1 = orb.detectAndCompute(_gray(reference), None)
    kp2, des2 = orb.detectAndCompute(_gray(current), None)
    if des1 is None or des2 is None or len(kp1) < 8 or len(kp2) < 8:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des1, des2)
    if not matches:
        return 1.0
    good = [m for m in matches if m.distance < 60]
    return 1.0 - min(1.0, len(good) / max(1, min(len(kp1), len(kp2))))


def assess_camera(
    frame: np.ndarray,
    previous_frame: np.ndarray | None = None,
    reference_frame: np.ndarray | None = None,
    blur_threshold: float = 45.0,
    dark_threshold: float = 28.0,
    frozen_similarity: float = 0.9995,
    scene_shift_threshold: float = 0.88,
) -> CameraTrust:
    b = blur_score(frame)
    l = luminance(frame)
    frozen = previous_frame is not None and frame_similarity(frame, previous_frame) >= frozen_similarity
    shift = reference_frame is not None and scene_shift_score(reference_frame, frame) >= scene_shift_threshold
    blurry = b < blur_threshold
    dark = l < dark_threshold
    reasons: list[str] = []
    if frozen: reasons.append("possible frozen/replayed stream")
    if blurry: reasons.append("image excessively blurred")
    if dark: reasons.append("image too dark for reliable verification")
    if shift: reasons.append("camera viewpoint may have shifted")
    penalties = (40 if frozen else 0) + (20 if blurry else 0) + (20 if dark else 0) + (25 if shift else 0)
    score = max(0.0, 100.0 - penalties)
    return CameraTrust(
        trusted=score > 65,
        score=score,
        is_frozen=frozen,
        is_blurry=blurry,
        is_too_dark=dark,
        scene_shift=shift,
        reasons=reasons,
    )
