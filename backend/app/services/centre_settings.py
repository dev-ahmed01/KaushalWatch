from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS = {
    "automatic_analysis": True,
    "frequency": "every_training_day",
    "monitoring_windows": ["09:00-11:00", "14:00-16:00"],
    "connectivity_mode": "low_bandwidth",
    "escalation_rules": {
        "repeated_attendance_days": 3,
        "unresolved_case_days": 3,
        "multi_signal_escalation": True,
        "duplicate_evidence_escalation": True,
    },
}


class CentreSettingsStore:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, centre_id: str) -> dict[str, Any]:
        rows = self._read()
        return {**DEFAULT_SETTINGS, **rows.get(centre_id, {})}

    def save(self, centre_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._read()
        rows[centre_id] = {**self.get(centre_id), **payload}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return rows[centre_id]
