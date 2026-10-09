"""Single-worker prototype safety boundary for offline edge telemetry.

Edge input is untrusted telemetry, NEVER an officer instruction, signed
authorization, or verified camera-compliance truth. Store only bounded fields.
"""
from __future__ import annotations

import re
from typing import Any

EVENT_ID = re.compile(r"^EDGE-[A-Za-z0-9-]{4,90}$")
SAFE_DETAILS = frozenset({
    "decision", "detector_backend", "detector_authoritative", "detector_failures",
    "reported_attendance", "estimated_occupancy", "discrepancy_pct",
    "trusted_sample_ratio", "mismatch_persistence_ratio", "vision_profile_id",
    "camera_id", "camera_trust_score", "reasons", "simulated", "visibility",
    "individual_identification", "raw_video_uploaded", "operational_data_status",
})
CASE_TYPES = frozenset({
    "camera_integrity", "attendance_discrepancy",
    "practical_activity_authorization", "practical_activity_authorization_review",
    "infrastructure_compliance",
})
DECISION_OUTCOME = {
    "compliant": "compliant",
    "attendance_exception": "attention",
    "camera_evidence_insufficient": "blocked",
    "detector_unavailable": "blocked",
}


def _text(value: Any, *, max_length: int = 600) -> str:
    return str(value)[:max_length] if isinstance(value, str) else ""


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    if type(value) in (float, int) and -1e9 < value < 1e9:
        return value
    return None


def _safe_details(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    kept: dict[str, Any] = {}
    for key in SAFE_DETAILS:
        v = value.get(key)
        if key in {"simulated", "detector_authoritative", "individual_identification", "raw_video_uploaded"}:
            if type(v) is bool:
                kept[key] = v
        elif key in {"detector_failures", "reported_attendance", "estimated_occupancy"}:
            if type(v) is int and 0 <= v < 1_000_000:
                kept[key] = v
        elif key in {"camera_trust_score", "discrepancy_pct", "trusted_sample_ratio",
                     "mismatch_persistence_ratio"}:
            number = _number(v)
            if number is not None:
                kept[key] = number
        elif key == "reasons":
            if isinstance(v, list):
                kept[key] = [_text(s, max_length=100) for s in v[:8] if isinstance(s, str)]
        elif isinstance(v, str):
            kept[key] = _text(v, max_length=160)
    # Edge cannot authenticate identity or privacy state.
    kept.pop("individual_identification", None)
    kept.pop("raw_video_uploaded", None)
    return kept


def normalize_event(event: Any) -> tuple[dict[str, Any] | None, str]:
    """Return (privacy-safe event, rejection code).

    Reject unknown, raw-video-bearing and non-serializable messages. Data
    that is safe but unverified is explicitly labelled as such.
    """
    if not isinstance(event, dict):
        return None, "invalid_event"
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not EVENT_ID.fullmatch(event_id):
        return None, "invalid_event_id"
    kind = event.get("event_type")
    if not isinstance(kind, str) or kind not in {"analysis_summary", "compliance_case"}:
        return None, "unsupported_event_type"
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None, "invalid_payload"
    privacy = payload.get("privacy")
    if privacy is not None and (
        not isinstance(privacy, dict)
        or privacy.get("raw_video_included") is not False
        or privacy.get("face_embeddings", False) is not False
        or privacy.get("individual_identification", False) is not False
    ):
        return None, "unsafe_privacy_claim"
    for key in ("raw_video", "video", "frames", "images", "face_embeddings", "identity_records"):
        if key in payload:
            return None, "raw_or_identity_data_not_accepted"

    centre, batch = payload.get("centre_id"), payload.get("batch_id")
    if not isinstance(centre, str) or not centre.strip() or len(centre) > 128:
        return None, "invalid_centre"
    if not isinstance(batch, str) or not batch.strip() or len(batch) > 128:
        return None, "invalid_batch"
    common = {"centre_id": centre, "batch_id": batch}
    if kind == "analysis_summary":
        if payload.get("analysis_type") != "attendance":
            return None, "unsupported_analysis"
        details = _safe_details(payload.get("details"))
        decision = details.get("decision")
        authoritative = details.get("detector_authoritative") is True
        trusted = details.get("trusted_sample_ratio")
        # No camera ratio or explicit successful detector: no clean result.
        expected_outcome = DECISION_OUTCOME.get(decision, "blocked")
        failures = details.get("detector_failures")
        if expected_outcome == "compliant" and (
            not authoritative or failures != 0 or not isinstance(trusted, (int, float))
            or not 0.5 <= trusted <= 1.0
        ):
            expected_outcome = "blocked"
        if expected_outcome == "attention" and not authoritative:
            expected_outcome = "blocked"
        canonical_payload = {
            **common,
            "analysis_type": "attendance",
            "outcome": expected_outcome,
            "summary": (
                _text(payload.get("summary"), max_length=600)
                if expected_outcome != "blocked"
                else "Edge attendance evaluation blocked or unverified; officer review required."
            ),
            "details": {
                **details,
                "edge_reported_outcome_unverified": _text(payload.get("outcome"), max_length=32),
                "edge_outcome_normalized": expected_outcome,
            },
            "privacy": {"raw_video_included": False, "individual_identification": False},
        }
    else:
        case_id = payload.get("case_id")
        case_type = payload.get("case_type")
        if (not isinstance(case_id, str) or not 1 <= len(case_id) <= 100
                or not re.fullmatch(r"[A-Za-z0-9_-]+", case_id)):
            return None, "invalid_case_id"
        if not isinstance(case_type, str) or case_type not in CASE_TYPES:
            return None, "unsupported_case_type"
        severity = payload.get("severity")
        if not isinstance(severity, str) or severity not in {"low", "medium", "high", "critical"}:
            return None, "invalid_severity"
        evidence = payload.get("evidence_integrity") or []
        if not isinstance(evidence, list) or len(evidence) > 40:
            return None, "invalid_evidence_digests"
        safe_evidence = []
        for item in evidence:
            if not isinstance(item, dict):
                return None, "invalid_evidence_digests"
            sha = item.get("sha256")
            if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
                return None, "invalid_evidence_digests"
            safe_evidence.append({
                "evidence_id": _text(item.get("evidence_id"), max_length=100),
                "sha256": sha.lower(),
            })
        canonical_payload = {
            **common,
            "case_id": case_id,
            "case_type": case_type,
            "severity": severity,
            "summary": _text(payload.get("summary"), max_length=600),
            "status": _text(payload.get("status") or "open", max_length=32),
            "created_at": _text(payload.get("created_at"), max_length=48),
            "reported_attendance": _number(payload.get("reported_attendance")),
            "visual_occupancy": _number(payload.get("visual_occupancy")),
            "discrepancy_pct": _number(payload.get("discrepancy_pct")),
            "persistence_ratio": _number(payload.get("persistence_ratio")),
            "details": _safe_details(payload.get("details")),
            "evidence_integrity": safe_evidence,
            "privacy": {"raw_video_included": False, "individual_identification": False},
        }
    return {
        "event_id": event_id,
        "event_type": kind,
        "created_at": _text(event.get("created_at"), max_length=48),
        "payload": canonical_payload,
    }, ""
