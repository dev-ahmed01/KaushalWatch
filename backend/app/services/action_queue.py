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
ACTIONABLE_CASE_STATUSES = {"open", "under_review", "virtual_verification"}

SEVERITY_SCORE = {
    "critical": 90,
    "high": 75,
    "medium": 60,
    "low": 40,
}
STATUS_SCORE = {
    "open": 0,
    "under_review": 8,
    "virtual_verification": 12,
}


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days(case: ComplianceCase, now: datetime) -> int:
    created = _parse(case.created_at)
    if not created:
        return 0
    return max(0, int((now.astimezone(timezone.utc) - created).total_seconds() // 86400))


def _priority(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _case_action_copy(case: ComplianceCase) -> tuple[str, str, str]:
    if case.case_type == "attendance_discrepancy":
        return (
            "attendance",
            "Review attendance evidence",
            "Open case",
        )
    if case.case_type == "infrastructure_compliance":
        return (
            "infrastructure",
            "Review infrastructure exception",
            "Open case",
        )
    if case.case_type == "camera_integrity":
        return (
            "camera",
            "Verify camera evidence",
            "Open case",
        )
    if case.case_type.startswith("practical_activity"):
        return (
            "practical",
            "Review practical activity evidence",
            "Open case",
        )
    if case.case_type == "evidence_integrity":
        return (
            "evidence",
            "Review evidence integrity",
            "Open case",
        )
    return (
        "case",
        "Review evidence-backed case",
        "Open case",
    )


def _case_score(
    case: ComplianceCase,
    centre: dict[str, Any],
    age_days: int,
) -> tuple[int, list[str]]:
    severity = str(case.severity or "low").lower()
    status = case.status.value
    escalation = centre.get("escalation") or {}
    escalation_level = int(escalation.get("level") or 0)

    score = SEVERITY_SCORE.get(severity, 40)
    score += STATUS_SCORE.get(status, 0)
    score += escalation_level * 10
    score += min(20, age_days * 3)

    basis = [f"{severity.title()} severity"]
    if age_days:
        basis.append(f"{age_days} day{'s' if age_days != 1 else ''} open")
    if escalation_level:
        basis.append(str(escalation.get("label") or f"Escalation level {escalation_level}"))
    if status == "under_review":
        basis.append("Officer review started")
    elif status == "virtual_verification":
        basis.append("Virtual verification pending")

    if case.case_type == "camera_integrity":
        score += 30
        basis.append("Blocks dependent visual conclusions")

    return score, basis


def _case_reason(case: ComplianceCase) -> str:
    if case.case_type == "attendance_discrepancy":
        if case.reported_attendance is not None and case.visual_occupancy is not None:
            return (
                f"{case.reported_attendance} reported vs {case.visual_occupancy} observed; "
                "the retained discrepancy needs an officer decision."
            )
    if case.case_type == "infrastructure_compliance":
        reported = case.details.get("reported_quantity")
        observed = case.details.get("observed_quantity")
        if reported is not None and observed is not None:
            return (
                f"{observed} observed against {reported} reported/required; "
                "the persistent infrastructure exception needs review."
            )
    if case.case_type == "camera_integrity":
        return (
            "Camera trust is insufficient, so attendance, activity, and infrastructure "
            "conclusions remain suspended."
        )
    return case.summary


def build_action_queue(
    *,
    centres: list[dict[str, Any]],
    cases: Iterable[ComplianceCase],
    history: list[dict[str, Any]],
    period: str = "yesterday",
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    centre_by_id = {
        str(centre.get("centre_id") or ""): centre
        for centre in centres
        if str(centre.get("centre_id") or "") in AI_FIRST_CENTRE_IDS
    }
    all_cases = [
        case for case in cases
        if case.centre_id in AI_FIRST_CENTRE_IDS
    ]

    actions: list[dict[str, Any]] = []

    for case in all_cases:
        if case.status.value not in ACTIONABLE_CASE_STATUSES:
            continue
        centre = centre_by_id.get(case.centre_id)
        if not centre:
            continue
        age_days = _age_days(case, current_time)
        score, basis = _case_score(case, centre, age_days)
        kind, title, cta = _case_action_copy(case)
        actions.append({
            "action_id": f"case:{case.case_id}",
            "source": "case",
            "kind": kind,
            "priority": _priority(score),
            "score": score,
            "centre_id": case.centre_id,
            "centre_name": centre.get("name"),
            "title": title,
            "reason": _case_reason(case),
            "href": f"/cases/{case.case_id}",
            "cta": cta,
            "case_id": case.case_id,
            "case_status": case.status.value,
            "severity": str(case.severity),
            "age_days": age_days,
            "escalation_level": int((centre.get("escalation") or {}).get("level") or 0),
            "escalation_label": str((centre.get("escalation") or {}).get("label") or "Normal"),
            "evidence_basis": basis,
            "simulated": bool(case.details.get("simulated")),
        })

    history_by_centre: dict[str, list[dict[str, Any]]] = {}
    for row in history:
        centre_id = str(row.get("centre_id") or "")
        if centre_id in centre_by_id:
            history_by_centre.setdefault(centre_id, []).append(row)

    for centre_id, centre in centre_by_id.items():
        activity = build_activity_intelligence(
            centre=centre,
            history=history_by_centre.get(centre_id, []),
            period=period,
            now=current_time,
        )
        if not activity["follow_up"]["recommended"]:
            continue
        escalation_level = int((centre.get("escalation") or {}).get("level") or 0)
        score = 55 + escalation_level * 5
        longest = activity["summary"].get("longest_low_period") or {}
        minutes = int(round(float(longest.get("minutes") or 0)))
        basis = [
            "Trusted activity evidence",
            f"{minutes} minute low-activity period" if minutes else "Sustained low activity",
        ]
        if escalation_level:
            basis.append(str((centre.get("escalation") or {}).get("label") or "Centre escalation"))
        actions.append({
            "action_id": f"activity:{centre_id}:{activity['period']}",
            "source": "activity",
            "kind": "activity_follow_up",
            "priority": _priority(score),
            "score": score,
            "centre_id": centre_id,
            "centre_name": centre.get("name"),
            "title": "Confirm low-activity context",
            "reason": activity["follow_up"]["reason"],
            "href": f"/centres/{centre_id}/practical",
            "cta": "View activity",
            "case_id": None,
            "case_status": None,
            "severity": None,
            "age_days": 0,
            "escalation_level": escalation_level,
            "escalation_label": str((centre.get("escalation") or {}).get("label") or "Normal"),
            "evidence_basis": basis,
            "simulated": bool(activity.get("simulated")),
        })

    actions.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item["centre_name"] or ""),
            str(item["action_id"]),
        )
    )

    mix = Counter(str(item["priority"]) for item in actions)
    centres_with_actions = len({str(item["centre_id"]) for item in actions})
    camera_blockers = sum(1 for item in actions if item["kind"] == "camera")

    top = actions[0] if actions else None
    if top:
        headline = f"Start with {top['centre_name']}: {top['title'].lower()}."
        summary = top["reason"]
    else:
        headline = "No officer action is currently queued."
        summary = "Latest trusted evidence does not require an operational follow-up."

    simulated = any(bool(item["simulated"]) for item in actions)

    return {
        "generated_at": current_time.astimezone(LOCAL_TIMEZONE).isoformat(),
        "timezone": "Asia/Kolkata",
        "period": period,
        "grounded": True,
        "simulated": simulated,
        "headline": headline,
        "summary": summary,
        "counts": {
            "total": len(actions),
            "high": mix["high"],
            "medium": mix["medium"],
            "low": mix["low"],
            "centres": centres_with_actions,
            "camera_blockers": camera_blockers,
        },
        "top_action": top,
        "actions": actions,
        "scope_note": (
            "Unresolved cases stay in the queue regardless of date selection. "
            "Activity follow-ups use the selected period."
        ),
        "decision_policy": "AI surfaces evidence. Officers decide.",
    }
