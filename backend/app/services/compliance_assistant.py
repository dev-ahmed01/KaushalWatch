from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models import ComplianceCase


def _period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "today":
        return now - timedelta(days=1)
    if period == "yesterday":
        return now - timedelta(days=2)
    if period == "30d":
        return now - timedelta(days=30)
    return now - timedelta(days=7)


def _period_for_question(question: str, fallback: str) -> str:
    q = question.lower()
    if "today" in q:
        return "today"
    if "yesterday" in q:
        return "yesterday"
    if any(token in q for token in ("month", "30 day", "30-day")):
        return "30d"
    if any(token in q for token in ("week", "7 day", "7-day")):
        return "7d"
    return fallback


def _in_period(row: dict[str, Any], period: str) -> bool:
    try:
        created = datetime.fromisoformat(str(row.get("created_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return True
    return created >= _period_start(period)


def answer_question(
    *,
    question: str,
    centre: dict[str, Any],
    cases: list[ComplianceCase],
    history: list[dict[str, Any]],
    period: str = "7d",
) -> dict[str, Any]:
    q = question.lower().strip()
    period = _period_for_question(question, period)
    period_rows = [row for row in history if _in_period(row, period)]
    pending = [
        case for case in cases
        if case.status.value in {"open", "under_review", "virtual_verification"}
    ]
    counts = Counter(row.get("analysis_type") for row in period_rows)
    outcomes = Counter(row.get("outcome") for row in period_rows)

    if any(token in q for token in ("week", "last 7", "summary", "happened", "today", "yesterday", "month")):
        answer = (
            f"{centre['name']} had {len(period_rows)} recorded analyses in the selected period. "
            f"{outcomes.get('compliant', 0)} completed without an exception and "
            f"{len(pending)} case{'s' if len(pending) != 1 else ''} currently need human attention."
        )
        if counts:
            answer += (
                f" Checks recorded: attendance {counts.get('attendance', 0)}, "
                f"practical work {counts.get('practical_work', 0)}, "
                f"infrastructure {counts.get('infrastructure', 0)}."
            )
    elif "attendance" in q:
        latest = next((row for row in period_rows if row.get("analysis_type") == "attendance"), None)
        answer = latest.get("summary") if latest else (
            "I do not have a recorded attendance analysis for this centre in the selected period."
        )
    elif any(token in q for token in ("infrastructure", "missing", "equipment")):
        latest = next((row for row in period_rows if row.get("analysis_type") == "infrastructure"), None)
        answer = latest.get("summary") if latest else (
            "I do not have a recorded infrastructure analysis for this centre in the selected period."
        )
    elif any(token in q for token in ("practical", "work zone", "activity")):
        latest = next((row for row in period_rows if row.get("analysis_type") == "practical_work"), None)
        answer = latest.get("summary") if latest else (
            "I do not have a recorded practical-work analysis for this centre in the selected period."
        )
    elif any(token in q for token in ("escalat", "attention", "problem", "issue")):
        escalation = centre.get("escalation", {})
        reasons = ", ".join(escalation.get("reasons", []))
        answer = (
            f"Current escalation level is {escalation.get('label', 'Normal')}. "
            f"{reasons or 'No escalation trigger is active.'}"
        )
    elif "camera" in q:
        answer = (
            "Camera integrity is treated as a gate. If imagery is too dark, blurred, frozen, "
            "or shifted, KaushalWatch withholds the affected compliance conclusion instead of "
            "pretending the result is reliable."
        )
    elif any(token in q for token in ("privacy", "face", "identify")):
        answer = (
            "KaushalWatch does not use face recognition for these compliance checks. "
            "Attendance uses anonymous short-lived tracks and exception evidence is privacy-minimised."
        )
    else:
        answer = (
            f"For {centre['name']}, I can explain attendance, practical work, infrastructure, "
            "camera integrity, escalation status, recent analyses, or help prepare a report. "
            "Ask in simple language."
        )

    return {
        "answer": answer,
        "period": period,
        "grounded_in": {
            "history_rows": len(period_rows),
            "pending_cases": len(pending),
            "centre_id": centre["centre_id"],
        },
        "suggested_actions": [
            "Show recent incidents",
            "Summarise the last 7 days",
            "Explain current escalation",
            "Generate report",
        ],
    }
