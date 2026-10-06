from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.models import CaseStatus, ComplianceCase


LOCAL_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

CASE_TO_ANALYSIS = {
    "attendance_discrepancy": "attendance",
    "infrastructure_compliance": "infrastructure",
    "practical_activity_authorization": "practical_work",
    "practical_activity_authorization_review": "practical_work",
    "camera_integrity": None,
    "evidence_integrity": None,
}

ACTION_LABELS = {
    CaseStatus.under_review: "Start review",
    CaseStatus.confirmed: "Confirm discrepancy",
    CaseStatus.false_positive: "False positive",
    CaseStatus.virtual_verification: "Request virtual verification",
    CaseStatus.resolved: "Resolve",
}

ALLOWED_ACTIONS = {
    CaseStatus.open: [CaseStatus.under_review, CaseStatus.virtual_verification],
    CaseStatus.under_review: [
        CaseStatus.confirmed,
        CaseStatus.false_positive,
        CaseStatus.virtual_verification,
        CaseStatus.resolved,
    ],
    CaseStatus.virtual_verification: [
        CaseStatus.under_review,
        CaseStatus.confirmed,
        CaseStatus.false_positive,
        CaseStatus.resolved,
    ],
    CaseStatus.confirmed: [],
    CaseStatus.false_positive: [],
    CaseStatus.resolved: [],
}


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE)


def _timeline_state(outcome: object) -> str:
    normalized = str(outcome or "").lower()
    if normalized in {"attention", "discrepancy", "miss"}:
        return "miss"
    if normalized in {"blocked", "uncertain"}:
        return "uncertain"
    return "ok"


def _seeded_temporal_points(case: ComplianceCase) -> list[dict[str, Any]]:
    raw = case.details.get("temporal_points")
    if not isinstance(raw, list):
        return []
    points = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        state = str(item.get("state") or "").strip().lower()
        if not label or state not in {"ok", "miss", "uncertain"}:
            continue
        points.append({
            "label": label,
            "state": state,
            "note": str(item.get("note") or "").strip() or None,
        })
    return points[:6]


def _history_temporal_points(
    case: ComplianceCase,
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    analysis_type = CASE_TO_ANALYSIS.get(case.case_type)
    if not analysis_type:
        return []
    relevant = [
        row for row in history
        if row.get("analysis_type") == analysis_type
        and str(row.get("centre_id") or "") == case.centre_id
    ]
    relevant.sort(key=lambda row: str(row.get("created_at") or ""))
    points = []
    for row in relevant[-6:]:
        created = _parse(row.get("created_at"))
        points.append({
            "label": created.strftime("%H:%M") if created else "Recorded",
            "state": _timeline_state(row.get("outcome")),
            "note": str(row.get("summary") or "").strip() or None,
        })
    return points


def _facts(case: ComplianceCase) -> list[dict[str, str]]:
    if case.case_type == "attendance_discrepancy":
        reported = case.reported_attendance
        observed = case.visual_occupancy
        facts = [
            {
                "label": "Reported",
                "value": str(reported) if reported is not None else "Unavailable",
                "note": "Centre attendance record",
            },
            {
                "label": "Observed",
                "value": str(observed) if observed is not None else "Unavailable",
                "note": "Sustained anonymous visual presence",
            },
        ]
        if reported is not None and observed is not None:
            difference = reported - observed
            facts.append({
                "label": "Difference",
                "value": str(abs(difference)),
                "note": "Review signal only; not an automatic compliance outcome",
            })
        return facts

    if case.case_type == "infrastructure_compliance":
        reported = case.details.get("reported_quantity")
        observed = case.details.get("observed_quantity")
        if reported is not None or observed is not None:
            return [
                {
                    "label": "Reported / required",
                    "value": str(reported) if reported is not None else "Unavailable",
                    "note": "Prototype manifest/centre record",
                },
                {
                    "label": "Observed",
                    "value": str(observed) if observed is not None else "Unavailable",
                    "note": "Camera-verifiable reviewed quantity",
                },
            ]
        items = case.details.get("items")
        if isinstance(items, list):
            discrepancies = [item for item in items if item.get("state") == "DISCREPANCY"]
            return [
                {
                    "label": "Items needing review",
                    "value": str(len(discrepancies)),
                    "note": "Camera-verifiable manifest exceptions",
                }
            ]

    if case.case_type.startswith("practical_activity"):
        authorization = case.details.get("authorization")
        fraction = case.details.get("practical_activity_fraction")
        return [
            {
                "label": "Authorization",
                "value": str(authorization or "Unknown").replace("_", " ").title(),
                "note": "External schedule/work-order state",
            },
            {
                "label": "Visual activity",
                "value": f"{float(fraction) * 100:.0f}%" if isinstance(fraction, (int, float)) else "Observed",
                "note": "Worker-centric visual activity proxy",
            },
        ]

    if case.case_type == "camera_integrity":
        score = case.details.get("camera_trust_score")
        return [
            {
                "label": "Camera trust",
                "value": f"{score}" if score is not None else "Insufficient",
                "note": "Dependent compliance conclusions are suspended",
            }
        ]

    return [
        {
            "label": "Case signal",
            "value": case.severity.upper(),
            "note": "Evidence requires officer interpretation",
        }
    ]


def _integrity(case: ComplianceCase) -> dict[str, Any]:
    items = []
    duplicate_count = 0
    for evidence in case.evidence:
        possible_duplicate = evidence.duplicate_of is not None
        if possible_duplicate:
            duplicate_count += 1
        items.append({
            "evidence_id": evidence.evidence_id,
            "created_at": evidence.created_at,
            "sha256": evidence.sha256,
            "perceptual_hash": evidence.perceptual_hash,
            "possible_duplicate": possible_duplicate,
            "duplicate_of": evidence.duplicate_of,
            "metadata": evidence.metadata,
        })

    return {
        "state": "review" if duplicate_count else "verified" if items else "unavailable",
        "retained_count": len(items),
        "possible_duplicate_count": duplicate_count,
        "checks": {
            "sha256_retained": bool(items) and all(bool(item["sha256"]) for item in items),
            "duplicate_review_clear": bool(items) and duplicate_count == 0,
            "camera_trust": (
                "trusted"
                if case.camera_trust and case.camera_trust.trusted
                else "untrusted"
                if case.camera_trust and not case.camera_trust.trusted
                else "not_recorded"
            ),
        },
        "items": items,
    }


def build_evidence_review_pack(
    *,
    case: ComplianceCase,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    temporal_points = _seeded_temporal_points(case) or _history_temporal_points(case, history)
    persistence_text = str(case.details.get("temporal_proof") or "").strip()
    if not persistence_text:
        if len(temporal_points) >= 2:
            misses = sum(1 for point in temporal_points if point["state"] == "miss")
            uncertain = sum(1 for point in temporal_points if point["state"] == "uncertain")
            if misses >= 2:
                persistence_text = "The discrepancy persisted across multiple recorded analysis periods."
            elif uncertain:
                persistence_text = "Temporal conclusion was limited by uncertain evidence."
            else:
                persistence_text = "No persistent discrepancy was recorded across the available points."
        else:
            persistence_text = "Not enough timestamped analysis points are available to establish persistence."

    allowed = ALLOWED_ACTIONS.get(case.status, [])
    return {
        "prototype": True,
        "case": case.model_dump(mode="json"),
        "facts": _facts(case),
        "temporal_proof": {
            "points": temporal_points,
            "summary": persistence_text,
            "rule": "A single frame never creates a case.",
        },
        "integrity": _integrity(case),
        "review": {
            "status": case.status.value,
            "terminal": case.status in {
                CaseStatus.confirmed,
                CaseStatus.false_positive,
                CaseStatus.resolved,
            },
            "allowed_actions": [
                {
                    "action": action.value,
                    "label": ACTION_LABELS[action],
                    "note_required": action in {
                        CaseStatus.confirmed,
                        CaseStatus.false_positive,
                        CaseStatus.resolved,
                    },
                }
                for action in allowed
            ],
            "history": list(reversed(case.review_history)),
        },
        "decision_policy": "AI surfaces evidence. Officers decide.",
        "privacy_note": "Track position, not identity. No face recognition is used.",
    }
