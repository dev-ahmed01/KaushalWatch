"""Shadow-only, three-axis advisory tests. No real CCTV or enforcement."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.camera_evidence_axes_shadow import compose_camera_evidence_axes
from app.services.camera_reference_lifecycle_shadow import ShadowReferenceLifecycle

TIME = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def scene(decision, review=False):
    return {
        "decision": decision,
        "review_cue": review,
        "production_integration": False,
    }


def axes(quality, s, ref=None):
    return compose_camera_evidence_axes(
        quality={"quality_status": quality},
        scene=s,
        reference=ref,
        observation_scope="Training evidence: verify instructor activity",
    )


def approved_reference():
    registry = ShadowReferenceLifecycle("camera-1")
    registry.propose(
        actor="operator-A", reference_sha256="0" * 64,
        capture_id="healthy-window-1", reviewed_source_id="source-1",
        event_time=TIME,
    )
    registry.approve(
        actor="officer-B", reference_review_id="proof-1",
        confirmed_healthy=True,
        confirmed_same_view=True,
        independent_reference_comparison=True,
        event_time=TIME + timedelta(minutes=1),
    )
    return registry


def test_quality_degradation_is_separate_from_scene_movement():
    result = axes("DEGRADED_VISIBILITY", scene("NO_SHADOW_REVIEW"))
    assert result["evidence_quality"]["indicator"] == "DEGRADATION_INDICATED"
    assert result["scene_change"]["indicator"] == "NO_SCENE_CHANGE_REVIEW_CUE"
    assert "CHECK_VISUAL_EVIDENCE" in result["human_review_cues"]
    assert "REFERENCE_APPROVAL_REQUIRED" in result["human_review_cues"]
    assert result["attendance_decision"] == "NOT_AUTHORIZED"


def test_scene_warning_does_not_prove_motion_or_unusable_evidence():
    result = axes(
        "SUFFICIENT", scene("SPATIAL_SCENE_REVIEW", review=True),
        approved_reference(),
    )
    assert result["scene_change"]["indicator"] == "OFFICER_SCENE_REVIEW"
    assert result["scene_change"]["camera_movement_proven"] is False
    assert result["evidence_quality"]["indicator"] == "NO_DEGRADATION_SIGNAL"
    assert result["evidence_quality"]["visual_activity_verification"] == "NOT_ESTABLISHED"
    assert result["reference"]["status"] == "APPROVED"
    assert result["reference"]["approval_is_external_verification"] is False
    assert result["compliance_decision"] == "NOT_AUTHORIZED"


def test_no_warning_and_good_quality_is_not_a_trusted_integrity_verdict():
    result = axes("SUFFICIENT", scene("NO_SHADOW_REVIEW"), approved_reference())
    assert result["human_review_cues"] == []
    assert result["stream_freshness"] == "NOT_ASSESSED"
    assert result["camera_integrity_verdict"] == "NOT_DETERMINED"
    assert result["evidence_quality"]["visual_activity_verification"] == "NOT_ESTABLISHED"
    assert result["production_integration"] is False


def test_missing_or_suspended_reference_stays_review_required():
    wf = approved_reference()
    wf.suspend(
        actor="officer-C", reason="View change reported",
        event_time=TIME + timedelta(minutes=2),
    )
    result = axes("SUFFICIENT", scene("NO_SHADOW_REVIEW"), wf)
    assert result["reference"]["status"] == "SUSPENDED"
    assert "REFERENCE_APPROVAL_REQUIRED" in result["human_review_cues"]


def test_low_texture_unknown_with_no_review_is_not_a_normal_scene():
    result = axes("UNKNOWN", scene("UNKNOWN_LOW_TEXTURE"))
    assert result["scene_change"]["indicator"] == "INSUFFICIENT_STRUCTURAL_EVIDENCE"
    assert "SCENE_EVIDENCE_UNKNOWN" in result["human_review_cues"]
    assert "QUALITY_EVIDENCE_UNKNOWN" in result["human_review_cues"]


@pytest.mark.parametrize("broken", [
    {"decision": "SPATIAL_SCENE_REVIEW", "review_cue": False, "production_integration": False},
    {"decision": "NO_SHADOW_REVIEW", "review_cue": True, "production_integration": False},
    {"decision": "WARMUP", "review_cue": "false", "production_integration": False},
    {"decision": "SCENE_MOVED_CONFIRMED", "review_cue": True, "production_integration": False},
    {"decision": "NO_SHADOW_REVIEW", "review_cue": False, "production_integration": True},
])
def test_inconsistent_or_production_scene_inputs_fail_closed(broken):
    with pytest.raises(ValueError):
        axes("SUFFICIENT", broken)


@pytest.mark.parametrize("bad_quality", [
    None, "TRUSTED", "USABLE", "NO_TAMPER_SIGNAL",
])
def test_quality_is_not_interchangeable_with_camera_integrity(bad_quality):
    with pytest.raises(ValueError):
        axes(bad_quality, scene("NO_SHADOW_REVIEW"))


def test_observation_scope_cannot_be_omitted():
    with pytest.raises(ValueError, match="scope"):
        compose_camera_evidence_axes(
            quality={"quality_status": "SUFFICIENT"},
            scene=scene("NO_SHADOW_REVIEW"),
            reference=None,
            observation_scope=" ",
        )
