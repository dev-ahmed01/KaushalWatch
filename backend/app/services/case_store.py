from __future__ import annotations
import json
import os
import tempfile
from threading import RLock
from datetime import datetime, timezone
from pathlib import Path
from app.models import ComplianceCase, CaseStatus


ALLOWED_CASE_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.open: {
        CaseStatus.under_review,
        CaseStatus.virtual_verification,
    },
    CaseStatus.under_review: {
        CaseStatus.virtual_verification,
        CaseStatus.confirmed,
        CaseStatus.false_positive,
        CaseStatus.resolved,
    },
    CaseStatus.virtual_verification: {
        CaseStatus.under_review,
        CaseStatus.confirmed,
        CaseStatus.false_positive,
        CaseStatus.resolved,
    },
    CaseStatus.confirmed: set(),
    CaseStatus.false_positive: set(),
    CaseStatus.resolved: set(),
}


class CaseStore:
    # Process-wide lock also protects separate CaseStore instances pointing
    # to the same JSON file under a single-worker SIH demo process. This is
    # deliberately NOT a cross-process transaction or pilot datastore.
    _lock = RLock()

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def list(self) -> list[ComplianceCase]:
        with self._lock:
            return [ComplianceCase.model_validate(x) for x in self._load()]

    def save(self, case: ComplianceCase) -> ComplianceCase:
        with self._lock:
            rows = [r for r in self._load() if r["case_id"] != case.case_id]
            rows.append(case.model_dump(mode="json"))
            # Write a complete replacement next to the destination first.
            # An interrupted write must not truncate the existing case ledger.
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.path.parent,
                    prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    json.dump(rows, handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, self.path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            return case

    def save_if_absent(self, case: ComplianceCase) -> bool:
        """Atomically accept a new edge case only if the ID is not present.

        Uses the same lock as update_status: an edge replay cannot overwrite
        an officer's transition even if both requests race in this worker.
        This is NOT a cross-process uniqueness guarantee.
        """
        with self._lock:
            if any(row.get("case_id") == case.case_id for row in self._load()):
                return False
            self.save(case)
            return True

    def get(self, case_id: str) -> ComplianceCase | None:
        return next((c for c in self.list() if c.case_id == case_id), None)

    def update_status(
        self,
        case_id: str,
        status: CaseStatus,
        note: str | None = None,
        actor: str = "prototype_officer",
    ) -> ComplianceCase | None:
        with self._lock:
            case = self.get(case_id)
            if not case:
                return None
            previous_status = case.status
            if status == previous_status:
                return case
            allowed = ALLOWED_CASE_TRANSITIONS.get(previous_status, set())
            if status not in allowed:
                raise ValueError(
                    f"Invalid case transition: {previous_status.value} -> {status.value}"
                )
            previous = previous_status.value
            case.status = status
            case.review_history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "from_status": previous,
                "to_status": status.value,
                "note": note,
            })
            return self.save(case)
