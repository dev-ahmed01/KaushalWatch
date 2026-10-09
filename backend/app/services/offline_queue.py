from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import tempfile
from threading import RLock
from pathlib import Path
import uuid
from typing import Any


class EdgeEventQueue:
    """Durable single-process edge queue; not a multi-agent message broker."""

    _lock = RLock()

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("Edge queue must be a JSON array")
        return rows

    def _save(self, rows: list[dict[str, Any]]) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(rows, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def enqueue(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_id": f"EDGE-{uuid.uuid4().hex[:10].upper()}",
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with self._lock:
            rows = self._load()
            rows.append(event)
            self._save(rows)
        return event

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load()

    def acknowledge(self, event_ids: list[str]) -> int:
        ids = {value for value in event_ids if isinstance(value, str)}
        with self._lock:
            rows = self._load()
            remaining = [row for row in rows if row.get("event_id") not in ids]
            removed = len(rows) - len(remaining)
            if removed:
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
