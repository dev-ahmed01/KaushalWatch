"""Development-only fusion of spatial and global camera scene-change probes.

This module is NOT imported by released camera trust or compliance decisions.
A review cue is NOT a tamper accusation or a verified camera movement.
No camera reference is enrolled automatically. The two probes both require
independently confirmed healthy warmup footage for meaningful interpretation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from .camera_persistent_scene_probe import PersistentSceneProbe
from .camera_spatial_scene_shadow import SpatialSceneShadow

VALID_SPATIAL = frozenset(("WARMUP", "SUFFICIENT_TILES", "UNKNOWN_LOW_TEXTURE"))


def combine_shadow_evidence(
    spatial: Mapping[str, object], global_scene: Mapping[str, object]
) -> dict:
    """Return an advisory review cue; never a camera-integrity verdict.

    An already-supported spatial result takes precedence. Persistent global
    difference is only a secondary review cue when spatial texture is unknown.
    A missing cue does not mean camera footage is authenticated or usable.
    """
    status = spatial.get("evidence_status")
    if status not in VALID_SPATIAL:
        raise ValueError("Unrecognized or missing spatial evidence status")
    spatial_alert = spatial.get("review_55")
    global_alert = global_scene.get("persistent_review")
    global_quality_limited = global_scene.get("quality_limited")
    if any(type(v) is not bool for v in (
        spatial_alert, global_alert, global_quality_limited
    )):
        raise ValueError("Shadow probes require explicit booleans and global quality")
    if status != "SUFFICIENT_TILES" and spatial_alert:
        raise ValueError("Spatial review cannot be asserted without sufficient tiles")

    if status == "WARMUP":
        decision, review = "WARMUP", False
    elif status == "SUFFICIENT_TILES":
        decision = "SPATIAL_SCENE_REVIEW" if spatial_alert else "NO_SHADOW_REVIEW"
        review = spatial_alert
    elif global_alert and not global_quality_limited:
        decision, review = "LOW_TEXTURE_GLOBAL_SCENE_REVIEW", True
    else:
        decision, review = "UNKNOWN_LOW_TEXTURE", False

    return {
        "decision": decision,
        "review_cue": review,
        "evidence_status": status,
        "spatial_review": spatial_alert,
        "global_review": global_alert,
        "global_quality_limited": global_quality_limited,
        "production_integration": False,
        "interpretation": "OFFICER_REVIEW_ONLY_NOT_TAMPER_OR_MOVEMENT_PROOF",
    }


@dataclass
class ShadowFusionProbe:
    """Short-window experimental probe, without any operational side effects."""

    spatial: SpatialSceneShadow = field(default_factory=SpatialSceneShadow)
    persistent: PersistentSceneProbe = field(default_factory=PersistentSceneProbe)

    def observe(self, frame: np.ndarray, sample_seconds: float) -> dict:
        spatial = self.spatial.observe(frame, sample_seconds)
        global_scene = self.persistent.observe(frame, sample_seconds)
        return combine_shadow_evidence(spatial, global_scene)
