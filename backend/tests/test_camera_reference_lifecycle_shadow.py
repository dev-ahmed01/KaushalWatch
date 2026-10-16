"""Synthetic-only tests of manual reference approval workflow boundaries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.camera_reference_lifecycle_shadow import (
    ReferenceTransitionError, ShadowReferenceLifecycle,
)

START = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def proposed() -> ShadowReferenceLifecycle:
    workflow = ShadowReferenceLifecycle("camera-b")
    workflow.propose(
        actor="operator-1", reference_sha256=HASH_A,
        capture_id="manual-capture-A", reviewed_source_id="source-ticket-1",
        event_time=START,
    )
    return workflow


def approve(workflow, seconds=20):
    workflow.approve(
        actor="reviewer-2", reference_review_id="independent-review-1",
        confirmed_healthy=True, confirmed_same_view=True,
        independent_reference_comparison=True,
        event_time=START + timedelta(seconds=seconds),
    )


def test_new_camera_is_unenrolled_and_never_automatically_approved():
    workflow = ShadowReferenceLifecycle("camera-b")
    assert workflow.status == "UNENROLLED"
    assert workflow.public_snapshot()["production_integration"] is False
    assert workflow.public_snapshot()["actual_reference_content_verified"] is False
    with pytest.raises(ReferenceTransitionError, match="Only a proposed"):
        approve(workflow)


def test_manual_propose_independent_approve_then_suspend_and_repropose():
    workflow = proposed()
    assert workflow.status == "PENDING_REVIEW"
    assert workflow.approved_by is None
    approve(workflow)
    assert workflow.status == "APPROVED"
    with pytest.raises(ReferenceTransitionError, match="cannot be replaced"):
        workflow.propose(
            actor="operator-1", reference_sha256=HASH_B,
            capture_id="capture-B", reviewed_source_id="review-B",
            event_time=START + timedelta(seconds=25),
        )
    workflow.suspend(
        actor="reviewer-3", reason="Scene mismatch under inspection",
        event_time=START + timedelta(seconds=30),
    )
    assert workflow.status == "SUSPENDED"
    workflow.propose(
        actor="operator-4", reference_sha256=HASH_B,
        capture_id="capture-B", reviewed_source_id="review-B",
        event_time=START + timedelta(seconds=40),
    )
    assert workflow.status == "PENDING_REVIEW"
    assert workflow.approved_by is None
    assert [e.action for e in workflow.events] == [
        "PROPOSE", "APPROVE", "SUSPEND", "PROPOSE"
    ]
    assert [e.sequence for e in workflow.events] == [1, 2, 3, 4]


def test_same_proposer_cannot_approve():
    workflow = proposed()
    with pytest.raises(ReferenceTransitionError, match="Independent approver"):
        workflow.approve(
            actor="operator-1", reference_review_id="review-2",
            confirmed_healthy=True, confirmed_same_view=True,
            independent_reference_comparison=True,
            event_time=START + timedelta(seconds=5),
        )
    assert workflow.status == "PENDING_REVIEW"


@pytest.mark.parametrize("checks", [
    (False, True, True), (True, False, True),
    (True, True, False), (1, True, True),
])
def test_unverified_or_nonboolean_approval_is_rejected(checks):
    workflow = proposed()
    with pytest.raises(ReferenceTransitionError):
        workflow.approve(
            actor="reviewer-2", reference_review_id="review-1",
            confirmed_healthy=checks[0],
            confirmed_same_view=checks[1],
            independent_reference_comparison=checks[2],
            event_time=START + timedelta(seconds=3),
        )
    assert workflow.status == "PENDING_REVIEW"
    assert len(workflow.events) == 1


def test_timestamps_must_be_ordered_and_aware():
    workflow = proposed()
    with pytest.raises(ReferenceTransitionError, match="increasing"):
        workflow.revoke(
            actor="reviewer-2", reason="bad recording",
            event_time=START,
        )
    with pytest.raises(ReferenceTransitionError, match="timezone-aware"):
        workflow.revoke(
            actor="reviewer-2", reason="bad recording",
            event_time=datetime(2026, 10, 17, 12, 1),
        )
    assert workflow.status == "PENDING_REVIEW"


def test_revoke_cannot_be_undone_without_new_proposal_and_approval():
    workflow = proposed()
    approve(workflow)
    workflow.revoke(
        actor="reviewer-3", reason="no verified provenance",
        event_time=START + timedelta(seconds=40),
    )
    assert workflow.status == "REVOKED"
    with pytest.raises(ReferenceTransitionError, match="Only a proposed"):
        approve(workflow, seconds=50)
    workflow.propose(
        actor="operator-5", reference_sha256=HASH_B,
        capture_id="new-capture", reviewed_source_id="new-review",
        event_time=START + timedelta(seconds=60),
    )
    assert workflow.status == "PENDING_REVIEW"


@pytest.mark.parametrize("bad", [
    "", "f" * 63, "g" * 64, "ABCDEF" * 10 + "0000",
])
def test_invalid_fingerprints_never_registered(bad):
    wf = ShadowReferenceLifecycle("camera-b")
    with pytest.raises(ReferenceTransitionError, match="SHA-256"):
        wf.propose(
            actor="operator", reference_sha256=bad,
            capture_id="capture", reviewed_source_id="local-review",
            event_time=START,
        )
    assert wf.status == "UNENROLLED"


def test_constructor_rejects_presets_that_bypass_human_approval():
    with pytest.raises(ReferenceTransitionError, match="start UNENROLLED"):
        ShadowReferenceLifecycle("camera-b", status="APPROVED", reference_sha256=HASH_A)
