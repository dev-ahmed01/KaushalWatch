"""Separate Camera Trust advisory axes. EXPERIMENTAL, NOT RELEASED.

The existing camera trust quality_status field is not evidence of a
camera's authenticity. Neither this adapter nor the shadow fusion can infer
that a training activity is verifiable, authorize reference renewal, or take
attendance/compliance action. No thresholds are modified here.
"""
from __future__ import annotations

from collections.abc import Mapping

from .camera_reference_lifecycle_shadow import ShadowReferenceLifecycle

QUALITY_VALUES = frozenset(("SUFFICIENT", "DEGRADED_VISIBILITY", "UNKNOWN"))
SCENE_VALUES = frozenset((
    "WARMUP", "SPATIAL_SCENE_REVIEW",
    "LOW_TEXTURE_GLOBAL_SCENE_REVIEW", "UNKNOWN_LOW_TEXTURE",
    "NO_SHADOW_REVIEW",
))


def compose_camera_evidence_axes(
    *, quality: Mapping[str, object],
    scene: Mapping[str, object],
    reference: ShadowReferenceLifecycle | None,
    observation_scope: str,
) -> dict:
    """Return 3 separate evidence axes, never a joint punitive verdict.

    Quality is a narrowed view of CameraTrust (quality_status only) or
    an independently reviewed quality assessment. CameraTrust.trusted and
    CameraTrust.tamper_suspected are purposely ignored.
    """
    if not isinstance(observation_scope, str) or not observation_scope.strip():
        raise ValueError("Observation scope must be named")
    if quality.get("quality_status") not in QUALITY_VALUES:
        raise ValueError("Camera quality status must be explicit and recognized")
    value = quality["quality_status"]
    if scene.get("decision") not in SCENE_VALUES:
        raise ValueError("Scene decision must be explicit and recognized")
    review = scene.get("review_cue")
    if type(review) is not bool:
        raise ValueError("Scene review cue must be boolean")
    if review != (scene["decision"] in (
        "SPATIAL_SCENE_REVIEW", "LOW_TEXTURE_GLOBAL_SCENE_REVIEW"
    )):
        raise ValueError("Scene decision and review cue disagree")
    if scene.get("production_integration") is not False:
        raise ValueError("Only isolated shadow scene signals are allowed")

    if reference is not None and not isinstance(reference, ShadowReferenceLifecycle):
        raise ValueError("Reference must be a ShadowReferenceLifecycle")
    status = reference.status if reference else "UNENROLLED"
    if status not in (
        "UNENROLLED", "PENDING_REVIEW", "APPROVED", "SUSPENDED", "REVOKED"
    ):
        raise ValueError("Unrecognized reference lifecycle status")

    if value == "DEGRADED_VISIBILITY":
        quality_hint = "DEGRADATION_INDICATED"
    elif value == "UNKNOWN":
        quality_hint = "UNKNOWN"
    else:
        quality_hint = "NO_DEGRADATION_SIGNAL"

    if scene["decision"] == "WARMUP":
        scene_hint = "WARMUP"
    elif scene["decision"] == "UNKNOWN_LOW_TEXTURE":
        scene_hint = "INSUFFICIENT_STRUCTURAL_EVIDENCE"
    elif review:
        scene_hint = "OFFICER_SCENE_REVIEW"
    else:
        scene_hint = "NO_SCENE_CHANGE_REVIEW_CUE"

    cues = []
    if status != "APPROVED":
        cues.append("REFERENCE_APPROVAL_REQUIRED")
    if quality_hint == "DEGRADATION_INDICATED":
        cues.append("CHECK_VISUAL_EVIDENCE")
    elif quality_hint == "UNKNOWN":
        cues.append("QUALITY_EVIDENCE_UNKNOWN")
    if scene_hint == "OFFICER_SCENE_REVIEW":
        cues.append("REVIEW_SCENE_CHANGE")
    elif scene_hint in ("WARMUP", "INSUFFICIENT_STRUCTURAL_EVIDENCE"):
        cues.append("SCENE_EVIDENCE_UNKNOWN")

    return {
        "status": "THREE_AXIS_CAMERA_ADVISORY_SHADOW_ONLY",
        "scope": observation_scope.strip(),
        "evidence_quality": {
            "indicator": quality_hint,
            "visual_activity_verification": "NOT_ESTABLISHED",
        },
        "scene_change": {
            "indicator": scene_hint,
            "underlying_decision": scene["decision"],
            "camera_movement_proven": False,
        },
        "reference": {
            "status": status,
            "approval_is_external_verification": False,
        },
        "human_review_cues": cues,
        "stream_freshness": "NOT_ASSESSED",
        "camera_integrity_verdict": "NOT_DETERMINED",
        "attendance_decision": "NOT_AUTHORIZED",
        "compliance_decision": "NOT_AUTHORIZED",
        "production_integration": False,
    }
