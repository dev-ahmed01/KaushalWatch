"""Camera evidence-quality assessment for a fixed-view surveillance feed.

A failed trust check indicates unusable evidence, not intentional tampering.
State and reference frames must be scoped to a single continuous video.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
    return max(0.0, min(1.0, 1.0 - float(diff) / 255.0))


def _scene_correlation(reference: np.ndarray, current: np.ndarray) -> float:
    """Lighting-insensitive comparison of whole-frame scene composition."""
    a = cv2.resize(_gray(reference), (96, 72)).astype(np.float32)
    b = cv2.resize(_gray(current), (96, 72)).astype(np.float32)
    a -= float(a.mean())
    b -= float(b.mean())
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norm < 1e-4:
        return 0.0
    return float(np.clip(np.sum(a * b) / norm, -1, 1))


def scene_shift_score(reference: np.ndarray, current: np.ndarray) -> float:
    """Coarse composition change, not a geometric-motion estimate."""
    return max(0.0, 1.0 - _scene_correlation(reference, current))


@dataclass
class CameraTrustState:
    """Temporal state scoped to ONE video-processing run."""
    previous_gray: np.ndarray | None = field(default=None, repr=False)
    reference_frame: np.ndarray | None = field(default=None, repr=False)
    reference_blur: float | None = None
    reference_light: float | None = None
    consecutive_seconds: dict[str, float] = field(default_factory=dict)

    def persistent(self, key: str, active: bool, seconds: float, minimum: float) -> bool:
        self.consecutive_seconds[key] = (
            self.consecutive_seconds.get(key, 0.0) + seconds if active else 0.0
        )
        return self.consecutive_seconds[key] >= minimum


def assess_camera(
    frame: np.ndarray,
    previous_frame: np.ndarray | None = None,
    reference_frame: np.ndarray | None = None,
    blur_threshold: float = 45.0,
    dark_threshold: float = 28.0,
    frozen_similarity: float = 0.9995,
    scene_shift_threshold: float = 0.88,
    *,
    state: CameraTrustState | None = None,
    sample_seconds: float = 1.0,
) -> CameraTrust:
    """Determine whether visual evidence remains usable.

    Legacy numeric arguments remain for API compatibility. The relative
    v2 checks require separate calibration and an explicit candidate profile.
    """
    if frame is None or frame.size == 0:
        raise ValueError("camera frame must be non-empty")
    if sample_seconds <= 0:
        raise ValueError("sample_seconds must be positive")
    memory = state if state is not None else CameraTrustState()
    if memory.reference_frame is None:
        memory.reference_frame = (
            reference_frame if reference_frame is not None else frame
        ).copy()
        memory.reference_blur = blur_score(memory.reference_frame)
        memory.reference_light = luminance(memory.reference_frame)

    gray = _gray(frame)
    b = blur_score(frame)
    light = float(gray.mean())
    base_blur = max(0.001, float(memory.reference_blur))
    blur_ratio = b / base_blur
    corr = _scene_correlation(memory.reference_frame, frame)
    light_delta = abs(light - float(memory.reference_light))

    # Compression noise and tiny foreground changes must not create a
    # frozen-stream alarm; exact identical decoded frames must persist.
    previous = memory.previous_gray
    if previous is None and previous_frame is not None:
        previous = _gray(previous_frame)
    identical = previous is not None and np.array_equal(gray, previous)
    memory.previous_gray = gray.copy()
    frozen = memory.persistent("frozen", identical, sample_seconds, 3.0)

    # Baseline-relative blur is essential for naturally low-texture CCTV.
    blurry = memory.persistent(
        "blur", base_blur >= 3.0 and blur_ratio < 0.27 and corr > 0.73,
        sample_seconds, 1.5,
    )
    dark = memory.persistent(
        "dark", light < dark_threshold, sample_seconds, 1.0,
    )

    changed = corr < 0.66
    occlusion = changed and (
        light_delta > 28 or blur_ratio > 7.0 or blur_ratio < 0.12
    )
    # A complete viewpoint change must persist between adjacent frames;
    # otherwise independent noisy/fast-changing foreground frames can look
    # unlike the initial reference even when the camera never moved.
    movement = changed and not occlusion and (
        0.35 <= blur_ratio <= 5.0
        and light_delta <= 28
        and previous is not None
        and _scene_correlation(previous, frame) > 0.72
    )
    obstructed = memory.persistent(
        "obstructed", occlusion, sample_seconds, 1.5,
    )
    shifted = memory.persistent(
        "shift", movement, sample_seconds, 1.5,
    )

    reasons: list[str] = []
    if frozen:
        reasons.append("possible frozen/replayed stream")
    if blurry:
        reasons.append("image excessively blurred")
    if dark:
        reasons.append("image too dark for reliable verification")
    if obstructed:
        reasons.append("camera view may be obstructed")
    if shifted:
        reasons.append("camera viewpoint may have shifted")

    unusable = frozen or blurry or dark or obstructed or shifted
    penalty = (
        (60 if frozen else 0)
        + (60 if blurry else 0)
        + (60 if dark else 0)
        + (65 if obstructed else 0)
        + (60 if shifted else 0)
    )
    return CameraTrust(
        trusted=not unusable,
        score=float(max(0, 100 - penalty)),
        is_frozen=frozen,
        is_blurry=blurry,
        is_too_dark=dark,
        scene_shift=shifted,
        reasons=reasons,
    )
