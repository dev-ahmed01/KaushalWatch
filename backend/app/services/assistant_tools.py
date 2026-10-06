from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

from app.models import ComplianceCase
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore


# India has used a fixed UTC+05:30 civil offset since 1945. A fixed offset
# keeps server-side period resolution portable on Windows runtimes that do
# not ship the IANA tz database.
LOCAL_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
UNRESOLVED_STATUSES = {"open", "under_review", "virtual_verification"}
RELATIVE_PERIODS = {
    "today", "yesterday", "this_week", "last_week", "last_7_days", "last_30_days"
}
ANALYSIS_DETAIL_KEYS = {
    "reported_attendance", "estimated_occupancy", "discrepancy_pct", "decision",
    "active_work_cells", "peak_stable_workers", "activity_fraction", "detector_backend",
    "detector_authoritative", "detector_failures", "demo_profile", "items",
    "edge_synced", "raw_video_uploaded", "edge_event_id",
}
CASE_DETAIL_KEYS = {
    "camera_id", "camera_trust_score", "reasons", "trusted_sample_ratio",
    "track_confirmation_seconds", "attendance_registration_seconds", "track_grace_seconds",
    "detector_backend", "individual_identification", "authorization",
    "practical_activity_fraction", "active_work_cells", "decision_basis", "job_role",
    "items", "verification_basis", "operational_data_status", "edge_synced",
    "raw_video_uploaded", "edge_event_id", "edge_evidence_integrity",
}
ITEM_KEYS = {
    "id", "label", "required", "observed", "verification_tier", "presence_method",
    "state", "confidence", "samples", "deficit_ratio", "required_persistence_ratio",
}


@dataclass(frozen=True)
class AssistantSource:
    kind: str
    id: str
    label: str
    href: str
    timestamp: str | None = None


@dataclass
class ToolResult:
    data: dict[str, Any]
    sources: list[AssistantSource] = field(default_factory=list)


@dataclass(frozen=True)
class AssistantDataContext:
    history: AnalysisHistoryStore
    cases: CaseStore
    centre_lookup: Callable[[str], dict[str, Any] | None]
    readiness_provider: Callable[[], dict[str, Any]]
    network_brief_provider: Callable[[str], dict[str, Any]] | None = None
    activity_intelligence_provider: Callable[[str, str], dict[str, Any]] | None = None
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=LOCAL_TIMEZONE)


def _period_bounds(
    period: str,
    now: datetime,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime, datetime, str, str]:
    local_now = now.astimezone(LOCAL_TIMEZONE)
    today = local_now.date()

    if start_date or end_date:
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required")
        try:
            start_day = date.fromisoformat(start_date)
            end_day = date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValueError("Dates must use YYYY-MM-DD") from exc
        if end_day < start_day:
            raise ValueError("end_date must be on or after start_date")
        start = _local_midnight(start_day)
        end = _local_midnight(end_day + timedelta(days=1))
        return start, end, start_day.isoformat(), end_day.isoformat()

    normalized = period.lower().strip().replace(" ", "_")
    if normalized not in RELATIVE_PERIODS:
        raise ValueError(
            "period must be one of: " + ", ".join(sorted(RELATIVE_PERIODS))
        )
    if normalized == "today":
        start_day, end_day = today, today
        start, end = _local_midnight(today), local_now + timedelta(microseconds=1)
    elif normalized == "yesterday":
        start_day = end_day = today - timedelta(days=1)
        start, end = _local_midnight(start_day), _local_midnight(today)
    elif normalized == "this_week":
        start_day, end_day = today - timedelta(days=today.weekday()), today
        start, end = _local_midnight(start_day), local_now + timedelta(microseconds=1)
    elif normalized == "last_week":
        current_week = today - timedelta(days=today.weekday())
        start_day, end_day = current_week - timedelta(days=7), current_week - timedelta(days=1)
        start, end = _local_midnight(start_day), _local_midnight(current_week)
    elif normalized in {"last_30_days", "30d"}:
        start_day, end_day = today - timedelta(days=30), today
        start, end = local_now - timedelta(days=30), local_now + timedelta(microseconds=1)
    elif normalized == "last_7_days":
        start_day, end_day = today - timedelta(days=7), today
        start, end = local_now - timedelta(days=7), local_now + timedelta(microseconds=1)
    return start, end, start_day.isoformat(), end_day.isoformat()


def _analysis_source(row: dict[str, Any]) -> AssistantSource:
    centre_id = str(row.get("centre_id") or "")
    label = str(row.get("analysis_type") or "analysis").replace("_", " ").title()
    return AssistantSource(
        kind="analysis",
        id=str(row.get("analysis_id") or ""),
        label=f"{label} analysis",
        timestamp=str(row.get("created_at") or "") or None,
        href=f"/centres/{centre_id}/history",
    )


def _case_source(case: ComplianceCase) -> AssistantSource:
    return AssistantSource(
        kind="case",
        id=case.case_id,
        label=f"{case.case_type.replace('_', ' ').title()} case",
        timestamp=case.created_at,
        href=f"/centres/{case.centre_id}/review",
    )


def _compact_case(case: ComplianceCase) -> dict[str, Any]:
    compact = {
        "case_id": case.case_id,
        "case_type": case.case_type,
        "status": case.status.value,
        "severity": case.severity,
        "summary": case.summary,
        "created_at": case.created_at,
        "reported_attendance": case.reported_attendance,
        "visual_occupancy": case.visual_occupancy,
        "discrepancy_pct": case.discrepancy_pct,
        "persistence_ratio": case.persistence_ratio,
        "camera_trust": case.camera_trust.model_dump(mode="json") if case.camera_trust else None,
        "details": _allowlisted_details(case.details, CASE_DETAIL_KEYS),
    }
    return {key: value for key, value in compact.items() if value is not None}


def _allowlisted_details(details: object, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    result = {key: details[key] for key in allowed if key in details}
    if isinstance(result.get("items"), list):
        result["items"] = [
            {key: item[key] for key in ITEM_KEYS if key in item}
            for item in result["items"][:50]
            if isinstance(item, dict)
        ]
    return result


def _compact_analysis(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "analysis_id": str(row.get("analysis_id") or ""),
        "created_at": row.get("created_at"),
        "batch_id": row.get("batch_id"),
        "analysis_type": row.get("analysis_type"),
        "outcome": row.get("outcome"),
        "summary": row.get("summary"),
        "details": _allowlisted_details(row.get("details"), ANALYSIS_DETAIL_KEYS),
    }


class KaushalToolset:
    def __init__(self, context: AssistantDataContext):
        self.context = context

    def _centre(self, centre_id: str) -> dict[str, Any] | None:
        return self.context.centre_lookup(centre_id)

    def _history_for_period(
        self,
        centre_id: str,
        period: str,
        analysis_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        start, end, start_label, end_label = _period_bounds(
            period, self.context.now_provider(), start_date, end_date
        )
        start_utc, end_utc = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        rows = []
        for row in self.context.history.list(centre_id=centre_id, limit=500):
            created = _parse_timestamp(row.get("created_at"))
            if not created or not start_utc <= created < end_utc:
                continue
            if analysis_type and row.get("analysis_type") != analysis_type:
                continue
            rows.append(row)
        return rows, {
            "period": period,
            "start_date": start_label,
            "end_date": end_label,
            "timezone": "Asia/Kolkata",
        }

    def get_network_brief(self, period: str = "last_7_days") -> ToolResult:
        if self.context.network_brief_provider is None:
            return ToolResult({"available": False, "reason": "Network briefing is unavailable."})
        data = self.context.network_brief_provider(period)
        sources = [
            AssistantSource(
                "centre",
                str(item.get("centre_id") or ""),
                str(item.get("name") or item.get("centre_id") or "Centre"),
                str(item.get("href") or f"/centres/{item.get('centre_id')}"),
                data.get("generated_at"),
            )
            for item in data.get("centres", [])
            if item.get("centre_id")
        ]
        return ToolResult({"available": True, **data}, sources)

    def get_activity_intelligence(
        self,
        centre_id: str,
        period: str = "yesterday",
    ) -> ToolResult:
        if self.context.activity_intelligence_provider is None:
            return ToolResult({"available": False, "reason": "Activity intelligence is unavailable."})
        data = self.context.activity_intelligence_provider(centre_id, period)
        return ToolResult(
            {"available": True, **data},
            [
                AssistantSource(
                    "centre",
                    centre_id,
                    f"{centre_id} activity intelligence",
                    f"/centres/{centre_id}/practical",
                    data.get("generated_at"),
                )
            ],
        )

    def get_centre_overview(self, centre_id: str) -> ToolResult:
        centre = self._centre(centre_id)
        if not centre:
            return ToolResult({"available": False, "centre_id": centre_id})
        allowed = {
            key: centre.get(key)
            for key in (
                "centre_id", "name", "batch_id", "job_role", "attendance_status",
                "practical_status", "infrastructure_status", "camera_status",
                "analysis_count", "pending_cases", "confirmed_cases", "last_analysis",
                "verification_complete", "escalation",
            )
        }
        return ToolResult(
            {"available": True, **allowed},
            [AssistantSource("centre", centre_id, str(centre.get("name") or centre_id), f"/centres/{centre_id}", centre.get("last_analysis"))],
        )

    def get_runtime_readiness(self, centre_id: str) -> ToolResult:
        return ToolResult(
            self.context.readiness_provider(),
            [AssistantSource("readiness", "runtime", "Runtime readiness", f"/centres/{centre_id}/analysis")],
        )

    def get_operational_history(
        self,
        centre_id: str,
        period: str = "last_7_days",
        analysis_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ToolResult:
        rows, period_data = self._history_for_period(
            centre_id, period, analysis_type, start_date, end_date
        )
        outcomes = Counter(str(row.get("outcome") or "unknown") for row in rows)
        types = Counter(str(row.get("analysis_type") or "unknown") for row in rows)
        return ToolResult(
            {
                "available": bool(rows),
                "count": len(rows),
                **period_data,
                "outcomes": dict(outcomes),
                "analysis_types": dict(types),
                "analyses": [_compact_analysis(row) for row in rows],
            },
            [_analysis_source(row) for row in rows],
        )

    def get_analysis_details(self, centre_id: str, analysis_id: str) -> ToolResult:
        row = next(
            (
                item
                for item in self.context.history.list(centre_id=centre_id, limit=500)
                if item.get("analysis_id") == analysis_id
            ),
            None,
        )
        if not row:
            return ToolResult({"available": False, "analysis_id": analysis_id})
        return ToolResult(
            {"available": True, "analysis": _compact_analysis(row)},
            [_analysis_source(row)],
        )

    def _cases_for_period(
        self, centre_id: str, period_data: dict[str, Any]
    ) -> list[ComplianceCase]:
        start = _local_midnight(date.fromisoformat(period_data["start_date"])).astimezone(timezone.utc)
        end = _local_midnight(date.fromisoformat(period_data["end_date"]) + timedelta(days=1)).astimezone(timezone.utc)
        return [
            case for case in self.context.cases.list()
            if case.centre_id == centre_id
            and (created := _parse_timestamp(case.created_at)) is not None
            and start <= created < end
        ]

    def get_attendance_summary(
        self,
        centre_id: str,
        period: str = "last_7_days",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ToolResult:
        rows, period_data = self._history_for_period(
            centre_id, period, "attendance", start_date, end_date
        )
        cases = [
            case for case in self._cases_for_period(centre_id, period_data)
            if case.case_type == "attendance_discrepancy"
        ]
        return ToolResult(
            {
                "available": bool(rows or cases),
                **period_data,
                "worker_identity_available": False,
                "identity_note": "Attendance uses anonymous short-lived tracks; named worker identity is not retained.",
                "analyses": [_compact_analysis(row) for row in rows],
                "cases": [_compact_case(case) for case in cases],
            },
            [_analysis_source(row) for row in rows] + [_case_source(case) for case in cases],
        )

    def get_practical_work_summary(
        self,
        centre_id: str,
        period: str = "last_7_days",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ToolResult:
        rows, period_data = self._history_for_period(
            centre_id, period, "practical_work", start_date, end_date
        )
        cases = [
            case for case in self._cases_for_period(centre_id, period_data)
            if case.case_type.startswith("practical_activity")
        ]
        return ToolResult(
            {
                "available": bool(rows or cases),
                **period_data,
                "limitation": "Visual motion is an activity proxy, not proof of task quality or worker identity.",
                "analyses": [_compact_analysis(row) for row in rows],
                "cases": [_compact_case(case) for case in cases],
            },
            [_analysis_source(row) for row in rows] + [_case_source(case) for case in cases],
        )

    def get_escalations(
        self,
        centre_id: str,
        status: str = "unresolved",
        severity: str | None = None,
    ) -> ToolResult:
        centre = self._centre(centre_id)
        if not centre:
            return ToolResult({"available": False, "centre_id": centre_id})
        cases = [case for case in self.context.cases.list() if case.centre_id == centre_id]
        if status == "unresolved":
            cases = [case for case in cases if case.status.value in UNRESOLVED_STATUSES]
        elif status != "all":
            cases = [case for case in cases if case.status.value == status]
        if severity:
            cases = [case for case in cases if case.severity == severity]
        cases.sort(key=lambda case: case.created_at, reverse=True)
        return ToolResult(
            {
                "available": bool(cases),
                "escalation": centre.get("escalation"),
                "cases": [_compact_case(case) for case in cases],
            },
            [_case_source(case) for case in cases],
        )

    def get_case_evidence(self, centre_id: str, case_id: str) -> ToolResult:
        case = self.context.cases.get(case_id)
        if not case or case.centre_id != centre_id:
            return ToolResult({"available": False, "case_id": case_id})
        evidence = [
            {
                "evidence_id": item.evidence_id,
                "created_at": item.created_at,
                "possible_duplicate": item.duplicate_of is not None,
                "duplicate_of": item.duplicate_of,
                "camera_id": item.metadata.get("camera_id"),
                "second": item.metadata.get("second"),
            }
            for item in case.evidence
        ]
        sources = [_case_source(case)] + [
            AssistantSource(
                "evidence",
                item.evidence_id,
                f"Evidence {item.evidence_id}",
                f"/centres/{centre_id}/review",
                item.created_at,
            )
            for item in case.evidence
        ]
        return ToolResult(
            {
                "available": True,
                "case": {
                    **_compact_case(case),
                    "review_history": case.review_history,
                },
                "evidence": evidence,
                "decision_policy": "AI evidence supports human review; final action remains a human decision.",
            },
            sources,
        )
