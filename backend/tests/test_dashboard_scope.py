import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main
from app.models import ComplianceCase, CaseStatus
from app.services.case_store import CaseStore


def _case(case_id: str, centre: str, batch: str, status: CaseStatus) -> ComplianceCase:
    return ComplianceCase(
        case_id=case_id,
        centre_id=centre,
        batch_id=batch,
        case_type="attendance_discrepancy",
        severity="medium",
        summary="test",
        status=status,
    )


def test_dashboard_scope_filters_active_centre_and_batch(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases.json")
    store.save(_case("C1-PENDING", "CENTRE-A", "BATCH-1", CaseStatus.open))
    store.save(_case("C1-DONE", "CENTRE-A", "BATCH-1", CaseStatus.confirmed))
    store.save(_case("C2-PENDING", "CENTRE-B", "BATCH-2", CaseStatus.open))

    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "DATA", tmp_path)

    scoped = main.dashboard("CENTRE-A", "BATCH-1")

    assert scoped["scope"] == {
        "centre_id": "CENTRE-A",
        "batch_id": "BATCH-1",
        "is_filtered": True,
    }
    assert scoped["open_cases"] == 1
    assert scoped["global_open_cases"] == 2
    assert scoped["resolved_cases"] == 1
    assert [row["case_id"] for row in scoped["pending_cases"]] == ["C1-PENDING"]
    assert [row["case_id"] for row in scoped["resolved_case_history"]] == ["C1-DONE"]


def test_dashboard_without_scope_returns_all_cases(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases.json")
    store.save(_case("A", "CENTRE-A", "BATCH-1", CaseStatus.open))
    store.save(_case("B", "CENTRE-B", "BATCH-2", CaseStatus.open))

    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "DATA", tmp_path)

    dashboard = main.dashboard()

    assert dashboard["scope"]["is_filtered"] is False
    assert dashboard["open_cases"] == 2
    assert dashboard["global_open_cases"] == 2
