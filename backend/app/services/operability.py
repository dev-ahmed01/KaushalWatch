from __future__ import annotations
import cv2
import numpy as np


def apparent_motion_state(frames: list[np.ndarray], roi: tuple[int, int, int, int], threshold: float = 0.8) -> tuple[str, float]:
    """Visual activity proxy only; never a mechanical/electrical health diagnosis."""
    if len(frames) < 3:
        return "UNCERTAIN", 0.0
    x1, y1, x2, y2 = roi
    scores: list[float] = []
    prev = None
    for frame in frames:
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return "UNCERTAIN", 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if prev is not None:
            scores.append(float(np.mean(cv2.absdiff(prev, gray))))
        prev = gray
    if not scores:
        return "UNCERTAIN", 0.0
    score = float(np.median(scores))
    return ("APPARENTLY_ACTIVE" if score >= threshold else "APPARENTLY_INACTIVE"), score
