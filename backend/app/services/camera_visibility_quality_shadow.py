"""Phase 3N: independent, UNCALIBRATED visibility/sharpness research axes.

Measures image quality relative to a fixed, separately supplied reference.
A low sharpness hypothesis may coexist with structural scene change, low
texture, illumination or an already open alert. It NEVER clears a review
cue, declares tampering/recovery, reenrolls a reference or decides attendance.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

from .camera_spatial_scene_shadow import _small

QUALITY = frozenset((
    "SHARPNESS_LOSS_COMPATIBLE",
    "REFERENCE_TEXTURE_INSUFFICIENT",
    "ILLUMINATION_CONFOUNDED",
    "NO_SHARPNESS_LOSS_SIGNAL",
))


def _features(gray: np.ndarray) -> dict:
    if (gray.dtype != np.uint8 or gray.shape != (144, 192)):
        raise ValueError("Canonical 192x144 uint8 luminance required")
    # Variance of Laplacian alone is sensitive to brightness/contrast;
    # use reference-normalized edge fraction and contrast as separate axes.
    lap = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gx, gy)
    return {
        "laplacian_variance": float(lap.var()),
        "edge_fraction": float((gradient >= 24.0).mean()),
        "luma_median": float(np.median(gray)),
        "contrast_std": float(gray.std()),
        "low_dynamic_range": bool(np.percentile(gray,95)-np.percentile(gray,5)<20),
    }


@dataclass
class VisibilityQualityShadow:
    reference_small: np.ndarray

    def __post_init__(self):
        ref = self.reference_small
        if not isinstance(ref, np.ndarray) or ref.dtype != np.uint8 or ref.shape != (144,192):
            raise ValueError("Fixed 192x144 uint8 reference required")
        self.reference_small = ref.copy()
        self.reference_small.setflags(write=False)
        self.reference_features = _features(self.reference_small)

    @classmethod
    def from_bgr(cls, frame: np.ndarray) -> "VisibilityQualityShadow":
        if not isinstance(frame,np.ndarray) or frame.dtype!=np.uint8 or frame.ndim!=3 or frame.shape[2]!=3:
            raise ValueError("Source reference must be uint8 BGR")
        return cls(_small(frame))

    def inspect(self, frame: np.ndarray) -> dict:
        if (not isinstance(frame,np.ndarray) or frame.dtype != np.uint8
                or frame.ndim!=3 or frame.shape[2]!=3 or frame.size==0):
            raise ValueError("Decoded uint8 BGR frame required")
        cur = _features(_small(frame))
        ref = self.reference_features
        denom = max(ref["laplacian_variance"], 1e-6)
        focus_ratio = cur["laplacian_variance"]/denom
        edge_ratio = cur["edge_fraction"]/max(ref["edge_fraction"],1e-6)
        contrast_ratio = cur["contrast_std"]/max(ref["contrast_std"],1e-6)
        illumination_shift = abs(cur["luma_median"]-ref["luma_median"])
        if ref["laplacian_variance"] < 12.0 or ref["edge_fraction"] < 0.035:
            decision = "REFERENCE_TEXTURE_INSUFFICIENT"
        elif illumination_shift >= 45.0 or cur["low_dynamic_range"]:
            decision = "ILLUMINATION_CONFOUNDED"
        elif focus_ratio < 0.35 and edge_ratio < 0.65 and contrast_ratio >= 0.25:
            decision = "SHARPNESS_LOSS_COMPATIBLE"
        else:
            decision = "NO_SHARPNESS_LOSS_SIGNAL"
        return {
            "status":"OFFLINE_UNCALIBRATED_VISIBILITY_AXES",
            "quality_hypothesis":decision,
            "reference_laplacian_variance":round(ref["laplacian_variance"],3),
            "sample_laplacian_variance":round(cur["laplacian_variance"],3),
            "relative_sharpness":round(float(focus_ratio),5),
            "reference_edge_fraction":round(ref["edge_fraction"],5),
            "sample_edge_fraction":round(cur["edge_fraction"],5),
            "relative_edge_fraction":round(float(edge_ratio),5),
            "relative_contrast":round(float(contrast_ratio),5),
            "median_brightness_shift":round(float(illumination_shift),3),
            "image_usable_verified":False,
            "blur_or_defocus_proven":False,
            "reference_provenance_verified":False,
            "detector_review_suppressed":False,
            "automatic_recovery":False,
            "production_integration":False,
        }
