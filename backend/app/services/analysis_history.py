from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import tempfile
from threading import RLock
from pathlib import Path
from typing import Any


class AnalysisHistoryStore:
    _lock = RLock()

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

    def _save(self, rows: list[dict[str, Any]]) -> None:
        """Single-worker crash-safe JSON replacement, not a DB transaction."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
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

    def append_edge_once(
        self,
        *,
        edge_event_id: str,
        centre_id: str,
        batch_id: str,
        analysis_type: str,
        outcome: str,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retry idempotence across an edge event ledger acknowledgment failure."""
        if not edge_event_id:
            raise ValueError("Edge history requires a unique event ID")
        with self._lock:
            rows = self._read()
            for row in rows:
                if (isinstance(row.get("details"), dict)
                        and row["details"].get("edge_event_id") == edge_event_id):
                    return row
            return self.append(
                centre_id=centre_id, batch_id=batch_id,
                analysis_type=analysis_type, outcome=outcome,
                summary=summary, details={**(details or {}), "edge_event_id": edge_event_id},
            )

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
        with self._lock:
            return self._append_locked(
                centre_id=centre_id, batch_id=batch_id, analysis_type=analysis_type,
                outcome=outcome, summary=summary, details=details,
            )

    def _append_locked(
        self, *, centre_id: str, batch_id: str,
        analysis_type: str, outcome: str, summary: str,
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
        self._save(rows)
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
