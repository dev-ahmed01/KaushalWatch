"""Measured application-byte sync with privacy and durable local delivery state.

All metrics are observed UTF-8 request/response BODY bytes; they do not
pretend to measure HTTPS/TCP headers, real WAN latency or cloud savings.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from app.services.edge_ingest import normalize_event

MAX_EVENT_BATCH = 200
MAX_BATCH_BYTES = 1_000_000


def prepare_upload(events: list[dict]) -> tuple[bytes, str]:
    """Canonicalize BEFORE transport; never transmit raw image/identity fields."""
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENT_BATCH:
        raise ValueError("Offline sync batch must hold 1..200 events")
    safe, centres = [], set()
    identifiers = set()
    for entry in events:
        normalized, rejected = normalize_event(entry)
        if normalized is None:
            raise ValueError("Local event refused before sending: " + rejected)
        if normalized["event_id"] in identifiers:
            raise ValueError("Duplicate event ID in one offline batch")
        identifiers.add(normalized["event_id"])
        centres.add(normalized["payload"]["centre_id"])
        safe.append(normalized)
    # One transport request is scoped to ONE centre. Mixed-centre queues must
    # use separate per-centre devices/queues, not an opportunistic broadcast.
    if len(centres) != 1:
        raise ValueError("Cross-centre batching prohibited")
    data = json.dumps({"events": safe}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_BATCH_BYTES:
        raise ValueError("Oversized private edge metadata batch")
    return data, next(iter(centres))


def state_file(queue_path: Path) -> Path:
    return Path(str(queue_path) + ".sync-state.json")


def read_sync_state(queue_path: Path) -> dict:
    target = state_file(queue_path)
    initial = {
        "schema": "KW_EDGE_SYNC_METRICS_V1",
        "attempts": 0, "failures": 0, "acknowledged_total": 0,
        "duplicate_acks_total": 0, "observed_request_body_bytes": 0,
        "observed_response_body_bytes": 0,
        "last_attempt_utc": None, "last_success_utc": None,
        "last_error_code": None,
    }
    if not target.is_file():
        return initial
    parsed = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or set(parsed) != set(initial) or parsed["schema"] != initial["schema"]:
        raise ValueError("Untrusted local sync state")
    for key in ("attempts","failures","acknowledged_total","duplicate_acks_total",
                "observed_request_body_bytes","observed_response_body_bytes"):
        if type(parsed[key]) is not int or parsed[key] < 0:
            raise ValueError("Corrupt local sync metrics")
    return parsed


def record_sync_attempt(queue_path: Path, *, acknowledged: int = 0, duplicates: int = 0,
                        request_bytes: int = 0, response_bytes: int = 0,
                        error_code: str | None = None) -> dict:
    """Write-before-return with atomic replace; totals survive edge restarts."""
    state = read_sync_state(queue_path)
    now = datetime.now(timezone.utc).isoformat()
    state["attempts"] += 1
    state["last_attempt_utc"] = now
    if error_code:
        if error_code not in {"offline", "rejected_locally", "invalid_ack", "http_error"}:
            raise ValueError("Unknown transport failure state")
        state["failures"] += 1
        state["last_error_code"] = error_code
    else:
        if any(type(x) is not int or x < 0 for x in
               (acknowledged, duplicates, request_bytes, response_bytes)):
            raise ValueError("Invalid measured transport metrics")
        state["acknowledged_total"] += acknowledged
        state["duplicate_acks_total"] += duplicates
        state["observed_request_body_bytes"] += request_bytes
        state["observed_response_body_bytes"] += response_bytes
        state["last_success_utc"] = now
        state["last_error_code"] = None
    target = state_file(queue_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                dir=target.parent, prefix=f".{target.name}.",
                suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return state
