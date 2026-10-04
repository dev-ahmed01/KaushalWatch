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
    estimated_occupancy: int | None
    discrepancy_pct: float | None
    decision: str = "unknown"
    trusted_sample_ratio: float = Field(default=0.0, ge=0, le=1)
    mismatch_persistence_ratio: float = Field(default=0.0, ge=0, le=1)
    sample_every_seconds: float = 0.2
    observations: list[AttendanceObservation]
    detector_backend: str
    detector_mode: str
    detector_authoritative: bool
    detector_message: str
    frames_sampled: int
    detector_failures: int = 0
    case: ComplianceCase | None = None
    note: str = "Prototype output; external scheme records are simulated unless explicitly sourced."


class WorkCellActivity(BaseModel):
    zone_id: str
    registered_worker_presence_fraction: float = Field(ge=0, le=1)
    activity_fraction: float = Field(ge=0, le=1)
    worker_motion_fraction_p50: float = Field(ge=0, le=1)
    worker_motion_fraction_p90: float = Field(ge=0, le=1)
    worker_motion_fraction_p95: float = Field(ge=0, le=1)


class PracticalActivitySummary(BaseModel):
    centre_id: str
    batch_id: str
    camera_id: str
    authorization: str
    decision: str
    zone_scaled: bool = False
    zone_reference_width: int | None = None
    zone_reference_height: int | None = None
    frames_processed: int
    duration_sec: float
    trusted_frame_ratio: float = Field(ge=0, le=1)
    peak_stable_workers: int
    practical_activity_fraction: float = Field(ge=0, le=1)
    first_practical_activity_time_sec: float | None = None
    active_work_cells: int
    work_cells: list[WorkCellActivity] = Field(default_factory=list)
    detector_backend: str = "unknown"
    detector_mode: str = "unknown"
    detector_authoritative: bool = False
    detector_message: str = ""
    detector_failures: int = 0
    case: ComplianceCase | None = None
    note: str = (
        "Practical activity is a worker-centric visual motion proxy. "
        "Authorization is external work-order/training-schedule state."
    )


class ReviewRequest(BaseModel):
    action: CaseStatus
    note: str | None = None


class EdgeSyncRequest(BaseModel):
    events: list[dict[str, Any]]
