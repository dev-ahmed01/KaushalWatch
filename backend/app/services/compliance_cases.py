from __future__ import annotations

import uuid
from app.models import ComplianceCase


def build_infrastructure_case(
    centre_id: str,
    batch_id: str,
    job_role: str,
    results: list[dict],
) -> ComplianceCase | None:
    discrepancies = [r for r in results if r.get("state") == "DISCREPANCY"]
    uncertain = [r for r in results if r.get("state") == "UNCERTAIN"]
    if not discrepancies and not uncertain:
        return None

    missing_units = sum(
        max(0, int(r.get("required") or 0) - int(r.get("observed") or 0))
        for r in discrepancies
    )
    severity = "high" if missing_units >= 2 or len(discrepancies) >= 2 else "medium"
    parts = []
    if discrepancies:
        parts.append(
            ", ".join(
                f"{r['label']} {r.get('observed', 0)}/{r.get('required', 0)}"
                for r in discrepancies
            )
        )
    if uncertain:
        parts.append(
            "uncertain: " + ", ".join(r["label"] for r in uncertain)
        )

    return ComplianceCase(
        case_id=f"CASE-{uuid.uuid4().hex[:8].upper()}",
        centre_id=centre_id,
        batch_id=batch_id,
        case_type="infrastructure_compliance",
        severity=severity,
        summary=(
            f"{job_role} visual manifest exception. "
            + "; ".join(parts)
            + ". Human verification is required before any compliance action."
        ),
        details={
            "job_role": job_role,
            "items": results,
            "verification_basis": "demo cached detections",
            "operational_data_status": "simulated",
        },
    )


def build_camera_integrity_case(
    centre_id: str,
    batch_id: str,
    camera_id: str,
    reasons: list[str],
    trust_score: float,
) -> ComplianceCase:
    return ComplianceCase(
        case_id=f"CASE-{uuid.uuid4().hex[:8].upper()}",
        centre_id=centre_id,
        batch_id=batch_id,
        case_type="camera_integrity",
        severity="high" if trust_score <= 40 else "medium",
        summary=(
            f"Camera {camera_id} failed visual trust checks: "
            + ", ".join(reasons or ["unspecified integrity failure"])
            + ". Compliance inference should be suspended until the feed is restored."
        ),
        details={
            "camera_id": camera_id,
            "camera_trust_score": trust_score,
            "reasons": reasons,
        },
    )



def build_camera_visibility_case(
    centre_id: str,
    batch_id: str,
    camera_id: str,
    reasons: list[str],
    trust_score: float,
) -> ComplianceCase:
    """Camera may be unusable without evidence of tampering."""
    return ComplianceCase(
        case_id=f"CASE-{uuid.uuid4().hex[:8].upper()}",
        centre_id=centre_id,
        batch_id=batch_id,
        case_type="camera_visibility",
        severity="medium",
        summary=(
            f"Camera {camera_id} has insufficient visibility: "
            + ", ".join(reasons or ["low image quality"])
            + ". Attendance and practical activity conclusions are suspended "
            "pending review; no tampering is inferred."
        ),
        details={
            "camera_id": camera_id,
            "camera_trust_score": trust_score,
            "reasons": reasons,
            "decision_basis": "inadequate visual evidence, not camera sabotage",
        },
    )


def build_practical_activity_case(
    centre_id: str,
    batch_id: str,
    camera_id: str,
    authorization: str,
    practical_activity_fraction: float,
    active_work_cells: int,
) -> ComplianceCase | None:
    if practical_activity_fraction <= 0:
        return None

    if authorization == "valid":
        return None

    if authorization == "absent":
        case_type = "practical_activity_authorization"
        severity = "high" if practical_activity_fraction >= 0.5 else "medium"
        summary = (
            f"Persistent practical-work activity was visually observed in "
            f"{active_work_cells} configured work cell(s), but no matching "
            f"training/work authorization was supplied. Human review is required."
        )
    else:
        case_type = "practical_activity_authorization_review"
        severity = "medium"
        summary = (
            f"Persistent practical-work activity was visually observed in "
            f"{active_work_cells} configured work cell(s), but authorization "
            f"status is unknown. Human verification is required."
        )

    return ComplianceCase(
        case_id=f"CASE-{uuid.uuid4().hex[:8].upper()}",
        centre_id=centre_id,
        batch_id=batch_id,
        case_type=case_type,
        severity=severity,
        summary=summary,
        persistence_ratio=round(practical_activity_fraction, 3),
        details={
            "camera_id": camera_id,
            "authorization": authorization,
            "practical_activity_fraction": round(practical_activity_fraction, 4),
            "active_work_cells": active_work_cells,
            "individual_identification": False,
            "decision_basis": (
                "worker-centric visual motion + configured work-cell presence + "
                "external authorization state"
            ),
        },
    )
