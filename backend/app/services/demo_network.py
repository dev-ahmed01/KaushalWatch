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


def _case_has_duplicate(case: ComplianceCase) -> bool:
    if any(evidence.duplicate_of for evidence in case.evidence):
        return True
    edge_integrity = case.details.get("edge_evidence_integrity") or []
    return any(
        isinstance(evidence, dict)
        and (evidence.get("duplicate_of") or evidence.get("possible_duplicate"))
        for evidence in edge_integrity
    )


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
    duplicate_count = sum(1 for case in cases if _case_has_duplicate(case))
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


def _latest_by_type(history: list[dict[str, Any]], analysis_type: str) -> dict[str, Any] | None:
    """History rows are normally newest-first; remain correct for arbitrary order."""
    matches = [row for row in history if row.get("analysis_type") == analysis_type]
    if not matches:
        return None

    def sort_key(row: dict[str, Any]) -> str:
        return str(row.get("created_at") or "")

    return max(matches, key=sort_key)


def _analysis_state(history: list[dict[str, Any]], analysis_type: str) -> str:
    row = _latest_by_type(history, analysis_type)
    if not row:
        return "pending"
    outcome = str(row.get("outcome") or "").lower()
    if outcome == "compliant":
        return "compliant"
    if outcome == "blocked":
        return "blocked"
    return "attention"


def centre_rows(
    cases: Iterable[ComplianceCase],
    settings_by_centre: dict[str, dict[str, Any]] | None = None,
    history_by_centre: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict]:
    cases = list(cases)
    settings_by_centre = settings_by_centre or {}
    history_by_centre = history_by_centre or {}
    rows = []

    for centre in DEMO_CENTRES:
        centre_id = centre["centre_id"]
        centre_cases = [case for case in cases if case.centre_id == centre_id]
        pending = [
            case for case in centre_cases
            if case.status.value in {"open", "under_review", "virtual_verification"}
        ]
        confirmed = [case for case in centre_cases if case.status.value == "confirmed"]
        active_cases = pending + confirmed
        case_pillars = Counter(_case_pillar(case.case_type) for case in active_cases)
        escalation = _escalation_level(
            centre_cases,
            settings_by_centre.get(centre_id),
        )
        history = history_by_centre.get(centre_id, [])

        attendance_status = _analysis_state(history, "attendance")
        practical_status = _analysis_state(history, "practical_work")
        infrastructure_status = _analysis_state(history, "infrastructure")

        # A still-open evidence-backed case must remain visible even if a later page
        # happens to contain a stale compliant summary.
        if case_pillars["attendance"]:
            attendance_status = "attention"
        elif attendance_status == "attention":
            attendance_status = "compliant"
        if case_pillars["practical_work"]:
            practical_status = "attention"
        elif practical_status == "attention":
            practical_status = "compliant"
        if case_pillars["infrastructure"]:
            infrastructure_status = "attention"
        elif infrastructure_status == "attention":
            infrastructure_status = "compliant"

        has_video_analysis = bool(history)
        camera_status = (
            "attention"
            if case_pillars["camera_integrity"]
            else ("nominal" if has_video_analysis else "pending")
        )
        duplicate_active = any(_case_has_duplicate(case) for case in active_cases)
        evidence_integrity_status = (
            "attention"
            if duplicate_active
            else ("clear" if has_video_analysis else "pending")
        )

        checkpoint_states = [
            attendance_status,
            practical_status,
            infrastructure_status,
        ]
        if escalation["level"] >= 3:
            status = "high_priority"
        elif pending or confirmed or "attention" in checkpoint_states:
            status = "attention"
        elif any(state in {"pending", "blocked"} for state in checkpoint_states):
            status = "incomplete"
        else:
            status = "compliant"

        latest_history = max(
            history,
            key=lambda row: str(row.get("created_at") or ""),
            default=None,
        )

        rows.append({
            **centre,
            "status": status,
            "pending_cases": len(pending),
            "confirmed_cases": len(confirmed),
            "attendance_status": attendance_status,
            "practical_status": practical_status,
            "infrastructure_status": infrastructure_status,
            "camera_status": camera_status,
            "evidence_integrity_status": evidence_integrity_status,
            "verification_complete": all(
                state not in {"pending", "blocked"} for state in checkpoint_states
            ),
            "analysis_count": len(history),
            "escalation": escalation,
            "last_analysis": latest_history.get("created_at") if latest_history else None,
        })
    return rows


def get_centre(
    centre_id: str,
    cases: Iterable[ComplianceCase],
    settings: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict | None:
    rows = centre_rows(
        cases,
        settings_by_centre={centre_id: settings or {}},
        history_by_centre={centre_id: history or []},
    )
    return next((row for row in rows if row["centre_id"] == centre_id), None)
