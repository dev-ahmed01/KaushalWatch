from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class CaseStatus(str, Enum):
    open = "open"
    under_review = "under_review"
    confirmed = "confirmed"
    false_positive = "false_positive"
    virtual_verification = "virtual_verification"
    resolved = "resolved"


class CameraTrust(BaseModel):
    trusted: bool
    score: float = Field(ge=0, le=100)
    is_frozen: bool = False
    is_blurry: bool = False
    is_too_dark: bool = False
    scene_shift: bool = False
    reasons: list[str] = Field(default_factory=list)


class AttendanceObservation(BaseModel):
    second: float
    raw_count: int
    tracker_count: int | None = None
    candidate_count: int | None = None
    confirmed_count: int | None = None
    registered_count: int | None = None
    smoothed_count: int
    camera_trust: float


class EvidenceRecord(BaseModel):
    evidence_id: str
    created_at: str
    frame_path: str
    sha256: str
    perceptual_hash: str
    duplicate_of: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceCase(BaseModel):
    case_id: str
    centre_id: str
    batch_id: str
    case_type: str
    status: CaseStatus = CaseStatus.open
    severity: str
    summary: str
    reported_attendance: int | None = None
    visual_occupancy: int | None = None
    discrepancy_pct: float | None = None
    persistence_ratio: float | None = None
    camera_trust: CameraTrust | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    review_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProcessSummary(BaseModel):
    centre_id: str
    batch_id: str
    reported_attendance: int
    estimated_occupancy: int
    discrepancy_pct: float
    observations: list[AttendanceObservation]
    case: ComplianceCase | None = None
    note: str = "Prototype output; external scheme records are simulated unless explicitly sourced."


class ReviewRequest(BaseModel):
    action: CaseStatus
    note: str | None = None


class EdgeSyncRequest(BaseModel):
    events: list[dict[str, Any]]
