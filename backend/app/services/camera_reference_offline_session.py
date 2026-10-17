"""Explicit, private-reference-bound OFFLINE shadow session.

Never imported by live CameraTrust, case creation, attendance, or compliance.
This is a staging-only trusted-worker library, not a public endpoint.
The caller MUST be an already authenticated, server-resolved officer principal;
constructing a Principal from command-line user text is NOT authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from app.services.camera_reference_artifacts import (
    pixel_digest, verified_reference_frame, artifact_status,
)
from app.services.protected_camera_reference import (
    ProtectedCameraReferenceWorkflow, CameraReferenceConflict,
    CameraReferencePolicyError, required,
)
from app.services.officer_permissions import OfficerPrincipal
from app.services.camera_shadow_fusion import ShadowFusionProbe
from app.services.camera_spatial_scene_shadow import SpatialSceneShadow, _small
from app.services.camera_persistent_scene_probe import PersistentSceneProbe, _gray_small


@dataclass
class OfflineApprovedReferenceSession:
    """Finite offline observation session, fixed approved source pixels.

    This binds to private artifact bytes, not a runtime camera stream.
    Every observation checks the current review metadata and audit history,
    with no background updates, automatic recovery or reference replacement.
    """

    principal: OfficerPrincipal
    centre_id: str
    camera_id: str
    revision: int
    reference_digest: str
    review_id: str
    probe: ShadowFusionProbe
    samples: int = 0
    closed: bool = False

    @classmethod
    def open(
        cls, *, principal: OfficerPrincipal,
        centre_id: str, camera_id: str, revision: int,
    ) -> "OfflineApprovedReferenceSession":
        if not isinstance(principal, OfficerPrincipal) or principal.role != "network_admin":
            raise CameraReferencePolicyError("An authenticated network administrator is required")
        centre_id, camera_id = required(centre_id, "centre"), required(camera_id, "camera")
        if not principal.can_access(centre_id) or type(revision) is not int or revision <= 0:
            raise CameraReferencePolicyError("Invalid centre or reference revision")
        workflow = ProtectedCameraReferenceWorkflow()
        current = workflow.get(
            principal=principal, centre_id=centre_id, camera_id=camera_id
        )
        if (current["state"] != "REVIEWED_NOT_BOUND"
                or current["revision"] != revision
                or not current.get("artifact_attached")
                or not current.get("reviewed_by")
                or not current.get("independent_review_id")):
            raise CameraReferenceConflict("Independently reviewed private reference required")
        reference, _ = verified_reference_frame(
            principal=principal, centre_id=centre_id, camera_id=camera_id,
            expected_revision=revision, require_reviewed=True,
        )
        digest = pixel_digest(reference)
        if digest != current["reference_digest"]:
            raise CameraReferenceConflict("Approved image and proposal digest mismatch")
        spatial = SpatialSceneShadow()
        persistent = PersistentSceneProbe()
        # Set both comparators EXPLICITLY. The offline session never learns
        # a reference from an arbitrary first frame or performs auto-reset.
        spatial.temporary_reference = _small(reference).copy()
        persistent.temporary_reference = _gray_small(reference).copy()
        spatial.warmup.clear()
        persistent.initial_frames.clear()
        return cls(
            principal=principal, centre_id=centre_id, camera_id=camera_id,
            revision=revision, reference_digest=digest,
            review_id=current["independent_review_id"],
            probe=ShadowFusionProbe(spatial=spatial, persistent=persistent),
        )

    def observe(self, frame: np.ndarray, sample_seconds: float) -> dict:
        if self.closed:
            raise CameraReferenceConflict("Offline reference session has been closed")
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3
                or frame.shape[2] != 3 or frame.dtype != np.uint8
                or frame.size == 0):
            raise CameraReferencePolicyError("Decoded BGR frame required")
        if (not isinstance(sample_seconds, (float, int))
                or isinstance(sample_seconds, bool) or
                not math.isfinite(sample_seconds) or sample_seconds <= 0):
            raise CameraReferencePolicyError("Positive finite sample interval required")
        # Check after frame validation and BEFORE modifying probe state.
        current = ProtectedCameraReferenceWorkflow().get(
            principal=self.principal, centre_id=self.centre_id,
            camera_id=self.camera_id,
        )
        if (current["state"] != "REVIEWED_NOT_BOUND"
                or current["revision"] != self.revision
                or current["reference_digest"] != self.reference_digest
                or current.get("independent_review_id") != self.review_id
                or not current.get("artifact_attached")):
            self.closed = True
            raise CameraReferenceConflict(
                "Reference revoked, changed or audit invalid: offline session closed"
            )
        result = self.probe.observe(frame, float(sample_seconds))
        if result["decision"] == "WARMUP":
            self.closed = True
            raise CameraReferenceConflict("Unapproved video warmup was attempted")
        self.samples += 1
        return {
            **result,
            "status": "OFFLINE_FIXED_APPROVED_REFERENCE_SHADOW_ONLY",
            "reference_revision": self.revision,
            "reference_sha256": self.reference_digest,
            "samples_processed": self.samples,
            "camera_movement_proven": False,
            "reference_provenance_independently_verified": False,
            "production_integration": False,
            "attendance_action": "NOT_AUTHORIZED",
            "compliance_action": "NOT_AUTHORIZED",
        }

    def close(self) -> None:
        self.closed = True
