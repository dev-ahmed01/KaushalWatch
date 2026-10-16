"""Bind a human-reviewed reference fingerprint to scene probes, shadow only.

This is not an enrolled production camera: the caller must already know
the verified full-resolution pixels (from a separately controlled local
reference store). The registry does not store images, prove the provenance
of a digest, or authenticate the caller. No automatic re-baselining occurs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from .camera_persistent_scene_probe import PersistentSceneProbe, _gray_small
from .camera_reference_registry_shadow import (
    ReferencePolicyError, ShadowReferenceRegistry, TrustedActor,
)
from .camera_shadow_fusion import ShadowFusionProbe
from .camera_spatial_scene_shadow import SpatialSceneShadow, _small


class ReferenceBindingError(ReferencePolicyError):
    pass


def image_reference_digest(frame: np.ndarray) -> str:
    """Canonical fingerprint of pixel contents, dimensions and dtype.

    This is NOT a JPEG/file checksum; exact same pixel array is required.
    """
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
            frame.ndim not in (2, 3) or frame.size == 0 or
            (frame.ndim == 3 and frame.shape[2] != 3)):
        raise ReferenceBindingError("Reference must be nonempty uint8 grayscale/BGR pixels")
    packed = np.ascontiguousarray(frame)
    metadata = json.dumps(
        {"shape":list(packed.shape),"dtype":str(packed.dtype)},
        sort_keys=True, separators=(",",":"),
    ).encode("ascii")
    return hashlib.sha256(
        len(metadata).to_bytes(4,"big") + metadata + packed.tobytes()
    ).hexdigest()


@dataclass
class BoundReferenceShadowProbe:
    """Per-session fixed-reference detector with no implicit warmup/reset."""

    registry: ShadowReferenceRegistry
    reader: TrustedActor
    camera_id: str
    reference_digest: str
    approved_revision: int
    scene: ShadowFusionProbe

    @classmethod
    def bind(
        cls, *, registry: ShadowReferenceRegistry, reader: TrustedActor,
        camera_id: str, reference_frame: np.ndarray,
    ) -> "BoundReferenceShadowProbe":
        if not isinstance(registry, ShadowReferenceRegistry):
            raise ReferenceBindingError("Registry required")
        if not isinstance(reader, TrustedActor):
            raise ReferenceBindingError("Trusted reader required")
        # Read access is separately scoped to the camera centre.
        snapshot = registry.snapshot(
            centre_id=reader.centre_id,camera_id=camera_id,actor=reader,
        )
        if snapshot["status"] != "APPROVED":
            raise ReferenceBindingError("Reference has not been independently approved")
        if not registry.verify_audit_chain(
            centre_id=reader.centre_id,camera_id=camera_id,
            actor=reader if reader.role=="camera_reviewer" else
            TrustedActor(reader.subject,"camera_reviewer",reader.centre_id),
        ):
            raise ReferenceBindingError("Reference audit chain does not verify")
        expected = snapshot["sha256"]
        actual = image_reference_digest(reference_frame)
        if expected != actual:
            raise ReferenceBindingError("Image bytes do not match approved reference fingerprint")

        # Fixed reference selected by explicit bind, not by recording warmup.
        spatial = SpatialSceneShadow()
        global_scene = PersistentSceneProbe()
        spatial.temporary_reference = _small(reference_frame).copy()
        global_scene.temporary_reference = _gray_small(reference_frame).copy()
        spatial.elapsed = 0.0
        global_scene.elapsed = 0.0
        return cls(
            registry=registry,reader=reader,camera_id=camera_id,
            reference_digest=expected,approved_revision=snapshot["revision"],
            scene=ShadowFusionProbe(spatial=spatial,persistent=global_scene),
        )

    def observe(self, frame: np.ndarray, sample_seconds: float) -> dict:
        # No process can silently reuse a suspended/revoked/replaced reference.
        current = self.registry.snapshot(
            centre_id=self.reader.centre_id,camera_id=self.camera_id,
            actor=self.reader,
        )
        if (current["status"] != "APPROVED" or
                current["revision"] != self.approved_revision or
                current["sha256"] != self.reference_digest):
            raise ReferenceBindingError(
                "Approved reference changed: stop shadow observations and seek human review"
            )
        result = self.scene.observe(frame,sample_seconds)
        return {
            **result,
            "reference_binding": "APPROVED_IMAGE_DIGEST_MATCHED",
            "bound_reference_sha256": self.reference_digest,
            "bound_reference_revision": self.approved_revision,
            "production_integration": False,
            "camera_integrity_verdict": "NOT_DETERMINED",
        }
