"""Runnable three-axis Camera Trust shadow adapter.

Requires an external, explicitly labeled quality signal; never guesses
whether footage is sufficient for a particular training activity. Uses the
existing spatial/global shadow detector without changing its thresholds.
An approved reference record is governance metadata only; the shadow
detector's temporary image comparator is NOT automatically substituted
or certified by this adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .camera_evidence_axes_shadow import (
    QUALITY_VALUES,
    compose_camera_evidence_axes,
)
from .camera_reference_lifecycle_shadow import ShadowReferenceLifecycle
from .camera_shadow_fusion import ShadowFusionProbe


@dataclass
class ThreeAxisCameraShadowProbe:
    """Per-stream state, no I/O or production decision side effects."""

    scene_probe: ShadowFusionProbe = field(default_factory=ShadowFusionProbe)

    def observe(
        self, frame: np.ndarray, sample_seconds: float, *,
        quality_status: str = "UNKNOWN",
        reference: ShadowReferenceLifecycle | None = None,
        observation_scope: str,
    ) -> dict:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            raise ValueError("Nonempty camera frame required")
        if not np.isfinite(sample_seconds) or sample_seconds <= 0:
            raise ValueError("Positive finite sampling interval required")
        if quality_status not in QUALITY_VALUES:
            raise ValueError("Camera quality status must be explicit and recognized")
        if not isinstance(observation_scope, str) or not observation_scope.strip():
            raise ValueError("Observation scope must be named")
        if reference is not None and not isinstance(
            reference, ShadowReferenceLifecycle
        ):
            raise ValueError("Reference must be a ShadowReferenceLifecycle")
        # Reject invalid requests before consuming any stateful scene samples.
        # The scene diagnostic runs for observation only. The lifecycle does
        # not auto-enroll, overwrite or reset its temporary image reference.
        scene = self.scene_probe.observe(frame, sample_seconds)
        axes = compose_camera_evidence_axes(
            quality={"quality_status": quality_status},
            scene=scene,
            reference=reference,
            observation_scope=observation_scope,
        )
        return {
            **axes,
            "scene_shadow": {
                "decision": scene["decision"],
                "review_cue": scene["review_cue"],
                "evidence_status": scene["evidence_status"],
                "global_quality_limited": scene["global_quality_limited"],
            },
            "reference_binding": "GOVERNANCE_ONLY_NOT_BOUND_TO_IMAGE_COMPARATOR",
            "production_integration": False,
        }
