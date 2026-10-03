from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any


class EdgeEventQueue:
    """Small durable prototype queue for compliance telemetry when the centre is offline."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(rows, indent=2))

    def enqueue(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_id": f"EDGE-{uuid.uuid4().hex[:10].upper()}",
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        rows = self._load()
        rows.append(event)
        self._save(rows)
        return event

    def pending(self) -> list[dict[str, Any]]:
        return self._load()

    def acknowledge(self, event_ids: list[str]) -> int:
        ids = set(event_ids)
        rows = self._load()
        remaining = [row for row in rows if row.get("event_id") not in ids]
        removed = len(rows) - len(remaining)
        self._save(remaining)
        return removed


def json_payload_bytes(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def bandwidth_measurement(
    raw_video_bytes: int,
    events: list[dict[str, Any]],
    evidence_bytes: int = 0,
) -> dict[str, Any]:
    telemetry_bytes = json_payload_bytes(events)
    transmitted = telemetry_bytes + max(0, evidence_bytes)
    reduction = (
        0.0
        if raw_video_bytes <= 0
        else max(0.0, 1.0 - transmitted / raw_video_bytes) * 100.0
    )
    return {
        "raw_video_bytes": raw_video_bytes,
        "telemetry_bytes": telemetry_bytes,
        "evidence_bytes": evidence_bytes,
        "transmitted_bytes": transmitted,
        "estimated_transfer_reduction_pct": round(reduction, 3),
        "note": "Prototype byte comparison; excludes protocol/TLS overhead.",
    }
