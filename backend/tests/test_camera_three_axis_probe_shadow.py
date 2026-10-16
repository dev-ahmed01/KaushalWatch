"""Synthetic frames exercise the full three-axis shadow adapter."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.services.camera_reference_lifecycle_shadow import ShadowReferenceLifecycle
from app.services.camera_three_axis_probe_shadow import ThreeAxisCameraShadowProbe

START = datetime(2026, 10, 17, tzinfo=timezone.utc)


def build_registry():
    reference = ShadowReferenceLifecycle("synthetic-camera-A")
    reference.propose(
        actor="human-operator", reference_sha256="1" * 64,
        capture_id="capture-id-1", reviewed_source_id="source-review-A",
        event_time=START,
    )
    return reference


def test_three_axis_probe_does_not_autoapprove_or_conclude_integrity():
    checker = ThreeAxisCameraShadowProbe()
    frame = np.full((80, 80, 3), 50, dtype=np.uint8)
    reference = build_registry()
    first = checker.observe(
        frame, 1 / 3, reference=reference,
        observation_scope="Evidence of training activity",
    )
    assert first["scene_shadow"]["decision"] == "WARMUP"
    assert first["reference"]["status"] == "PENDING_REVIEW"
    assert first["reference_binding"] == "GOVERNANCE_ONLY_NOT_BOUND_TO_IMAGE_COMPARATOR"
    for _ in range(90):
        result = checker.observe(
            frame, 1 / 3, reference=reference,
            observation_scope="Evidence of training activity",
        )
    assert result["scene_shadow"]["evidence_status"] == "UNKNOWN_LOW_TEXTURE"
    assert result["evidence_quality"]["indicator"] == "UNKNOWN"
    assert result["camera_integrity_verdict"] == "NOT_DETERMINED"
    assert result["attendance_decision"] == "NOT_AUTHORIZED"
    assert reference.status == "PENDING_REVIEW"
    assert len(reference.events) == 1


def test_quality_signal_does_not_claim_camera_shift():
    checker = ThreeAxisCameraShadowProbe()
    dark = np.full((64, 64, 3), 2, dtype=np.uint8)
    value = checker.observe(
        dark, 1, quality_status="DEGRADED_VISIBILITY",
        observation_scope="Person count",
    )
    assert value["evidence_quality"]["indicator"] == "DEGRADATION_INDICATED"
    assert value["scene_change"]["camera_movement_proven"] is False
    assert value["compliance_decision"] == "NOT_AUTHORIZED"


def test_reference_approval_only_affects_governance_axis():
    checker = ThreeAxisCameraShadowProbe()
    frame = np.full((80, 80, 3), 70, dtype=np.uint8)
    ref = build_registry()
    ref.approve(
        actor="independent-reviewer", reference_review_id="review-2",
        confirmed_healthy=True, confirmed_same_view=True,
        independent_reference_comparison=True,
        event_time=START + timedelta(minutes=1),
    )
    output = checker.observe(
        frame, 1, quality_status="SUFFICIENT",
        reference=ref, observation_scope="Evidence clarity",
    )
    assert output["reference"]["status"] == "APPROVED"
    assert output["stream_freshness"] == "NOT_ASSESSED"
    assert output["reference_binding"] == "GOVERNANCE_ONLY_NOT_BOUND_TO_IMAGE_COMPARATOR"
    assert output["scene_shadow"]["decision"] == "WARMUP"


@pytest.mark.parametrize("bad_time", [float("nan"), 0, -2])
def test_invalid_sample_intervals_fail(bad_time):
    checker = ThreeAxisCameraShadowProbe()
    with pytest.raises(ValueError, match="Positive finite"):
        checker.observe(
            np.ones((40, 40, 3), dtype=np.uint8), bad_time,
            observation_scope="Person count",
        )


def test_never_accept_deceptive_quality_labels():
    checker = ThreeAxisCameraShadowProbe()
    with pytest.raises(ValueError, match="quality status"):
        checker.observe(
            np.ones((40, 40, 3), dtype=np.uint8), 1,
            quality_status="TRUSTED", observation_scope="Person count",
        )
