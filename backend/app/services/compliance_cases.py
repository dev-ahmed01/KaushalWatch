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
