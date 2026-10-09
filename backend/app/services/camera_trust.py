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



def _registered_translation(reference: np.ndarray, current: np.ndarray) -> bool:
    """Require coherent global displacement, not merely different scene pixels."""
    size = (192, 144)
    def edge_map(frame: np.ndarray) -> np.ndarray:
        grayscale = cv2.resize(_gray(frame), size)
        return cv2.Laplacian(cv2.equalizeHist(grayscale), cv2.CV_32F)
    a = edge_map(reference)
    b = edge_map(current)
    if float(np.std(a)) < 5.0 or float(np.std(b)) < 5.0:
        return False
    (dx, dy), response = cv2.phaseCorrelate(a, b)
    if not np.isfinite([dx, dy, response]).all():
        return False
    return bool(response >= 0.25 and float(np.hypot(dx, dy)) >= 3.5)


@dataclass
class CameraTrustState:
    """Temporal state scoped to ONE video-processing run."""
    previous_gray: np.ndarray | None = field(default=None, repr=False)
    reference_frame: np.ndarray | None = field(default=None, repr=False)
    reference_blur: float | None = None
    reference_light: float | None = None
    consecutive_seconds: dict[str, float] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    registration_checked_at: float = -999.0
    registration_shift: bool = False
    reference_reviewed: bool = False
    reference_id: str | None = None
    reference_mode: str | None = None

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
    """Separate evidence quality from *suspected* tamper events.

    Legacy parameters remain API-compatible. Relative v3 settings require
    their own vision profile and must not silently replace frozen v1.
    """
    if frame is None or frame.size == 0:
        raise ValueError("camera frame must be nonempty")
    if sample_seconds <= 0:
        raise ValueError("sample_seconds must be positive")
    memory = state if state is not None else CameraTrustState()
    if memory.reference_frame is None:
        memory.reference_frame = (
            reference_frame if reference_frame is not None else frame
        ).copy()
    if memory.reference_frame.shape[:2] != frame.shape[:2]:
        raise ValueError("Camera frame and reviewed reference resolution must match")
    if memory.reference_blur is None:
        memory.reference_blur = blur_score(memory.reference_frame)
    if memory.reference_light is None:
        memory.reference_light = luminance(memory.reference_frame)

    reference = memory.reference_frame
    gray = _gray(frame)
    image_light = float(gray.mean())
    blur = blur_score(frame)
    base_blur = max(0.001, float(memory.reference_blur))
    blur_ratio = blur / base_blur
    brightness_delta = abs(image_light - float(memory.reference_light))
    corr = _scene_correlation(reference, frame)

    previous = memory.previous_gray
    if previous is None and previous_frame is not None:
        previous = _gray(previous_frame)
    identical = previous is not None and np.array_equal(gray, previous)
    memory.previous_gray = gray.copy()
    memory.elapsed_seconds += sample_seconds

    # Exact identical black video is not sufficient proof of a replay.
    frozen = memory.persistent(
        "frozen", identical and image_light >= dark_threshold and blur >= 3.0,
        sample_seconds, 3.0,
    )
    dark = memory.persistent(
        "dark", image_light < dark_threshold, sample_seconds, 1.0,
    )
    blurry = memory.persistent(
        "blur", base_blur >= 3.0 and blur_ratio < 0.27
        and corr > 0.73 and brightness_delta < 35.0,
        sample_seconds, 1.5,
    )
    # Poor visibility must not automatically become a tampering allegation.
    low_detail = memory.persistent(
        "low_detail", image_light < 95.0 and blur < 12.0,
        sample_seconds, 1.5,
    )

    # A global dimming + loss of texture can be a normal camera
    # illumination/imaging regime change. It is NOT independent evidence
    # that the lens is covered. This is a candidate safeguard, not a
    # validated guarantee: a dark translucent obstruction may resemble it.
    dimmed_reference_regime = (
        image_light >= dark_threshold
        and image_light <= 0.75 * float(memory.reference_light)
        and blur_ratio < 0.15
    )
    candidate_obstruction = (
        corr < 0.66
        and (blur_ratio < 0.12 or blur_ratio > 7.0)
        and image_light >= dark_threshold
        and not dimmed_reference_regime
    )
    obstructed = memory.persistent(
        "obstructed", candidate_obstruction, sample_seconds, 1.5,
    )

    # Change in raw appearance is not sufficient for camera displacement.
    # Compare spatially coherent registration while controlling CPU usage.
    candidate_shift = (
        corr < 0.66 and not candidate_obstruction
        and 0.35 <= blur_ratio <= 5.0 and brightness_delta <= 50.0
        and previous is not None
        and _scene_correlation(previous, frame) > 0.72
    )
    if not candidate_shift:
        memory.registration_shift = False
    elif memory.elapsed_seconds - memory.registration_checked_at >= 1.0:
        memory.registration_checked_at = memory.elapsed_seconds
        memory.registration_shift = _registered_translation(reference, frame)
    shifted = memory.persistent(
        "shift", candidate_shift and memory.registration_shift,
        sample_seconds, 1.5,
    )

    reasons: list[str] = []
    if frozen:
        reasons.append("possible frozen/replayed stream")
    if blurry:
        reasons.append("image excessively blurred")
    if dark:
        reasons.append("image too dark for reliable verification")
    if low_detail:
        reasons.append("low-detail scene limits visual verification")
    if obstructed:
        reasons.append("camera view may be obstructed")
    if shifted:
        reasons.append("camera viewpoint may have shifted")

    # Optical defocus alone is insufficient to infer intentional tampering.
    suspected_tamper = frozen or obstructed or shifted
    degraded_visibility = blurry or dark or low_detail
    unusable = suspected_tamper or degraded_visibility
    penalty = sum((
        60 if frozen else 0,
        60 if blurry else 0,
        60 if dark else 0,
        60 if low_detail else 0,
        65 if obstructed else 0,
        60 if shifted else 0,
    ))
    return CameraTrust(
        trusted=not unusable,
        score=float(max(0, 100 - penalty)),
        is_frozen=frozen,
        is_blurry=blurry,
        is_too_dark=dark,
        scene_shift=shifted,
        tamper_suspected=suspected_tamper,
        quality_status="DEGRADED_VISIBILITY" if degraded_visibility else "SUFFICIENT",
        integrity_status="SUSPECTED_TAMPERING" if suspected_tamper else "NO_TAMPER_SIGNAL",
        camera_status=(
            "SUSPECTED_TAMPERING" if suspected_tamper
            else "DEGRADED_VISIBILITY" if degraded_visibility else "USABLE"
        ),
        reference_status=(
            "REVIEWED_REFERENCE" if memory.reference_reviewed
            else "UNVERIFIED_INITIAL_FRAME"
        ),
        reference_id=memory.reference_id,
        reasons=reasons,
    )
