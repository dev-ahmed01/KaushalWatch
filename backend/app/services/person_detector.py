from __future__ import annotations
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


class PersonDetector:
    """Zero-download baseline. Replace with the chosen lightweight detector before final benchmarking."""

    def __init__(self) -> None:
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        target_w = min(w, 960)
        scale = target_w / w
        img = cv2.resize(frame, (target_w, int(h * scale))) if scale < 1 else frame
        rects, weights = self.hog.detectMultiScale(img, winStride=(8, 8), padding=(8, 8), scale=1.05)
        inv = 1 / scale if scale else 1
        return [
            Detection(int(x*inv), int(y*inv), int((x+rw)*inv), int((y+rh)*inv), float(weight))
            for (x, y, rw, rh), weight in zip(rects, weights)
        ]
