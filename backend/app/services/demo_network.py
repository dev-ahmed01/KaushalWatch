from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from app.models import ComplianceCase

DEMO_CENTRES = [
    {
        "centre_id": "DEMO-KA-104",
        "name": "Bengaluru TC-04",
        "location": "Bengaluru, Karnataka",
        "district": "Bengaluru Urban",
        "state": "Karnataka",
        "batch_id": "ELEC-2026-08",
        "job_role": "Construction Electrician - LV",
        "trainees": 120,
        "camera_id": "LAB-CAM-01",
        "connectivity_mode": "low_bandwidth",
    },
    {
        "centre_id": "DEMO-KA-112",
        "name": "Mysuru TC-12",
        "location": "Mysuru, Karnataka",
        "district": "Mysuru",
        "state": "Karnataka",
        "batch_id": "FIT-2026-07",
        "job_role": "Fitter",
        "trainees": 84,
        "camera_id": "LAB-CAM-02",
        "connectivity_mode": "normal",
    },
    {
        "centre_id": "DEMO-KA-207",
        "name": "Tumakuru TC-07",
        "location": "Tumakuru, Karnataka",
        "district": "Tumakuru",
        "state": "Karnataka",
        "batch_id": "WELD-2026-08",
        "job_role": "Welder",
        "trainees": 72,
        "camera_id": "WORKSHOP-CAM-01",
        "connectivity_mode": "low_bandwidth",
    },
    {
        "centre_id": "DEMO-KA-303",
        "name": "Hubballi TC-03",
        "location": "Hubballi, Karnataka",
        "district": "Dharwad",
        "state": "Karnataka",
        "batch_id": "MECH-2026-08",
        "job_role": "Mechanical Technician",
        "trainees": 96,
        "camera_id": "LAB-CAM-03",
        "connectivity_mode": "normal",
    },
    {
        "centre_id": "DEMO-KA-509",
        "name": "Belagavi TC-09",
        "location": "Belagavi, Karnataka",
        "district": "Belagavi",
        "state": "Karnataka",
        "batch_id": "ELEC-2026-08",
        "job_role": "Construction Electrician - LV",
        "trainees": 68,
        "camera_id": "LAB-CAM-01",
        "connectivity_mode": "low_bandwidth",
    },
    {
        "centre_id": "DEMO-KA-601",
        "name": "Mangaluru TC-01",
        "location": "Mangaluru, Karnataka",
        "district": "Dakshina Kannada",
        "state": "Karnataka",
        "batch_id": "CARP-2026-07",
        "job_role": "Carpenter",
        "trainees": 52,
        "camera_id": "WORKSHOP-CAM-02",
        "connectivity_mode": "normal",
    },
]


def _case_pillar(case_type: str) -> str:
    if case_type == "attendance_discrepancy":
        return "attendance"
    if case_type.startswith("practical_activity"):
        return "practical_work"
    if case_type == "infrastructure_compliance":
        return "infrastructure"
    if case_type == "camera_integrity":
        return "camera_integrity"
    return "other"


def _escalation_level(cases: list[ComplianceCase]) -> dict:
    pending = [
        case for case in cases
        if case.status.value in {"open", "under_review", "virtual_verification"}
    ]
    confirmed = [case for case in cases if case.status.value == "confirmed"]
    duplicate_count = sum(
        1 for case in cases for evidence in case.evidence if evidence.duplicate_of
    )
    pillars = {_case_pillar(case.case_type) for case in pending + confirmed}

    score = 0
    reasons: list[str] = []
    if len(pending) >= 3:
        score += 2
        reasons.append(f"{len(pending)} unresolved exceptions")
    elif len(pending) >= 1:
        score += 1
        reasons.append(f"{len(pending)} pending exception{'s' if len(pending) != 1 else ''}")
    if len(confirmed) >= 2:
        score += 2
        reasons.append("repeated confirmed issues")
    if len(pillars) >= 2:
        score += 1
        reasons.append("multiple independent compliance signals")
    if duplicate_count:
        score += 1
        reasons.append("possible duplicate evidence")

    if score >= 5:
        level, label = 4, "Ministry review"
    elif score >= 3:
        level, label = 3, "Regional escalation"
    elif score >= 2:
        level, label = 2, "Regional attention"
    elif score >= 1:
        level, label = 1, "Centre review"
    else:
        level, label = 0, "Normal"

    return {
        "level": level,
        "label": label,
        "reasons": reasons or ["No escalation trigger"],
    }


def centre_rows(cases: Iterable[ComplianceCase]) -> list[dict]:
    cases = list(cases)
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for centre in DEMO_CENTRES:
        centre_cases = [case for case in cases if case.centre_id == centre["centre_id"]]
        pending = [
            case for case in centre_cases
            if case.status.value in {"open", "under_review", "virtual_verification"}
        ]
        pillars = Counter(_case_pillar(case.case_type) for case in pending)
        escalation = _escalation_level(centre_cases)

        status = "compliant"
        if escalation["level"] >= 3:
            status = "high_priority"
        elif pending:
            status = "attention"

        rows.append({
            **centre,
            "status": status,
            "pending_cases": len(pending),
            "attendance_status": "attention" if pillars["attendance"] else "compliant",
            "practical_status": "attention" if pillars["practical_work"] else "compliant",
            "infrastructure_status": "attention" if pillars["infrastructure"] else "compliant",
            "camera_status": "attention" if pillars["camera_integrity"] else "nominal",
            "escalation": escalation,
            "last_analysis": centre_cases[-1].created_at if centre_cases else now,
        })
    return rows


def get_centre(centre_id: str, cases: Iterable[ComplianceCase]) -> dict | None:
    return next((row for row in centre_rows(cases) if row["centre_id"] == centre_id), None)
