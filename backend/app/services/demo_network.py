from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, Any

from app.models import ComplianceCase
from app.services.centre_settings import DEFAULT_SETTINGS

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


def _age_days(case: ComplianceCase) -> float:
    try:
        created = datetime.fromisoformat(case.created_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 86400)


def _escalation_level(
    cases: list[ComplianceCase],
    settings: dict[str, Any] | None = None,
) -> dict:
    effective = {**DEFAULT_SETTINGS, **(settings or {})}
    rules = {
        **DEFAULT_SETTINGS["escalation_rules"],
        **effective.get("escalation_rules", {}),
    }
    pending = [
        case for case in cases
        if case.status.value in {"open", "under_review", "virtual_verification"}
    ]
    confirmed = [case for case in cases if case.status.value == "confirmed"]
    duplicate_count = sum(
        1 for case in cases for evidence in case.evidence if evidence.duplicate_of
    )
    pillars = {_case_pillar(case.case_type) for case in pending + confirmed}

    attendance_days = {
        case.created_at[:10]
        for case in pending + confirmed
        if case.case_type == "attendance_discrepancy"
    }
    oldest_pending_days = max((_age_days(case) for case in pending), default=0.0)

    score = 0
    reasons: list[str] = []

    if len(pending) >= 3:
        score += 2
        reasons.append(f"{len(pending)} unresolved exceptions")
    elif pending:
        score += 1
        reasons.append(f"{len(pending)} pending exception{'s' if len(pending) != 1 else ''}")

    attendance_threshold = max(1, int(rules.get("repeated_attendance_days", 3)))
    if len(attendance_days) >= attendance_threshold:
        score += 2
        reasons.append(
            f"attendance discrepancy repeated on {len(attendance_days)} training days"
        )

    unresolved_threshold = max(1, int(rules.get("unresolved_case_days", 3)))
    if oldest_pending_days >= unresolved_threshold:
        score += 2
        reasons.append(
            f"oldest unresolved case is {int(oldest_pending_days)} days old"
        )

    if len(confirmed) >= 2:
        score += 2
        reasons.append("repeated confirmed issues")

    if bool(rules.get("multi_signal_escalation", True)) and len(pillars) >= 2:
        score += 1
        reasons.append("multiple independent compliance signals")

    if bool(rules.get("duplicate_evidence_escalation", True)) and duplicate_count:
        score += 1
        reasons.append("possible duplicate evidence")

    if score >= 5:
        level, label = 4, "Ministry review"
        next_action = "Escalate the evidence pack and case history for ministry-level review."
    elif score >= 3:
        level, label = 3, "Regional escalation"
        next_action = "Regional reviewer should inspect repeated or multi-signal exceptions."
    elif score >= 2:
        level, label = 2, "Regional attention"
        next_action = "Regional monitoring should review this centre before the next cycle."
    elif score >= 1:
        level, label = 1, "Centre review"
        next_action = "Centre monitoring officer should resolve the pending evidence-backed case."
    else:
        level, label = 0, "Normal"
        next_action = "No escalation action is currently required."

    return {
        "level": level,
        "label": label,
        "score": score,
        "reasons": reasons or ["No escalation trigger"],
        "next_action": next_action,
        "policy": {
            "repeated_attendance_days": attendance_threshold,
            "unresolved_case_days": unresolved_threshold,
            "multi_signal_escalation": bool(rules.get("multi_signal_escalation", True)),
            "duplicate_evidence_escalation": bool(rules.get("duplicate_evidence_escalation", True)),
        },
    }


def centre_rows(
    cases: Iterable[ComplianceCase],
    settings_by_centre: dict[str, dict[str, Any]] | None = None,
) -> list[dict]:
    cases = list(cases)
    settings_by_centre = settings_by_centre or {}
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for centre in DEMO_CENTRES:
        centre_cases = [case for case in cases if case.centre_id == centre["centre_id"]]
        pending = [
            case for case in centre_cases
            if case.status.value in {"open", "under_review", "virtual_verification"}
        ]
        pillars = Counter(_case_pillar(case.case_type) for case in pending)
        escalation = _escalation_level(
            centre_cases,
            settings_by_centre.get(centre["centre_id"]),
        )

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


def get_centre(
    centre_id: str,
    cases: Iterable[ComplianceCase],
    settings: dict[str, Any] | None = None,
) -> dict | None:
    rows = centre_rows(
        cases,
        settings_by_centre={centre_id: settings or {}},
    )
    return next((row for row in rows if row["centre_id"] == centre_id), None)
