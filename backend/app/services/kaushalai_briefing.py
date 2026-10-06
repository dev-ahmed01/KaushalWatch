from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable

from app.models import ComplianceCase


LOCAL_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
AI_FIRST_CENTRE_IDS = (
    "DEMO-KA-104",
    "DEMO-KA-112",
    "DEMO-KA-207",
    "DEMO-KA-303",
    "DEMO-KA-509",
)
UNRESOLVED_STATUSES = {"open", "under_review", "virtual_verification", "confirmed"}


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE)


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=LOCAL_TIMEZONE)


def _period_bounds(period: str, now: datetime) -> tuple[datetime, datetime, str, str]:
    local_now = now.astimezone(LOCAL_TIMEZONE)
    today = local_now.date()
    normalized = period.strip().lower().replace(" ", "_")

    if normalized in {"today"}:
        return _local_midnight(today), local_now + timedelta(microseconds=1), "today", "Today"
    if normalized in {"yesterday"}:
        start = today - timedelta(days=1)
        return _local_midnight(start), _local_midnight(today), "yesterday", "Yesterday"
    if normalized in {"7d", "last_7_days", "7_days"}:
        return local_now - timedelta(days=7), local_now + timedelta(microseconds=1), "last_7_days", "Last 7 days"
    if normalized in {"30d", "last_30_days", "30_days"}:
        return local_now - timedelta(days=30), local_now + timedelta(microseconds=1), "last_30_days", "Last 30 days"
    raise ValueError("period must be one of: today, yesterday, last_7_days, last_30_days")


def _in_window(value: object, start: datetime, end: datetime) -> bool:
    parsed = _parse_timestamp(value)
    return bool(parsed and start <= parsed < end)


def _ui_state(centre: dict[str, Any]) -> str:
    camera = str(centre.get("camera_status") or "").lower()
    if camera in {"attention", "blocked"}:
        return "uncertain"
    if int(centre.get("pending_cases") or 0) > 0 or int(centre.get("confirmed_cases") or 0) > 0:
        return "review"
    if str(centre.get("status") or "").lower() in {"attention", "high_priority"}:
        return "review"
    if str(centre.get("status") or "").lower() == "compliant":
        return "verified"
    return "unavailable"


def _status_reason(centre: dict[str, Any], unresolved: list[ComplianceCase]) -> str:
    camera = str(centre.get("camera_status") or "").lower()
    if camera in {"attention", "blocked"}:
        return "Camera trust is insufficient; dependent conclusions remain suspended."

    if unresolved:
        newest = max(unresolved, key=lambda case: str(case.created_at or ""))
        if newest.case_type == "attendance_discrepancy":
            if newest.reported_attendance is not None and newest.visual_occupancy is not None:
                return (
                    f"Attendance needs review: {newest.reported_attendance} reported, "
                    f"{newest.visual_occupancy} observed in retained evidence."
                )
            return "Attendance discrepancy remains open for officer review."
        if newest.case_type == "infrastructure_compliance":
            reported = newest.details.get("reported_quantity")
            observed = newest.details.get("observed_quantity")
            if reported is not None and observed is not None:
                return f"Infrastructure needs review: {observed} observed against {reported} reported."
            return "Infrastructure discrepancy remains open for officer review."
        if newest.case_type.startswith("practical_activity"):
            return "Practical activity evidence requires officer review."
        return newest.summary

    if str(centre.get("attendance_status") or "").lower() == "attention":
        return "Attendance evidence needs officer review."
    if str(centre.get("infrastructure_status") or "").lower() == "attention":
        return "Infrastructure evidence needs officer review."
    if str(centre.get("practical_status") or "").lower() == "attention":
        return "Practical activity evidence needs officer review."
    if _ui_state(centre) == "verified":
        return "Latest trusted checks are aligned; no officer action is currently required."
    return "No trusted conclusion is available yet."


def _next_action(state: str, centre: dict[str, Any], unresolved: list[ComplianceCase]) -> tuple[str, str]:
    centre_id = str(centre.get("centre_id") or "")
    if state == "uncertain":
        return "Verify camera evidence", f"/centres/{centre_id}/evidence"
    if unresolved:
        newest = max(unresolved, key=lambda case: str(case.created_at or ""))
        if newest.case_type == "attendance_discrepancy":
            return "Review attendance evidence", f"/centres/{centre_id}/evidence"
        if newest.case_type == "infrastructure_compliance":
            return "Review infrastructure evidence", f"/centres/{centre_id}/infrastructure"
        return "Review open case", f"/centres/{centre_id}/evidence"
    if state == "review":
        return "Review centre evidence", f"/centres/{centre_id}/evidence"
    return "View centre", f"/centres/{centre_id}"


def _priority_score(state: str, centre: dict[str, Any], unresolved: list[ComplianceCase]) -> int:
    score = {"review": 300, "uncertain": 240, "unavailable": 100, "verified": 0}.get(state, 0)
    score += int((centre.get("escalation") or {}).get("level") or 0) * 30
    severity_weight = {"critical": 80, "high": 60, "medium": 30, "low": 10}
    if unresolved:
        score += max(severity_weight.get(str(case.severity).lower(), 0) for case in unresolved)
    return score


def build_network_brief(
    *,
    centres: list[dict[str, Any]],
    cases: Iterable[ComplianceCase],
    history: list[dict[str, Any]],
    period: str = "yesterday",
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    start, end, normalized_period, period_label = _period_bounds(period, current_time)

    selected_centres = [
        centre for centre in centres
        if str(centre.get("centre_id")) in AI_FIRST_CENTRE_IDS
    ]
    centre_order = {centre_id: index for index, centre_id in enumerate(AI_FIRST_CENTRE_IDS)}
    selected_centres.sort(key=lambda centre: centre_order.get(str(centre.get("centre_id")), 99))

    all_cases = [
        case for case in cases
        if case.centre_id in AI_FIRST_CENTRE_IDS
    ]
    period_history = [
        row for row in history
        if str(row.get("centre_id") or "") in AI_FIRST_CENTRE_IDS
        and _in_window(row.get("created_at"), start, end)
    ]

    case_by_centre: dict[str, list[ComplianceCase]] = {}
    for case in all_cases:
        if case.status.value in UNRESOLVED_STATUSES:
            case_by_centre.setdefault(case.centre_id, []).append(case)

    history_by_centre: dict[str, list[dict[str, Any]]] = {}
    for row in period_history:
        history_by_centre.setdefault(str(row.get("centre_id") or ""), []).append(row)

    centre_briefs = []
    state_counts: Counter[str] = Counter()

    for centre in selected_centres:
        centre_id = str(centre.get("centre_id") or "")
        unresolved = case_by_centre.get(centre_id, [])
        selected_history = history_by_centre.get(centre_id, [])
        state = _ui_state(centre)
        state_counts[state] += 1
        action_label, action_href = _next_action(state, centre, unresolved)

        analysis_types = Counter(
            str(row.get("analysis_type") or "unknown")
            for row in selected_history
        )
        attention_count = sum(
            1 for row in selected_history
            if str(row.get("outcome") or "").lower() in {"attention", "blocked"}
        )
        simulated = any(
            bool((row.get("details") or {}).get("simulated"))
            for row in selected_history
        ) or any(bool(case.details.get("simulated")) for case in unresolved)

        centre_briefs.append({
            "centre_id": centre_id,
            "name": centre.get("name"),
            "location": centre.get("location"),
            "district": centre.get("district"),
            "job_role": centre.get("job_role"),
            "state": state,
            "reason": _status_reason(centre, unresolved),
            "period_analysis_count": len(selected_history),
            "period_attention_count": attention_count,
            "analysis_types": dict(analysis_types),
            "open_case_count": len(unresolved),
            "escalation_level": int((centre.get("escalation") or {}).get("level") or 0),
            "recommended_action": {
                "label": action_label,
                "href": action_href,
            },
            "simulated": simulated,
            "href": f"/centres/{centre_id}",
            "_priority_score": _priority_score(state, centre, unresolved),
        })

    ranked = sorted(
        centre_briefs,
        key=lambda item: (-int(item["_priority_score"]), centre_order.get(item["centre_id"], 99)),
    )
    attention = [item for item in ranked if item["state"] != "verified"]
    recommendations = [
        {
            "centre_id": item["centre_id"],
            "centre_name": item["name"],
            "state": item["state"],
            "reason": item["reason"],
            **item["recommended_action"],
        }
        for item in attention[:3]
    ]

    priority = recommendations[0] if recommendations else None
    bullets = []
    verified = state_counts["verified"]
    review = state_counts["review"]
    uncertain = state_counts["uncertain"]
    unavailable = state_counts["unavailable"]

    bullets.append(
        f"{verified} of {len(selected_centres)} centres are verified from their latest trusted evidence."
    )
    if review:
        bullets.append(f"{review} centres require officer review.")
    if uncertain:
        bullets.append(
            f"{uncertain} centre has an uncertain state because camera trust is insufficient."
            if uncertain == 1
            else f"{uncertain} centres have uncertain states because camera trust is insufficient."
        )
    if unavailable:
        bullets.append(f"{unavailable} centres do not yet have a trusted conclusion.")
    if not period_history:
        bullets.append(
            f"No new analysis runs were recorded in {period_label.lower()}; current states use the latest trusted evidence."
        )
    else:
        attention_runs = sum(
            1 for row in period_history
            if str(row.get("outcome") or "").lower() in {"attention", "blocked"}
        )
        bullets.append(
            f"{len(period_history)} analysis runs were recorded in {period_label.lower()}, "
            f"including {attention_runs} that need review or were blocked."
        )

    for item in centre_briefs:
        item.pop("_priority_score", None)

    simulated = any(item["simulated"] for item in centre_briefs)
    return {
        "generated_at": current_time.astimezone(LOCAL_TIMEZONE).isoformat(),
        "timezone": "Asia/Kolkata",
        "period": normalized_period,
        "period_label": period_label,
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "grounded": True,
        "simulated": simulated,
        "headline": f"{verified} of {len(selected_centres)} centres are verified.",
        "bullets": bullets[:4],
        "counts": {
            "total": len(selected_centres),
            "verified": verified,
            "review": review,
            "uncertain": uncertain,
            "unavailable": unavailable,
        },
        "period_activity": {
            "analysis_runs": len(period_history),
            "attention_or_blocked_runs": sum(
                1 for row in period_history
                if str(row.get("outcome") or "").lower() in {"attention", "blocked"}
            ),
            "analysis_types": dict(Counter(
                str(row.get("analysis_type") or "unknown") for row in period_history
            )),
        },
        "priority": priority,
        "recommendations": recommendations,
        "centres": centre_briefs,
        "source_counts": {
            "analysis_rows_in_period": len(period_history),
            "unresolved_or_confirmed_cases": sum(len(rows) for rows in case_by_centre.values()),
        },
        "decision_policy": "AI surfaces evidence. Officers decide.",
    }
