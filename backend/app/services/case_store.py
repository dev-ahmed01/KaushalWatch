from __future__ import annotations
import json
from pathlib import Path
from app.models import ComplianceCase, CaseStatus


class CaseStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def list(self) -> list[ComplianceCase]:
        return [ComplianceCase.model_validate(x) for x in self._load()]

    def save(self, case: ComplianceCase) -> ComplianceCase:
        rows = [r for r in self._load() if r["case_id"] != case.case_id]
        rows.append(case.model_dump(mode="json"))
        self.path.write_text(json.dumps(rows, indent=2))
        return case

    def get(self, case_id: str) -> ComplianceCase | None:
        return next((c for c in self.list() if c.case_id == case_id), None)

    def update_status(self, case_id: str, status: CaseStatus) -> ComplianceCase | None:
        case = self.get(case_id)
        if not case:
            return None
        case.status = status
        return self.save(case)
