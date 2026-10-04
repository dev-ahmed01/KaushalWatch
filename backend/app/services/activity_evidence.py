from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class ActivityDecision:
    motion_fraction: float
    worker_present: bool
    instantaneous_motion: bool
    active: bool
    positive_ratio: float
    samples: int


def roi_motion_fraction(
    previous_frame: np.ndarray | None,
    current_frame: np.ndarray,
    roi: tuple[int, int, int, int],
    pixel_delta_threshold: int = 18,
) -> float:
    """Return the fraction of ROI pixels whose appearance changed materially.

    This is a visual activity proxy for fixed-camera footage. It does not infer
    a specific task, machine state, safety status, or worker identity.
    """
    if previous_frame is None:
        return 0.0

    x1, y1, x2, y2 = roi
    h, w = current_frame.shape[:2]
    x1 = max(0, min(w, int(x1)))
    x2 = max(0, min(w, int(x2)))
    y1 = max(0, min(h, int(y1)))
    y2 = max(0, min(h, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return 0.0

    prev_crop = previous_frame[y1:y2, x1:x2]
    curr_crop = current_frame[y1:y2, x1:x2]
    if prev_crop.size == 0 or curr_crop.size == 0:
        return 0.0

    prev_gray = cv2.cvtColor(prev_crop, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_crop, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (5, 5), 0)
    curr_gray = cv2.GaussianBlur(curr_gray, (5, 5), 0)

    diff = cv2.absdiff(prev_gray, curr_gray)
    changed = diff >= int(pixel_delta_threshold)
    return float(np.mean(changed))


class TemporalActivityGate:
    """Require sustained motion evidence while a confirmed worker occupies a zone."""

    def __init__(
        self,
        window_frames: int,
        motion_fraction_threshold: float = 0.015,
        required_positive_ratio: float = 0.60,
    ) -> None:
        if window_frames <= 0:
            raise ValueError("window_frames must be > 0")
        if not 0 <= motion_fraction_threshold <= 1:
            raise ValueError("motion_fraction_threshold must be between 0 and 1")
        if not 0 < required_positive_ratio <= 1:
            raise ValueError("required_positive_ratio must be in (0, 1]")

        self.window_frames = int(window_frames)
        self.motion_fraction_threshold = float(motion_fraction_threshold)
        self.required_positive_ratio = float(required_positive_ratio)
        self.required_positive_frames = max(
            1,
            int(math.ceil(self.window_frames * self.required_positive_ratio)),
        )
        self._history: deque[bool] = deque(maxlen=self.window_frames)

    def reset(self) -> None:
        self._history.clear()

    def update(self, worker_present: bool, motion_fraction: float) -> ActivityDecision:
        instantaneous_motion = (
            bool(worker_present)
            and float(motion_fraction) >= self.motion_fraction_threshold
        )
        self._history.append(instantaneous_motion)

        positive = sum(self._history)
        ratio = positive / len(self._history) if self._history else 0.0
        active = (
            len(self._history) == self.window_frames
            and positive >= self.required_positive_frames
        )

        return ActivityDecision(
            motion_fraction=float(motion_fraction),
            worker_present=bool(worker_present),
            instantaneous_motion=instantaneous_motion,
            active=active,
            positive_ratio=float(ratio),
            samples=len(self._history),
        )
