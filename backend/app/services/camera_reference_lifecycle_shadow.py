"""Shadow-only manual camera-reference lifecycle. NOT a production approval API.

Models explicit human proposals, independent approval, suspension and revocation.
Stores only reference fingerprints and numerical provenance, never CCTV frames.
Caller identity, authorization, secure logging and reference source verification
must be implemented and audited separately before operational use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ReferenceTransitionError(ValueError):
    """An unsafe or unsupported experimental reference transition."""


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReferenceTransitionError(f"{name} is required")
    return value.strip()


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceTransitionError("Explicit timezone-aware event time is required")
    if value.utcoffset() is None:
        raise ReferenceTransitionError("Event timezone must have a valid offset")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ReferenceEvent:
    sequence: int
    action: str
    actor: str
    event_time: datetime
    reference_sha256: str | None
    rationale: str


@dataclass
class ShadowReferenceLifecycle:
    """An in-memory single-camera reference workflow; no automatic enrollment."""

    camera_id: str
    status: str = "UNENROLLED"
    reference_sha256: str | None = None
    capture_id: str | None = None
    proposal_by: str | None = None
    approved_by: str | None = None
    approved_review_id: str | None = None
    last_transition_at: datetime | None = None
    events: list[ReferenceEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.camera_id = _text(self.camera_id, "camera_id")
        if self.status != "UNENROLLED" or any((
            self.reference_sha256, self.capture_id, self.proposal_by,
            self.approved_by, self.approved_review_id, self.last_transition_at,
            self.events,
        )):
            raise ReferenceTransitionError(
                "Reference lifecycle must start UNENROLLED; no preset approvals"
            )

    def _stamp(self, event_time: datetime) -> datetime:
        stamp = _utc(event_time)
        if self.last_transition_at is not None and stamp <= self.last_transition_at:
            raise ReferenceTransitionError("Event timestamps must be increasing")
        return stamp

    def _record(
        self, action: str, actor: str, stamp: datetime, reason: str
    ) -> None:
        self.events.append(ReferenceEvent(
            sequence=len(self.events) + 1,
            action=action,
            actor=actor,
            event_time=stamp,
            reference_sha256=self.reference_sha256,
            rationale=reason,
        ))
        self.last_transition_at = stamp

    def propose(
        self, *, actor: str, reference_sha256: str, capture_id: str,
        reviewed_source_id: str, event_time: datetime,
    ) -> None:
        actor = _text(actor, "proposer")
        capture_id = _text(capture_id, "capture_id")
        reviewed_source_id = _text(reviewed_source_id, "reviewed_source_id")
        if not isinstance(reference_sha256, str) or not _SHA256.fullmatch(reference_sha256):
            raise ReferenceTransitionError("Lowercase reference SHA-256 required")
        if self.status not in ("UNENROLLED", "SUSPENDED", "REVOKED"):
            raise ReferenceTransitionError(
                "Active or pending reference cannot be replaced or auto-reset"
            )
        stamp = self._stamp(event_time)
        self.reference_sha256 = reference_sha256
        self.capture_id = capture_id
        self.proposal_by = actor
        self.approved_by = None
        self.approved_review_id = None
        self.status = "PENDING_REVIEW"
        self._record("PROPOSE", actor, stamp, f"source_review_id:{reviewed_source_id}")

    def approve(
        self, *, actor: str, reference_review_id: str,
        confirmed_healthy: bool, confirmed_same_view: bool,
        independent_reference_comparison: bool, event_time: datetime,
    ) -> None:
        actor = _text(actor, "approver")
        review_id = _text(reference_review_id, "reference_review_id")
        if self.status != "PENDING_REVIEW":
            raise ReferenceTransitionError("Only a proposed reference can be approved")
        if actor == self.proposal_by:
            raise ReferenceTransitionError(
                "Independent approver must differ from proposer"
            )
        if any(type(v) is not bool for v in (
            confirmed_healthy, confirmed_same_view,
            independent_reference_comparison,
        )):
            raise ReferenceTransitionError("Independent verification flags must be booleans")
        if not all((
            confirmed_healthy, confirmed_same_view,
            independent_reference_comparison,
        )):
            raise ReferenceTransitionError(
                "Unverified healthy view and independent comparison cannot be approved"
            )
        stamp = self._stamp(event_time)
        self.status = "APPROVED"
        self.approved_by = actor
        self.approved_review_id = review_id
        self._record("APPROVE", actor, stamp, f"comparison_review_id:{review_id}")

    def suspend(
        self, *, actor: str, reason: str, event_time: datetime
    ) -> None:
        actor = _text(actor, "reviewer")
        reason = _text(reason, "reason")
        if self.status != "APPROVED":
            raise ReferenceTransitionError("Only an approved reference can be suspended")
        stamp = self._stamp(event_time)
        self.status = "SUSPENDED"
        self._record("SUSPEND", actor, stamp, reason)

    def revoke(
        self, *, actor: str, reason: str, event_time: datetime
    ) -> None:
        actor = _text(actor, "reviewer")
        reason = _text(reason, "reason")
        if self.status not in ("PENDING_REVIEW", "APPROVED", "SUSPENDED"):
            raise ReferenceTransitionError("No revocable reference")
        stamp = self._stamp(event_time)
        self.status = "REVOKED"
        self._record("REVOKE", actor, stamp, reason)

    def public_snapshot(self) -> dict:
        """Diagnostic metadata only, not proof of identity/authorization."""
        return {
            "camera_id": self.camera_id,
            "reference_status": self.status,
            "reference_sha256": self.reference_sha256,
            "capture_id": self.capture_id,
            "proposal_by": self.proposal_by,
            "approved_by": self.approved_by,
            "approved_review_id": self.approved_review_id,
            "transition_count": len(self.events),
            "last_transition_at": (
                self.last_transition_at.isoformat()
                if self.last_transition_at else None
            ),
            "production_integration": False,
            "external_identity_verified": False,
            "actual_reference_content_verified": False,
        }
