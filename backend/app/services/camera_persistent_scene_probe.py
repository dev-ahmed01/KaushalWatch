"""Development-only persistent scene-change evidence for a fixed camera.

The warmup comparator is temporary and MUST come from a known healthy
inspection window. It is never enrolled as a verified camera reference.
A persistent appearance change is an OFFICER REVIEW cue, not motion proof.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


def _gray_small(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return cv2.resize(gray, (96, 72), interpolation=cv2.INTER_AREA)


def _correlation(a: np.ndarray, b: np.ndarray) -> float:
    left = a.astype(np.float32)
    right = b.astype(np.float32)
    left -= float(left.mean())
    right -= float(right.mean())
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.sum(left * right) / denominator) if denominator >= 1e-5 else 0.0


@dataclass
class PersistentSceneProbe:
    """A shadow evaluator; never automatically promotes a camera reference."""

    warmup_seconds: float = 10.0
    confirmation_seconds: float = 12.0
    correlation_floor: float = 0.67
    elapsed: float = 0.0
    changed_for: float = 0.0
    initial_frames: list[np.ndarray] = field(default_factory=list, repr=False)
    temporary_reference: np.ndarray | None = field(default=None, repr=False)

    def observe(self, frame: np.ndarray, sample_seconds: float) -> dict:
        if not np.isfinite(sample_seconds) or sample_seconds <= 0:
            raise ValueError("sample_seconds must be positive and finite")
        if frame is None or frame.size == 0:
            raise ValueError("frame must be nonempty")
        small = _gray_small(frame)
        self.elapsed += sample_seconds
        if self.temporary_reference is None:
            self.initial_frames.append(small.copy())
            if self.elapsed >= self.warmup_seconds:
                # Median rejects a brief pedestrian occupying the foreground.
                self.temporary_reference = np.median(
                    np.stack(self.initial_frames, axis=0), axis=0
                ).astype(np.uint8)
                self.initial_frames.clear()
            return {
                "signal": "WARMUP", "scene_correlation": None,
                "low_similarity": False, "persistent_review": False,
                "changed_seconds": 0.0, "quality_limited": False,
            }
        correlation = _correlation(self.temporary_reference, small)
        changed = correlation < self.correlation_floor
        self.changed_for = self.changed_for + sample_seconds if changed else 0.0
        persistent = self.changed_for >= self.confirmation_seconds
        if persistent:
            signal = "PERSISTENT_SCENE_CHANGE_REVIEW"
        elif changed:
            signal = "UNCONFIRMED_SCENE_DIFFERENCE"
        else:
            signal = "NO_PERSISTENT_CHANGE"
        texture = float(cv2.Laplacian(small, cv2.CV_64F).var())
        return {
            "signal": signal,
            "scene_correlation": round(correlation, 5),
            "low_similarity": changed,
            "persistent_review": persistent,
            "changed_seconds": round(self.changed_for, 3),
            "quality_limited": texture < 5.0,
        }
