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


def inset_box(
    box: tuple[int, int, int, int],
    inset_ratio: float = 0.08,
) -> tuple[int, int, int, int]:
    """Inset a person box to reduce background-edge motion contamination."""
    if not 0 <= inset_ratio < 0.5:
        raise ValueError("inset_ratio must be in [0, 0.5)")

    x1, y1, x2, y2 = [int(v) for v in box]
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    dx = int(round(width * inset_ratio))
    dy = int(round(height * inset_ratio))

    nx1, ny1 = x1 + dx, y1 + dy
    nx2, ny2 = x2 - dx, y2 - dy

    if nx2 <= nx1 or ny2 <= ny1:
        return x1, y1, x2, y2
    return nx1, ny1, nx2, ny2


def worker_motion_fraction(
    previous_frame: np.ndarray | None,
    current_frame: np.ndarray,
    worker_boxes: list[tuple[int, int, int, int]],
    pixel_delta_threshold: int = 18,
    inset_ratio: float = 0.08,
) -> float:
    """Measure motion around currently visible registered workers.

    Each worker is scored in a slightly inset bounding box. The zone score is
    the maximum worker score because one genuinely active operator is enough to
    establish visual activity in that work cell. This avoids diluting worker
    motion by the size of a large configured work-cell rectangle.
    """
    if previous_frame is None or not worker_boxes:
        return 0.0

    scores = [
        roi_motion_fraction(
            previous_frame,
            current_frame,
            inset_box(box, inset_ratio=inset_ratio),
            pixel_delta_threshold=pixel_delta_threshold,
        )
        for box in worker_boxes
    ]
    return float(max(scores)) if scores else 0.0


class TemporalActivityGate:
    """Require sustained motion evidence while a confirmed worker occupies a zone."""

    def __init__(
        self,
        window_frames: int,
        motion_fraction_threshold: float = 0.02,
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
