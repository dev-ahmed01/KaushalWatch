"""Local synthetic-only reference registry and image binding verification."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.services.camera_reference_binding_shadow import (
    BoundReferenceShadowProbe, ReferenceBindingError, image_reference_digest,
)
from app.services.camera_reference_registry_shadow import (
    ReferencePolicyError, ShadowReferenceRegistry, TrustedActor,
)

START = datetime(2026, 10, 17, tzinfo=timezone.utc)
OPERATOR = TrustedActor("operator-1","camera_operator","centre-a")
REVIEWER = TrustedActor("officer-2","camera_reviewer","centre-a")
OTHER_CENTRE = TrustedActor("officer-2","camera_reviewer","centre-b")
WRONG_ROLE = TrustedActor("viewer-3","viewer","centre-a")


def fixture(tmp_path):
    store=ShadowReferenceRegistry(tmp_path / "reference.db")
    rng=np.random.default_rng(7)
    frame=rng.integers(80,170,(144,192,3),dtype=np.uint8)
    digest=image_reference_digest(frame)
    proposal=store.propose(
        actor=OPERATOR,camera_id="cam-1",sha256=digest,
        capture_id="local-capture-42",reviewed_source_id="source-ticket-42",
        at=START,
    )
    return store,frame,proposal


def approved(tmp_path):
    store,frame,proposal=fixture(tmp_path)
    result=store.approve(
        actor=REVIEWER,camera_id="cam-1",
        review_id="independent-review-2026",expected_revision=1,
        confirmed_healthy=True,confirmed_same_view=True,
        independent_comparison=True,at=START+timedelta(seconds=2),
    )
    return store,frame,result


def test_durable_reference_survives_registry_restart(tmp_path):
    store,frame,pending=fixture(tmp_path)
    assert pending["status"]=="PENDING_REVIEW"
    persisted=ShadowReferenceRegistry(store.path)
    assert persisted.snapshot(
        centre_id="centre-a",camera_id="cam-1",actor=OPERATOR
    )["sha256"]==image_reference_digest(frame)
    assert persisted.verify_audit_chain(
        centre_id="centre-a",camera_id="cam-1",actor=OPERATOR
    )
    approved=persisted.approve(
        actor=REVIEWER,camera_id="cam-1",review_id="review-2",
        expected_revision=1,confirmed_healthy=True,
        confirmed_same_view=True,independent_comparison=True,
        at=START+timedelta(seconds=1),
    )
    assert approved["status"]=="APPROVED"
    assert approved["approver"]=="officer-2"
    assert ShadowReferenceRegistry(store.path).snapshot(
        centre_id="centre-a",camera_id="cam-1",actor=OPERATOR
    )["status"]=="APPROVED"


def test_scoped_access_and_different_actor_approval(tmp_path):
    store,frame,_=fixture(tmp_path)
    with pytest.raises(ReferencePolicyError, match="permission"):
        store.snapshot(centre_id="centre-a",camera_id="cam-1",actor=OTHER_CENTRE)
    with pytest.raises(ReferencePolicyError, match="Unsupported"):
        store.snapshot(centre_id="centre-a",camera_id="cam-1",actor=WRONG_ROLE)
    with pytest.raises(ReferencePolicyError, match="permission"):
        store.approve(
            actor=OPERATOR,camera_id="cam-1",review_id="2",
            expected_revision=1,confirmed_healthy=True,
            confirmed_same_view=True,independent_comparison=True,
        )
    self_reviewer=TrustedActor("operator-1","camera_reviewer","centre-a")
    with pytest.raises(ReferencePolicyError, match="Independent"):
        store.approve(
            actor=self_reviewer,camera_id="cam-1",review_id="2",
            expected_revision=1,confirmed_healthy=True,
            confirmed_same_view=True,independent_comparison=True,
            at=START+timedelta(seconds=2),
        )
    assert store.snapshot(
        centre_id="centre-a",camera_id="cam-1",actor=OPERATOR
    )["status"]=="PENDING_REVIEW"


@pytest.mark.parametrize("evidence",[
    (1,True,True),(True,False,True),(True,True,False)
])
def test_approval_requires_three_explicit_positive_checks(tmp_path,evidence):
    store,_,_=fixture(tmp_path)
    with pytest.raises(ReferencePolicyError,match="positive evidence"):
        store.approve(
            actor=REVIEWER,camera_id="cam-1",review_id="review-2",
            expected_revision=1,confirmed_healthy=evidence[0],
            confirmed_same_view=evidence[1],
            independent_comparison=evidence[2],
            at=START+timedelta(seconds=2),
        )


def test_stale_revision_cannot_approve_or_modify(tmp_path):
    store,frame,_=fixture(tmp_path)
    with pytest.raises(ReferencePolicyError,match="Stale"):
        store.approve(
            actor=REVIEWER,camera_id="cam-1",review_id="review-2",
            expected_revision=2,confirmed_healthy=True,
            confirmed_same_view=True,independent_comparison=True,
            at=START+timedelta(seconds=1),
        )
    with pytest.raises(ReferencePolicyError,match="approved"):
        store.transition(
            actor=REVIEWER,camera_id="cam-1",action="SUSPEND",
            reason="inspect",expected_revision=1,at=START+timedelta(seconds=2),
        )


def test_fingerprint_binding_requires_exact_reviewed_pixels(tmp_path):
    store,frame,_=approved(tmp_path)
    altered=frame.copy()
    altered[0,0,0]^=1
    with pytest.raises(ReferenceBindingError,match="Image bytes"):
        BoundReferenceShadowProbe.bind(
            registry=store,reader=REVIEWER,camera_id="cam-1",
            reference_frame=altered,
        )
    binder=BoundReferenceShadowProbe.bind(
        registry=store,reader=OPERATOR,camera_id="cam-1",
        reference_frame=frame,
    )
    assert binder.scene.spatial.temporary_reference is not None
    assert binder.scene.persistent.temporary_reference is not None
    assert binder.scene.spatial.elapsed==0
    first=binder.observe(frame,1)
    assert first["reference_binding"]=="APPROVED_IMAGE_DIGEST_MATCHED"
    assert first["evidence_status"]=="SUFFICIENT_TILES"
    assert first["camera_integrity_verdict"]=="NOT_DETERMINED"
    assert first["production_integration"] is False


def test_bound_reference_fails_closed_after_suspension(tmp_path):
    store,frame,_=approved(tmp_path)
    binder=BoundReferenceShadowProbe.bind(
        registry=store,reader=OPERATOR,camera_id="cam-1",
        reference_frame=frame,
    )
    store.transition(
        actor=REVIEWER,camera_id="cam-1",action="SUSPEND",
        reason="manual investigation",expected_revision=1,
        at=START+timedelta(seconds=3),
    )
    with pytest.raises(ReferenceBindingError,match="stop shadow"):
        binder.observe(frame,1)
    with pytest.raises(ReferenceBindingError,match="not been independently approved"):
        BoundReferenceShadowProbe.bind(
            registry=store,reader=OPERATOR,camera_id="cam-1",
            reference_frame=frame,
        )
    assert store.verify_audit_chain(
        centre_id="centre-a",camera_id="cam-1",actor=REVIEWER
    )


def test_approved_reference_cannot_be_silently_replaced(tmp_path):
    store,frame,_=approved(tmp_path)
    with pytest.raises(ReferencePolicyError,match="must be suspended"):
        store.propose(
            actor=OPERATOR,camera_id="cam-1",sha256=image_reference_digest(frame),
            capture_id="secret-reset",reviewed_source_id="automatic-reset",
            at=START+timedelta(seconds=4),
        )
    assert store.snapshot(
        centre_id="centre-a",camera_id="cam-1",actor=REVIEWER
    )["capture_id"]=="local-capture-42"


def test_shadow_audit_is_append_only_under_sqlite_trigger(tmp_path):
    store,_,_=approved(tmp_path)
    with sqlite3.connect(store.path) as conn:
        with pytest.raises(sqlite3.DatabaseError,match="append-only"):
            conn.execute(
                "DELETE FROM reference_audit WHERE centre_id='centre-a'"
            )
    assert store.verify_audit_chain(
        centre_id="centre-a",camera_id="cam-1",actor=REVIEWER
    )


def test_reference_digests_include_shape_and_pixels():
    frame=np.zeros((144,192,3),dtype=np.uint8)
    same=frame.copy()
    assert image_reference_digest(frame)==image_reference_digest(same)
    frame[1,1,1]=10
    assert image_reference_digest(frame)!=image_reference_digest(same)
    with pytest.raises(ReferenceBindingError,match="uint8"):
        image_reference_digest(np.zeros((144,192,3),dtype=np.float32))


def test_reviewer_cannot_approve_preexisting_unapproved_empty_db(tmp_path):
    store=ShadowReferenceRegistry(tmp_path/"fresh.db")
    with pytest.raises(ReferencePolicyError,match="No pending"):
        store.approve(
            actor=REVIEWER,camera_id="cam-1",review_id="r",
            confirmed_healthy=True,confirmed_same_view=True,
            independent_comparison=True,expected_revision=1,
        )



def test_metadata_tampering_detected_and_bound_observation_blocked(tmp_path):
    store, frame, _ = approved(tmp_path)
    binder = BoundReferenceShadowProbe.bind(
        registry=store, reader=REVIEWER, camera_id="cam-1",
        reference_frame=frame,
    )
    # Tamper with mutable state outside approved transactional domain API.
    with sqlite3.connect(store.path) as db:
        db.execute(
            "UPDATE reference_proposals SET capture_id='forged-capture' "
            "WHERE centre_id='centre-a' AND camera_id='cam-1'"
        )
    assert not store.verify_audit_chain(
        centre_id="centre-a", camera_id="cam-1", actor=REVIEWER
    )
    with pytest.raises(ReferenceBindingError, match="audit chain"):
        binder.observe(frame, 1)
    with pytest.raises(ReferenceBindingError, match="audit chain"):
        BoundReferenceShadowProbe.bind(
            registry=store, reader=REVIEWER, camera_id="cam-1",
            reference_frame=frame,
        )


def test_metadata_status_change_without_audit_never_binds(tmp_path):
    store, frame, _ = fixture(tmp_path)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "UPDATE reference_proposals SET status='APPROVED' "
            "WHERE centre_id='centre-a' AND camera_id='cam-1'"
        )
    assert not store.verify_audit_chain(
        centre_id="centre-a", camera_id="cam-1", actor=REVIEWER
    )
    with pytest.raises(ReferenceBindingError, match="audit chain"):
        BoundReferenceShadowProbe.bind(
            registry=store, reader=REVIEWER, camera_id="cam-1",
            reference_frame=frame,
        )
