from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class AnalysisHistoryStore:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def append(
        self,
        *,
        centre_id: str,
        batch_id: str,
        analysis_type: str,
        outcome: str,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rows = self._read()
        row = {
            "analysis_id": f"AN-{len(rows)+1:06d}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "centre_id": centre_id,
            "batch_id": batch_id,
            "analysis_type": analysis_type,
            "outcome": outcome,
            "summary": summary,
            "details": details or {},
        }
        rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return row

    def list(
        self,
        *,
        centre_id: str | None = None,
        batch_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = self._read()
        if centre_id:
            rows = [row for row in rows if row.get("centre_id") == centre_id]
        if batch_id:
            rows = [row for row in rows if row.get("batch_id") == batch_id]
        return list(reversed(rows[-max(1, limit):]))
