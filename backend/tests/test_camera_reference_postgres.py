"""Real PostgreSQL integration tests on disposable CI database only.

Never mutate a live/prod schema. This suite runs only when CI explicitly
sets KAUSHALWATCH_TEST_DATABASE=isolated_ci and applies migration v3.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.services.officer_permissions import OfficerPrincipal
from app.services.protected_camera_reference import (
    CameraReferenceConflict, CameraReferencePolicyError,
    ProtectedCameraReferenceWorkflow,
)
from app.services.postgres_store import connection

pytestmark = pytest.mark.skipif(
    os.getenv("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci",
    reason="Requires disposable, explicitly opted-in PostgreSQL CI database",
)
CENTRE = "DEMO-KA-104"
OPERATOR = OfficerPrincipal("ci-ref-operator", "centre_reviewer", frozenset({CENTRE}))
REVIEWER = OfficerPrincipal("ci-ref-reviewer", "network_admin", frozenset())
VIEWER = OfficerPrincipal("ci-ref-viewer", "centre_viewer", frozenset({CENTRE}))
OTHER = OfficerPrincipal("ci-other-centre", "centre_reviewer", frozenset({"DEMO-KA-112"}))


def _camera() -> str:
    return "CAM-REF-" + uuid4().hex[:18]


def propose(store, camera):
    return store.propose(
        principal=OPERATOR, centre_id=CENTRE, camera_id=camera,
        reference_digest="a"*64, capture_id="ci-capture-1",
        source_review_id="ci-source-1", expected_revision=0,
    )


def test_postgres_proposal_review_and_suspension_roundtrip():
    camera = _camera()
    store = ProtectedCameraReferenceWorkflow()
    assert store.get(principal=VIEWER, centre_id=CENTRE, camera_id=camera)["state"] == "UNENROLLED"
    pending = propose(store, camera)
    assert pending["state"] == "PENDING_REVIEW"
    assert pending["production_binding"] is False
    assert pending["actual_reference_verified"] is False
    assert pending["proposed_by"] == OPERATOR.actor
    other_process = ProtectedCameraReferenceWorkflow()
    assert other_process.get(
        principal=VIEWER, centre_id=CENTRE, camera_id=camera
    )["revision"] == 1
    reviewed = other_process.review(
        principal=REVIEWER, centre_id=CENTRE, camera_id=camera,
        expected_revision=1, independent_review_id="ci-independent-2",
        verified_healthy=True, verified_same_view=True,
        compared_independently=True,
    )
    assert reviewed["state"] == "REVIEWED_NOT_BOUND"
    assert reviewed["reviewed_by"] == REVIEWER.actor
    assert reviewed["production_binding"] is False
    suspended = store.suspend(
        principal=REVIEWER, centre_id=CENTRE, camera_id=camera,
        expected_revision=1, reason="CI scenario suspension",
    )
    assert suspended["state"] == "SUSPENDED"
    updated = store.propose(
        principal=OPERATOR, centre_id=CENTRE, camera_id=camera,
        reference_digest="b"*64, capture_id="ci-capture-2",
        source_review_id="ci-source-2", expected_revision=1,
    )
    assert updated["state"] == "PENDING_REVIEW"
    assert updated["revision"] == 2
    assert updated["reviewed_by"] is None
    with connection() as db:
        events = db.execute(
            "SELECT action,sequence FROM kw_camera_reference_events "
            "WHERE centre_id=%s AND camera_id=%s ORDER BY sequence",
            (CENTRE,camera),
        ).fetchall()
    assert [row["action"] for row in events] == [
        "PROPOSE","REVIEW","SUSPEND","PROPOSE"
    ]
    assert [row["sequence"] for row in events] == [1,2,3,4]


def test_postgres_rejects_cross_centre_and_self_approval():
    camera = _camera()
    store = ProtectedCameraReferenceWorkflow()
    propose(store,camera)
    with pytest.raises(CameraReferencePolicyError):
        store.get(principal=OTHER,centre_id=CENTRE,camera_id=camera)
    with pytest.raises(CameraReferencePolicyError):
        store.propose(
            principal=VIEWER,centre_id=CENTRE,camera_id=camera,
            reference_digest="b"*64,capture_id="other",source_review_id="other",
            expected_revision=1,
        )
    with pytest.raises(CameraReferencePolicyError):
        store.review(
            principal=OPERATOR,centre_id=CENTRE,camera_id=camera,
            expected_revision=1,independent_review_id="self",
            verified_healthy=True,verified_same_view=True,compared_independently=True,
        )
    with pytest.raises(CameraReferencePolicyError):
        store.review(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
            expected_revision=1,independent_review_id="invalid",
            verified_healthy=False,verified_same_view=True,compared_independently=True,
        )


def test_postgres_stale_revisions_and_pending_cannot_be_overwritten():
    camera = _camera()
    store = ProtectedCameraReferenceWorkflow()
    propose(store,camera)
    with pytest.raises(CameraReferenceConflict):
        propose(store,camera)
    with pytest.raises(CameraReferenceConflict,match="Stale"):
        store.review(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
            expected_revision=2,independent_review_id="r2",
            verified_healthy=True,verified_same_view=True,compared_independently=True,
        )
    assert store.get(principal=VIEWER,centre_id=CENTRE,camera_id=camera)["revision"]==1


def test_postgres_audit_is_append_only_and_tampered_current_record_blocked():
    camera = _camera()
    store = ProtectedCameraReferenceWorkflow()
    propose(store,camera)
    with connection() as db:
        with pytest.raises(Exception,match="camera reference audit cannot be changed"):
            db.execute(
                "DELETE FROM kw_camera_reference_events "
                "WHERE centre_id=%s AND camera_id=%s", (CENTRE,camera),
            )
    # Current state edits are detected by verification, even if table owner
    # can bypass the domain and directly mutate the mutable proposal record.
    with connection() as db:
        db.execute(
            "UPDATE kw_camera_reference_proposals SET capture_id=%s "
            "WHERE centre_id=%s AND camera_id=%s",
            ("tampered",CENTRE,camera),
        )
    with pytest.raises(CameraReferenceConflict,match="audit"):
        store.get(principal=VIEWER,centre_id=CENTRE,camera_id=camera)
    with pytest.raises(CameraReferenceConflict,match="audit"):
        store.review(
            principal=REVIEWER,centre_id=CENTRE,camera_id=camera,
            expected_revision=1,independent_review_id="review-false",
            verified_healthy=True,verified_same_view=True,compared_independently=True,
        )
