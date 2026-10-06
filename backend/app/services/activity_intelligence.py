from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


LOCAL_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE)


def _period_bounds(period: str, now: datetime) -> tuple[datetime, datetime, str, str]:
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


def _minutes(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 60.0)


def _label(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


def _extract_buckets(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for row in history:
        if row.get("analysis_type") != "practical_work":
            continue
        details = row.get("details") or {}
        raw = details.get("activity_buckets")
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            start = _parse(item.get("start_at"))
            end = _parse(item.get("end_at"))
            if not start or not end or end <= start:
                continue
            try:
                score = float(item.get("activity_score"))
                trusted_ratio = float(item.get("trusted_frame_ratio", 0.0))
                active_cells = int(item.get("active_work_cells", 0))
            except (TypeError, ValueError):
                continue
            buckets.append({
                "analysis_id": row.get("analysis_id"),
                "start": start,
                "end": end,
                "activity_score": min(1.0, max(0.0, score)),
                "trusted_frame_ratio": min(1.0, max(0.0, trusted_ratio)),
                "active_work_cells": max(0, active_cells),
                "simulated": bool(item.get("simulated", details.get("simulated", False))),
                "source": str(item.get("source") or "scheduled_practical_analysis"),
            })
    return buckets


def _merge_adjacent_low_periods(buckets: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    low = [item for item in buckets if item["activity_score"] <= threshold]
    low.sort(key=lambda item: item["start"])
    merged: list[dict[str, Any]] = []
    for item in low:
        if not merged:
            merged.append(dict(item))
            continue
        previous = merged[-1]
        gap = (item["start"] - previous["end"]).total_seconds() / 60.0
        if gap <= 15:
            previous_duration = _minutes(previous["start"], previous["end"])
            item_duration = _minutes(item["start"], item["end"])
            total_duration = previous_duration + item_duration
            if total_duration > 0:
                previous["activity_score"] = (
                    previous["activity_score"] * previous_duration
                    + item["activity_score"] * item_duration
                ) / total_duration
            previous["end"] = max(previous["end"], item["end"])
            previous["trusted_frame_ratio"] = min(
                previous["trusted_frame_ratio"], item["trusted_frame_ratio"]
            )
            previous["active_work_cells"] = max(
                previous["active_work_cells"], item["active_work_cells"]
            )
            previous["simulated"] = previous["simulated"] or item["simulated"]
        else:
            merged.append(dict(item))
    return merged


def build_activity_intelligence(
    *,
    centre: dict[str, Any],
    history: list[dict[str, Any]],
    period: str = "yesterday",
    now: datetime | None = None,
    minimum_trusted_ratio: float = 0.50,
    low_activity_threshold: float = 0.25,
    follow_up_minutes: float = 30.0,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    start, end, normalized_period, period_label = _period_bounds(period, current_time)
    centre_id = str(centre.get("centre_id") or "")
    camera_state = str(centre.get("camera_status") or "").lower()
    camera_trusted = camera_state not in {"attention", "blocked"}

    all_buckets = _extract_buckets(history)
    selected = [
        item for item in all_buckets
        if item["start"] < end and item["end"] > start
    ]
    selected.sort(key=lambda item: item["start"])
    trusted = [
        item for item in selected
        if item["trusted_frame_ratio"] >= minimum_trusted_ratio
    ]

    if not camera_trusted:
        state = "uncertain"
        explanation = "Camera trust is insufficient, so activity conclusions are suspended."
    elif not selected:
        state = "unavailable"
        explanation = "No time-bucketed practical activity evidence is available for this period."
    elif not trusted:
        state = "uncertain"
        explanation = "Activity samples exist, but none meet the trusted-frame requirement."
    else:
        state = "available"
        explanation = "Activity is aggregated from trusted scheduled practical-analysis buckets."

    peak = max(trusted, key=lambda item: item["activity_score"]) if trusted else None
    low = min(trusted, key=lambda item: item["activity_score"]) if trusted else None

    low_periods = _merge_adjacent_low_periods(trusted, low_activity_threshold)
    longest_low = (
        max(low_periods, key=lambda item: _minutes(item["start"], item["end"]))
        if low_periods
        else None
    )
    longest_low_minutes = (
        _minutes(longest_low["start"], longest_low["end"]) if longest_low else 0.0
    )

    follow_up = {
        "recommended": False,
        "title": "No centre-head follow-up suggested",
        "reason": "No trusted sustained low-activity period crossed the follow-up threshold.",
        "action_label": "No action",
    }
    if state == "available" and longest_low and longest_low_minutes >= follow_up_minutes:
        follow_up = {
            "recommended": True,
            "title": "Confirm the low-activity period with the Centre Head",
            "reason": (
                f"Trusted activity stayed low for about {int(round(longest_low_minutes))} minutes "
                f"({_label(longest_low['start'], longest_low['end'])}). "
                "KaushalAI cannot determine whether this was a scheduled break, class transition, "
                "or interruption from vision alone."
            ),
            "action_label": "Contact Centre Head",
        }
    elif state == "uncertain":
        follow_up = {
            "recommended": False,
            "title": "Restore evidence trust first",
            "reason": explanation,
            "action_label": "Verify camera evidence",
        }
    elif state == "unavailable":
        follow_up = {
            "recommended": False,
            "title": "Collect scheduled activity evidence first",
            "reason": explanation,
            "action_label": "Run analysis",
        }

    timeline = [
        {
            "start_at": item["start"].isoformat(),
            "end_at": item["end"].isoformat(),
            "label": _label(item["start"], item["end"]),
            "activity_score": round(item["activity_score"], 4),
            "activity_percent": round(item["activity_score"] * 100, 1),
            "trusted_frame_ratio": round(item["trusted_frame_ratio"], 4),
            "active_work_cells": item["active_work_cells"],
            "trusted": item["trusted_frame_ratio"] >= minimum_trusted_ratio,
            "simulated": item["simulated"],
            "source": item["source"],
        }
        for item in selected
    ]

    return {
        "generated_at": current_time.astimezone(LOCAL_TIMEZONE).isoformat(),
        "timezone": "Asia/Kolkata",
        "period": normalized_period,
        "period_label": period_label,
        "grounded": True,
        "simulated": any(item["simulated"] for item in selected),
        "centre_id": centre_id,
        "state": state,
        "explanation": explanation,
        "thresholds": {
            "minimum_trusted_ratio": minimum_trusted_ratio,
            "low_activity_threshold": low_activity_threshold,
            "follow_up_minutes": follow_up_minutes,
        },
        "summary": {
            "bucket_count": len(selected),
            "trusted_bucket_count": len(trusted),
            "peak": (
                {
                    "label": _label(peak["start"], peak["end"]),
                    "activity_score": round(peak["activity_score"], 4),
                    "activity_percent": round(peak["activity_score"] * 100, 1),
                    "active_work_cells": peak["active_work_cells"],
                }
                if peak else None
            ),
            "lowest": (
                {
                    "label": _label(low["start"], low["end"]),
                    "activity_score": round(low["activity_score"], 4),
                    "activity_percent": round(low["activity_score"] * 100, 1),
                    "active_work_cells": low["active_work_cells"],
                }
                if low else None
            ),
            "longest_low_period": (
                {
                    "label": _label(longest_low["start"], longest_low["end"]),
                    "minutes": round(longest_low_minutes, 1),
                    "activity_score": round(longest_low["activity_score"], 4),
                }
                if longest_low else None
            ),
        },
        "timeline": timeline,
        "follow_up": follow_up,
        "interpretation_boundary": (
            "Activity is a visual worker-motion/work-cell proxy. It does not measure productivity, "
            "training quality, skill, or individual performance."
        ),
        "decision_policy": "AI surfaces evidence. Officers decide.",
    }


def activity_bucket_for_practical_run(
    *,
    start_at: datetime,
    duration_sec: float,
    activity_score: float,
    trusted_frame_ratio: float,
    active_work_cells: int,
) -> dict[str, Any]:
    start = start_at.astimezone(LOCAL_TIMEZONE)
    duration = max(1.0, float(duration_sec))
    end = start + timedelta(seconds=duration)
    return {
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "activity_score": round(min(1.0, max(0.0, float(activity_score))), 4),
        "trusted_frame_ratio": round(min(1.0, max(0.0, float(trusted_frame_ratio))), 4),
        "active_work_cells": max(0, int(active_work_cells)),
        "simulated": False,
        "source": "live_practical_analysis",
    }
