from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.models import ComplianceCase
from app.services.activity_intelligence import build_activity_intelligence


LOCAL_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
AI_FIRST_CENTRE_IDS = (
    "DEMO-KA-104",
    "DEMO-KA-112",
    "DEMO-KA-207",
    "DEMO-KA-303",
    "DEMO-KA-509",
)
ACTIVE_CASE_STATUSES = {"open", "under_review", "virtual_verification", "confirmed"}
HOURS = tuple(range(9, 16))


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE)


def _bounds(period: str, now: datetime) -> tuple[datetime, datetime, str, str]:
    local_now = now.astimezone(LOCAL_TIMEZONE)
    normalized = period.strip().lower().replace(" ", "_")
    if normalized == "today":
        start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, local_now + timedelta(microseconds=1), "today", "Today"
    if normalized == "yesterday":
        end = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return end - timedelta(days=1), end, "yesterday", "Yesterday"
    if normalized in {"7d", "7_days", "last_7_days"}:
        return local_now - timedelta(days=7), local_now + timedelta(microseconds=1), "last_7_days", "Last 7 days"
    if normalized in {"30d", "30_days", "last_30_days"}:
        return local_now - timedelta(days=30), local_now + timedelta(microseconds=1), "last_30_days", "Last 30 days"
    raise ValueError("period must be one of: today, yesterday, last_7_days, last_30_days")


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


def _latest(rows: list[dict[str, Any]], centre_id: str, analysis_type: str) -> dict[str, Any] | None:
    matches = [
        row for row in rows
        if str(row.get("centre_id") or "") == centre_id
        and row.get("analysis_type") == analysis_type
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: str(row.get("created_at") or ""))


def _attendance_point(
    centre: dict[str, Any],
    rows: list[dict[str, Any]],
    cases: list[ComplianceCase],
) -> dict[str, Any]:
    centre_id = str(centre.get("centre_id") or "")
    camera_untrusted = str(centre.get("camera_status") or "").lower() in {"attention", "blocked"}
    active_attendance = [
        case for case in cases
        if case.centre_id == centre_id
        and case.case_type == "attendance_discrepancy"
        and case.status.value in ACTIVE_CASE_STATUSES
    ]
    latest = _latest(rows, centre_id, "attendance")
    details = (latest or {}).get("details") or {}

    reported = details.get("reported_attendance", details.get("reported"))
    observed = details.get("estimated_occupancy", details.get("observed"))

    if active_attendance:
        newest = max(active_attendance, key=lambda case: str(case.created_at or ""))
        if newest.reported_attendance is not None:
            reported = newest.reported_attendance
        if newest.visual_occupancy is not None:
            observed = newest.visual_occupancy

    available = (
        not camera_untrusted
        and isinstance(reported, (int, float))
        and isinstance(observed, (int, float))
    )
    status = (
        "uncertain"
        if camera_untrusted
        else "review"
        if active_attendance
        else "verified"
        if available
        else "unavailable"
    )
    return {
        "centre_id": centre_id,
        "name": centre.get("name"),
        "short_name": str(centre.get("name") or centre_id).split(" TC-")[0],
        "reported": int(reported) if isinstance(reported, (int, float)) else None,
        "observed": int(observed) if isinstance(observed, (int, float)) else None,
        "difference": (
            abs(int(reported) - int(observed))
            if available else None
        ),
        "available": available,
        "status": status,
    }


def _hourly_values(timeline: list[dict[str, Any]]) -> list[float | None]:
    values: list[float | None] = []
    for hour in HOURS:
        weighted = 0.0
        total_minutes = 0.0
        for bucket in timeline:
            if not bucket.get("trusted"):
                continue
            start = _parse(bucket.get("start_at"))
            end = _parse(bucket.get("end_at"))
            if not start or not end or end <= start:
                continue
            window_start = start.replace(hour=hour, minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(hours=1)
            overlap_start = max(start, window_start)
            overlap_end = min(end, window_end)
            minutes = max(0.0, (overlap_end - overlap_start).total_seconds() / 60.0)
            if minutes <= 0:
                continue
            weighted += float(bucket.get("activity_score") or 0.0) * minutes
            total_minutes += minutes
        values.append(round((weighted / total_minutes) * 100, 1) if total_minutes else None)
    return values


def _infrastructure_point(
    centre: dict[str, Any],
    cases: list[ComplianceCase],
) -> dict[str, Any]:
    centre_id = str(centre.get("centre_id") or "")
    camera_untrusted = str(centre.get("camera_status") or "").lower() in {"attention", "blocked"}
    active = [
        case for case in cases
        if case.centre_id == centre_id
        and case.case_type == "infrastructure_compliance"
        and case.status.value in ACTIVE_CASE_STATUSES
    ]
    missing_units = 0
    discrepancy_items = 0
    for case in active:
        reported = case.details.get("reported_quantity")
        observed = case.details.get("observed_quantity")
        if isinstance(reported, (int, float)) and isinstance(observed, (int, float)):
            missing_units += max(0, int(reported) - int(observed))
        items = case.details.get("items")
        if isinstance(items, list):
            discrepancy_items += sum(1 for item in items if item.get("state") == "DISCREPANCY")

    return {
        "centre_id": centre_id,
        "name": centre.get("name"),
        "short_name": str(centre.get("name") or centre_id).split(" TC-")[0],
        "case_count": len(active),
        "missing_units": missing_units,
        "discrepancy_items": discrepancy_items,
        "status": "uncertain" if camera_untrusted else "review" if active else "verified",
    }


def build_network_insights(
    *,
    centres: list[dict[str, Any]],
    cases: Iterable[ComplianceCase],
    history: list[dict[str, Any]],
    period: str = "last_7_days",
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    start, end, normalized_period, period_label = _bounds(period, current_time)
    selected_centres = [
        centre for centre in centres
        if str(centre.get("centre_id") or "") in AI_FIRST_CENTRE_IDS
    ]
    order = {centre_id: index for index, centre_id in enumerate(AI_FIRST_CENTRE_IDS)}
    selected_centres.sort(key=lambda item: order.get(str(item.get("centre_id")), 99))

    all_cases = [
        case for case in cases
        if case.centre_id in AI_FIRST_CENTRE_IDS
    ]
    period_history = []
    for row in history:
        if str(row.get("centre_id") or "") not in AI_FIRST_CENTRE_IDS:
            continue
        created = _parse(row.get("created_at"))
        if created and start <= created < end:
            period_history.append(row)

    health_rows = [
        {
            "centre_id": str(centre.get("centre_id") or ""),
            "name": centre.get("name"),
            "short_name": str(centre.get("name") or "").split(" TC-")[0],
            "state": _ui_state(centre),
        }
        for centre in selected_centres
    ]
    health_counts = Counter(row["state"] for row in health_rows)

    attendance = [
        _attendance_point(centre, period_history, all_cases)
        for centre in selected_centres
    ]

    activity = []
    for centre in selected_centres:
        centre_id = str(centre.get("centre_id") or "")
        centre_history = [
            row for row in history
            if str(row.get("centre_id") or "") == centre_id
        ]
        activity_result = build_activity_intelligence(
            centre=centre,
            history=centre_history,
            period=normalized_period,
            now=current_time,
        )
        activity.append({
            "centre_id": centre_id,
            "name": centre.get("name"),
            "short_name": str(centre.get("name") or centre_id).split(" TC-")[0],
            "state": activity_result["state"],
            "values": (
                _hourly_values(activity_result["timeline"])
                if activity_result["state"] == "available"
                else [None for _ in HOURS]
            ),
            "peak": activity_result["summary"]["peak"],
            "lowest": activity_result["summary"]["lowest"],
        })

    infrastructure = [
        _infrastructure_point(centre, all_cases)
        for centre in selected_centres
    ]

    camera = [
        {
            "centre_id": str(centre.get("centre_id") or ""),
            "name": centre.get("name"),
            "short_name": str(centre.get("name") or "").split(" TC-")[0],
            "state": (
                "uncertain"
                if str(centre.get("camera_status") or "").lower() in {"attention", "blocked"}
                else "verified"
                if str(centre.get("camera_status") or "").lower() == "nominal"
                else "unavailable"
            ),
        }
        for centre in selected_centres
    ]

    case_outcomes = Counter(case.status.value for case in all_cases)
    analysis_outcomes = Counter(str(row.get("outcome") or "unknown") for row in period_history)
    analysis_types = Counter(str(row.get("analysis_type") or "unknown") for row in period_history)

    insight_rows: list[dict[str, Any]] = []
    attendance_available = [row for row in attendance if row["available"]]
    if attendance_available:
        largest = max(attendance_available, key=lambda row: int(row["difference"] or 0))
        if int(largest["difference"] or 0) > 0:
            insight_rows.append({
                "title": f"{largest['short_name']} attendance variance",
                "body": f"{largest['difference']} fewer people were observed than reported in the latest trusted comparison.",
                "centre_id": largest["centre_id"],
                "href": f"/centres/{largest['centre_id']}/attendance",
                "kind": "attendance",
            })

    infra_attention = [row for row in infrastructure if row["status"] == "review"]
    if infra_attention:
        strongest = max(infra_attention, key=lambda row: (row["missing_units"], row["case_count"]))
        detail = (
            f"{strongest['missing_units']} units are below the current reported/required quantity."
            if strongest["missing_units"]
            else f"{strongest['case_count']} infrastructure case requires review."
        )
        insight_rows.append({
            "title": f"{strongest['short_name']} infrastructure",
            "body": detail,
            "centre_id": strongest["centre_id"],
            "href": f"/centres/{strongest['centre_id']}/infrastructure",
            "kind": "infrastructure",
        })

    camera_attention = [row for row in camera if row["state"] == "uncertain"]
    if camera_attention:
        item = camera_attention[0]
        insight_rows.append({
            "title": f"{item['short_name']} camera trust",
            "body": "Dependent visual conclusions remain suspended until camera evidence is trusted again.",
            "centre_id": item["centre_id"],
            "href": f"/centres/{item['centre_id']}/evidence",
            "kind": "camera",
        })

    simulated = any(
        bool((row.get("details") or {}).get("simulated"))
        for row in period_history
    ) or any(bool(case.details.get("simulated")) for case in all_cases)

    return {
        "generated_at": current_time.astimezone(LOCAL_TIMEZONE).isoformat(),
        "timezone": "Asia/Kolkata",
        "period": normalized_period,
        "period_label": period_label,
        "grounded": True,
        "simulated": simulated,
        "counts": {
            "total": len(selected_centres),
            "verified": health_counts["verified"],
            "review": health_counts["review"],
            "uncertain": health_counts["uncertain"],
            "unavailable": health_counts["unavailable"],
            "analysis_runs": len(period_history),
        },
        "centre_health": health_rows,
        "attendance": attendance,
        "activity_heatmap": {
            "hours": [f"{hour:02d}:00" for hour in HOURS],
            "rows": activity,
        },
        "infrastructure": infrastructure,
        "camera_trust": camera,
        "analysis_mix": {
            "types": dict(analysis_types),
            "outcomes": dict(analysis_outcomes),
        },
        "case_outcomes": {
            key: case_outcomes[key]
            for key in (
                "open",
                "under_review",
                "virtual_verification",
                "confirmed",
                "false_positive",
                "resolved",
            )
        },
        "insights": insight_rows[:3],
        "report_centres": [
            {
                "centre_id": str(centre.get("centre_id") or ""),
                "name": centre.get("name"),
                "state": _ui_state(centre),
            }
            for centre in selected_centres
        ],
        "decision_policy": "AI surfaces evidence. Officers decide.",
    }
