"""Atomic JSON event acknowledgements in the single-worker SIH prototype.

This is not a distributed transaction with CaseStore/AnalysisHistoryStore,
nor a replacement for PostgreSQL when using multiple server processes.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock


class EdgeEventLedger:
    _lock = RLock()

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        result = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(result, list):
            raise ValueError("Edge event ledger must contain a JSON array")
        return result

    def save(self, rows: list[dict]) -> None:
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
