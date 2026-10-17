"""Frozen-reference scene-cause forensic signals, DEVELOPMENT ONLY.

This module never modifies camera review cues, reference enrollment,
evidence usability, attendance, or compliance. It computes independent
observable measurements and *compatible-with* hypotheses, never claims
that an actor moved a camera or that a labelled normal frame is safe.
All calculations use a stable, explicitly approved OFFLINE reference.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from .camera_spatial_scene_shadow import _small, spatial_metrics

STATUS = frozenset(("SUFFICIENT_TILES", "UNKNOWN_LOW_TEXTURE"))
PHASE_PRESETS = {
    "conservative": (0.36, 3, 2.0),
    "exploratory": (0.22, 3, 3.0),
}
# Response floor, minimum agreeing regions (out of 4), pixel shift tolerance.


def _phase(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Phase translation is a measurement, NOT a verified camera displacement."""
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError("Grayscale shapes must match")
    a = a.astype(np.float32, copy=False)
    b = b.astype(np.float32, copy=False)
    if min(float(a.std()), float(b.std())) < 4.0:
        return 0.0, 0.0, 0.0
    # Subtracting local brightness means reduces purely photometric effects.
    aa = np.ascontiguousarray(a - float(a.mean()))
    bb = np.ascontiguousarray(b - float(b.mean()))
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(aa, bb, window)
    if not all(math.isfinite(v) for v in (dx, dy, response)):
        return 0.0, 0.0, 0.0
    return float(dx), float(dy), max(0., min(1., float(response)))


@dataclass
class SceneCauseDiagnostics:
    """Stateless measurements against the fixed approved comparator."""

    reference_small: np.ndarray

    def __post_init__(self):
        ref = self.reference_small
        if (not isinstance(ref, np.ndarray) or ref.shape != (144, 192)
                or ref.dtype != np.uint8):
            raise ValueError("Fixed 192x144 uint8 grayscale reference is required")
        # A private immutable copy; never re-enrolls from the current stream.
        self.reference_small = ref.copy()
        self.reference_small.setflags(write=False)

    def inspect(self, current: np.ndarray, *, spatial_evidence_status: str) -> dict:
        if spatial_evidence_status not in STATUS:
            raise ValueError("Explicit spatial evidence status is required")
        if (not isinstance(current, np.ndarray) or current.size == 0
                or current.dtype != np.uint8
                or current.ndim != 3 or current.shape[2] != 3):
            raise ValueError("Decoded uint8 BGR sample required")

        ref = self.reference_small
        cur = _small(current)
        # Use the original full frame here: spatial_metrics performs _small
        # internally. Resizing the current frame twice could diverge from
        # the frozen spatial detector near the low-texture boundary.
        measured = spatial_metrics(ref, current)
        if measured["evidence_status"] != spatial_evidence_status:
            raise ValueError("Detector/diagnostic spatial evidence mismatch")

        brightness_delta = float(np.median(cur.astype(np.int16) - ref.astype(np.int16)))
        median_ref = float(np.median(ref))
        median_current = float(np.median(cur))
        brightness_magnitude = abs(brightness_delta)
        ref_contrast = float(np.std(ref))
        current_contrast = float(np.std(cur))
        contrast_ratio = current_contrast / max(ref_contrast, 1.0)

        regions = []
        for y in (slice(0,72), slice(72,144)):
            for x in (slice(0,96), slice(96,192)):
                dx, dy, quality = _phase(ref[y,x], cur[y,x])
                regions.append((dx,dy,quality))
        gdx,gdy,gquality = _phase(ref,cur)
        length = math.hypot(gdx,gdy)
        agreements = {}
        for name,(floor,minimum,tolerance) in PHASE_PRESETS.items():
            coherent = sum(
                q >= floor and math.hypot(dx-gdx,dy-gdy) <= tolerance
                for dx,dy,q in regions
            )
            supported = (
                spatial_evidence_status == "SUFFICIENT_TILES"
                and gquality >= floor and 2.0 <= length <= 28.0
                and coherent >= minimum
            )
            agreements[name] = {
                "candidate_global_translation_supported": bool(supported),
                "quadrants_agreeing": coherent,
                "required_quadrants": minimum,
            }

        changed_quadrants = measured["changed_quadrants"]
        changed_tiles = measured["changed_tiles"]
        localized = bool(changed_tiles > 0 and changed_quadrants <= 2)
        illumination_compatible = bool(
            brightness_magnitude >= 25.0 and
            measured["evidence_status"] == "SUFFICIENT_TILES"
            and (measured["median_tile_correlation"] is not None)
            and measured["median_tile_correlation"] >= 0.70
        )
        # Multiple causes can coexist. Illumination or coherent translation
        # never cancels another cue: a changed scene still needs human review.
        hypotheses = []
        if spatial_evidence_status == "UNKNOWN_LOW_TEXTURE":
            hypotheses.append("STRUCTURAL_EVIDENCE_INSUFFICIENT")
        if illumination_compatible:
            hypotheses.append("PHOTOMETRIC_SHIFT_COMPATIBLE")
        if localized:
            hypotheses.append("LOCAL_FOREGROUND_OR_OCCLUSION_COMPATIBLE")
        if agreements["conservative"]["candidate_global_translation_supported"]:
            hypotheses.append("COHERENT_IMAGE_TRANSLATION_COMPATIBLE")
        if (not hypotheses or hypotheses == ["STRUCTURAL_EVIDENCE_INSUFFICIENT"]):
            hypotheses.append("CAUSE_UNRESOLVED")

        return {
            "status": "DEVELOPMENT_CAUSE_DIAGNOSTIC_NOT_HELD_OUT",
            "hypotheses": hypotheses,
            "spatial_evidence_status": spatial_evidence_status,
            "reference_median_brightness": round(median_ref,3),
            "current_median_brightness": round(median_current,3),
            "median_brightness_delta": round(brightness_delta,3),
            "contrast_ratio": round(contrast_ratio,4),
            "eligible_tiles": measured["eligible_tiles"],
            "changed_tiles": changed_tiles,
            "changed_quadrants": changed_quadrants,
            "changed_fraction": measured["changed_fraction"],
            "median_tile_correlation": measured["median_tile_correlation"],
            "global_phase_response": round(gquality,4),
            "global_phase_translation_pixels": [round(gdx,3),round(gdy,3)],
            "quadrant_phase_responses": [round(item[2],4) for item in regions],
            "translation_preset_sweep": agreements,
            "camera_movement_proven": False,
            "reference_updated": False,
            "suppresses_raw_review": False,
            "evidence_usable_verified": False,
            "production_integration": False,
        }
