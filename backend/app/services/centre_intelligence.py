from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.models import ComplianceCase


LOCAL_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
ACTIVE_CASE_STATUSES = {"open", "under_review", "virtual_verification", "confirmed"}


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE)


def _period_window(period: str, now: datetime) -> tuple[datetime, datetime, str, str]:
    local_now = now.astimezone(LOCAL_TIMEZONE)
    normalized = period.strip().lower().replace(" ", "_")
    if normalized == "today":
        start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, local_now + timedelta(microseconds=1), "today", "Today"
    if normalized == "yesterday":
        end = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        return start, end, "yesterday", "Yesterday"
    if normalized in {"7d", "7_days", "last_7_days"}:
        return local_now - timedelta(days=7), local_now + timedelta(microseconds=1), "last_7_days", "Last 7 days"
    if normalized in {"30d", "30_days", "last_30_days"}:
        return local_now - timedelta(days=30), local_now + timedelta(microseconds=1), "last_30_days", "Last 30 days"
    raise ValueError("period must be one of: today, yesterday, last_7_days, last_30_days")


def _latest(history: list[dict[str, Any]], analysis_type: str) -> dict[str, Any] | None:
    rows = [row for row in history if row.get("analysis_type") == analysis_type]
    if not rows:
        return None
    return max(rows, key=lambda row: str(row.get("created_at") or ""))


def _active_cases(cases: Iterable[ComplianceCase], case_type: str | None = None) -> list[ComplianceCase]:
    rows = [
        case for case in cases
        if case.status.value in ACTIVE_CASE_STATUSES
        and (case_type is None or case.case_type == case_type)
    ]
    rows.sort(key=lambda case: str(case.created_at or ""), reverse=True)
    return rows


def _dependent_state(value: object, camera_state: str) -> str:
    if camera_state == "uncertain":
        return "uncertain"
    normalized = str(value or "").lower()
    if normalized in {"compliant", "verified", "nominal", "clear"}:
        return "verified"
    if normalized in {"attention", "review", "high_priority"}:
        return "review"
    if normalized in {"blocked", "uncertain"}:
        return "uncertain"
    return "unavailable"


def _camera_state(centre: dict[str, Any]) -> str:
    value = str(centre.get("camera_status") or "").lower()
    if value in {"attention", "blocked"}:
        return "uncertain"
    if value in {"nominal", "clear", "verified"}:
        return "verified"
    return "unavailable"


def _evidence_state(centre: dict[str, Any], cases: list[ComplianceCase]) -> tuple[str, str]:
    possible_duplicates = 0
    for case in cases:
        possible_duplicates += sum(1 for item in case.evidence if item.duplicate_of)
        integrity = case.details.get("evidence_integrity") or {}
        if isinstance(integrity, dict) and integrity.get("possible_duplicate"):
            possible_duplicates += 1

    if possible_duplicates:
        return "review", f"{possible_duplicates} possible duplicate evidence signal{'s' if possible_duplicates != 1 else ''} require review."

    value = str(centre.get("evidence_integrity_status") or "").lower()
    if value == "clear":
        return "verified", "Original evidence integrity metadata is clear."
    if value == "attention":
        return "review", "Evidence integrity requires officer review."
    return "unavailable", "No retained integrity conclusion is available yet."


def _attendance_summary(cases: list[ComplianceCase], latest: dict[str, Any] | None, state: str) -> str:
    attendance_cases = _active_cases(cases, "attendance_discrepancy")
    if attendance_cases:
        case = attendance_cases[0]
        if case.reported_attendance is not None and case.visual_occupancy is not None:
            return f"{case.reported_attendance} reported · {case.visual_occupancy} observed in retained evidence."
        return case.summary
    if state == "uncertain":
        return "Trusted attendance conclusion is suspended by camera state."
    details = (latest or {}).get("details") or {}
    reported = details.get("reported_attendance", details.get("reported"))
    observed = details.get("estimated_occupancy", details.get("observed"))
    if reported is not None and observed is not None:
        return f"{reported} reported · {observed} observed."
    if latest:
        return str(latest.get("summary") or "Latest attendance evidence is available.")
    return "No trusted attendance analysis yet."


def _practical_summary(latest: dict[str, Any] | None, state: str) -> str:
    if state == "uncertain":
        return "Practical-activity conclusion is suspended by camera state."
    details = (latest or {}).get("details") or {}
    cells = details.get("active_work_cells")
    workers = details.get("peak_stable_workers")
    if cells is not None and workers is not None:
        return f"{cells} active work cells · peak {workers} stable workers."
    if cells is not None:
        return f"{cells} active work cells in the latest analysis."
    if latest:
        return str(latest.get("summary") or "Latest practical activity evidence is available.")
    return "No trusted practical-activity analysis yet."


def _infrastructure_summary(cases: list[ComplianceCase], latest: dict[str, Any] | None, state: str) -> str:
    infrastructure_cases = _active_cases(cases, "infrastructure_compliance")
    if infrastructure_cases:
        case = infrastructure_cases[0]
        reported = case.details.get("reported_quantity")
        observed = case.details.get("observed_quantity")
        if reported is not None and observed is not None:
            return f"{observed} observed against {reported} reported in the current case."
        return case.summary
    if state == "uncertain":
        return "Infrastructure conclusion is suspended by camera state."
    if latest:
        return str(latest.get("summary") or "Latest infrastructure evidence is available.")
    return "No trusted infrastructure analysis yet."


def _apparent_operability(cases: list[ComplianceCase], camera_state: str) -> dict[str, Any]:
    if camera_state == "uncertain":
        return {
            "key": "apparent_operability",
            "name": "Apparent operability",
            "state": "uncertain",
            "label": "UNCERTAIN",
            "summary": "Camera trust is insufficient for a visual activity proxy.",
            "href_suffix": "/infrastructure",
        }

    for case in sorted(cases, key=lambda item: str(item.created_at or ""), reverse=True):
        payload = case.details.get("apparent_operability")
        if not isinstance(payload, dict):
            continue
        raw_state = str(payload.get("state") or "").upper()
        if raw_state == "APPARENTLY_ACTIVE":
            state, label = "verified", "APPARENTLY ACTIVE"
        elif raw_state == "APPARENTLY_INACTIVE":
            state, label = "review", "APPARENTLY INACTIVE"
        else:
            state, label = "uncertain", "UNCERTAIN"
        item = str(payload.get("item_id") or "equipment").replace("_", " ")
        return {
            "key": "apparent_operability",
            "name": "Apparent operability",
            "state": state,
            "label": label,
            "summary": f"{item.title()} · visual activity proxy only, not mechanical or electrical health.",
            "href_suffix": "/infrastructure",
        }

    return {
        "key": "apparent_operability",
        "name": "Apparent operability",
        "state": "unavailable",
        "label": "ANALYSIS UNAVAILABLE",
        "summary": "No trusted visual activity proxy has been recorded for equipment yet.",
        "href_suffix": "/infrastructure",
    }


def _action_rows(centre_id: str, centre: dict[str, Any], cases: list[ComplianceCase], engines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    camera = next(item for item in engines if item["key"] == "camera_integrity")
    if camera["state"] == "uncertain":
        actions.append({
            "priority": "high",
            "title": "Verify camera evidence",
            "reason": "Dependent conclusions are suspended until camera trust is restored.",
            "href": f"/centres/{centre_id}/evidence",
        })

    attendance_cases = _active_cases(cases, "attendance_discrepancy")
    if attendance_cases:
        actions.append({
            "priority": "high",
            "title": "Review attendance evidence",
            "reason": attendance_cases[0].summary,
            "href": f"/centres/{centre_id}/evidence",
        })

    infrastructure_cases = _active_cases(cases, "infrastructure_compliance")
    if infrastructure_cases:
        actions.append({
            "priority": "medium",
            "title": "Review infrastructure evidence",
            "reason": infrastructure_cases[0].summary,
            "href": f"/centres/{centre_id}/infrastructure",
        })

    if not actions and str(centre.get("status") or "").lower() == "compliant":
        actions.append({
            "priority": "low",
            "title": "No immediate officer action",
            "reason": "Latest trusted checks are aligned.",
            "href": f"/centres/{centre_id}",
        })

    return actions[:3]


def build_centre_intelligence(
    *,
    centre: dict[str, Any],
    cases: Iterable[ComplianceCase],
    history: list[dict[str, Any]],
    settings: dict[str, Any] | None = None,
    period: str = "last_7_days",
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    start, end, normalized_period, period_label = _period_window(period, current_time)
    centre_id = str(centre.get("centre_id") or "")
    centre_cases = [case for case in cases if case.centre_id == centre_id]
    current_camera_state = _camera_state(centre)

    recent = []
    for row in history:
        if str(row.get("centre_id") or "") != centre_id:
            continue
        created = _parse_timestamp(row.get("created_at"))
        if created and start <= created < end:
            recent.append(row)
    recent.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)

    attendance_latest = _latest(history, "attendance")
    practical_latest = _latest(history, "practical_work")
    infrastructure_latest = _latest(history, "infrastructure")

    attendance_state = _dependent_state(centre.get("attendance_status"), current_camera_state)
    practical_state = _dependent_state(centre.get("practical_status"), current_camera_state)
    infrastructure_state = _dependent_state(centre.get("infrastructure_status"), current_camera_state)
    evidence_state, evidence_summary = _evidence_state(centre, centre_cases)

    engines = [
        {
            "key": "attendance",
            "name": "Attendance",
            "state": attendance_state,
            "label": "NEEDS REVIEW" if attendance_state == "review" else None,
            "summary": _attendance_summary(centre_cases, attendance_latest, attendance_state),
            "href_suffix": "/attendance",
        },
        {
            "key": "practical_activity",
            "name": "Practical activity",
            "state": practical_state,
            "label": "ACTIVE" if practical_state == "verified" else None,
            "summary": _practical_summary(practical_latest, practical_state),
            "href_suffix": "/practical",
        },
        {
            "key": "infrastructure",
            "name": "Infrastructure",
            "state": infrastructure_state,
            "label": None,
            "summary": _infrastructure_summary(centre_cases, infrastructure_latest, infrastructure_state),
            "href_suffix": "/infrastructure",
        },
        {
            "key": "camera_integrity",
            "name": "Camera integrity",
            "state": current_camera_state,
            "label": "TRUSTED" if current_camera_state == "verified" else None,
            "summary": (
                "Camera evidence remained usable for current conclusions."
                if current_camera_state == "verified"
                else "Camera trust is insufficient; dependent conclusions remain suspended."
                if current_camera_state == "uncertain"
                else "No trusted camera conclusion is available yet."
            ),
            "href_suffix": "/evidence",
        },
        {
            "key": "evidence_integrity",
            "name": "Evidence integrity",
            "state": evidence_state,
            "label": None,
            "summary": evidence_summary,
            "href_suffix": "/evidence",
        },
        _apparent_operability(centre_cases, current_camera_state),
    ]

    problem_engines = [item for item in engines if item["state"] in {"review", "uncertain"}]
    if current_camera_state == "uncertain":
        headline = "Camera trust is limiting this centre's conclusions."
    elif problem_engines:
        headline = f"{problem_engines[0]['name']} needs officer attention."
    elif all(item["state"] == "verified" for item in engines[:5]):
        headline = "Latest trusted checks are aligned."
    else:
        headline = "Some centre checks do not yet have a trusted conclusion."

    bullets = []
    for item in engines:
        if item["state"] in {"review", "uncertain"}:
            bullets.append(f"{item['name']}: {item['summary']}")
    if not bullets:
        for item in engines[:3]:
            if item["state"] == "verified":
                bullets.append(f"{item['name']}: {item['summary']}")
    if current_camera_state == "verified" and not any(line.startswith("Camera integrity") for line in bullets):
        bullets.append("Camera integrity: Camera evidence remained usable for current conclusions.")
    bullets = bullets[:4]

    actions = _action_rows(centre_id, centre, centre_cases, engines)
    if actions and len(bullets) < 4:
        bullets.append(f"Recommended next step: {actions[0]['title']}.")

    contact = {
        "role": "Centre Head",
        "available": False,
        "name": None,
        "phone": None,
        "email": None,
        "note": "Centre contact details are not connected in this prototype.",
    }

    schedule = settings or {}
    simulated = any(bool(case.details.get("simulated")) for case in centre_cases) or any(
        bool((row.get("details") or {}).get("simulated")) for row in history
    )

    return {
        "generated_at": current_time.astimezone(LOCAL_TIMEZONE).isoformat(),
        "timezone": "Asia/Kolkata",
        "period": normalized_period,
        "period_label": period_label,
        "grounded": True,
        "simulated": simulated,
        "centre": {
            "centre_id": centre_id,
            "name": centre.get("name"),
            "location": centre.get("location"),
            "district": centre.get("district"),
            "state": centre.get("state"),
            "batch_id": centre.get("batch_id"),
            "job_role": centre.get("job_role"),
            "trainees": centre.get("trainees"),
            "camera_id": centre.get("camera_id"),
            "connectivity_mode": centre.get("connectivity_mode"),
            "last_analysis": centre.get("last_analysis"),
            "escalation": centre.get("escalation"),
        },
        "brief": {
            "headline": headline,
            "bullets": bullets,
        },
        "engines": engines,
        "actions": actions,
        "contact": contact,
        "schedule": {
            "automatic_analysis": schedule.get("automatic_analysis", True),
            "frequency": schedule.get("frequency", "every_training_day"),
            "monitoring_windows": schedule.get("monitoring_windows", ["09:00-11:00", "14:00-16:00"]),
        },
        "period_activity": {
            "analysis_runs": len(recent),
            "recent_analyses": [
                {
                    "analysis_id": row.get("analysis_id"),
                    "created_at": row.get("created_at"),
                    "analysis_type": row.get("analysis_type"),
                    "outcome": row.get("outcome"),
                    "summary": row.get("summary"),
                }
                for row in recent[:5]
            ],
        },
        "decision_policy": "AI surfaces evidence. Officers decide.",
    }
