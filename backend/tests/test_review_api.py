import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as app_main
from app.models import ComplianceCase
from app.services.case_store import CaseStore


def test_final_review_decision_requires_officer_note(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases.json")
    store.save(
        ComplianceCase(
            case_id="CASE-REVIEW-NOTE",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-DEMO-01",
            case_type="infrastructure_compliance",
            severity="medium",
            summary="demo case",
        )
    )
    monkeypatch.setattr(app_main, "STORE", store)
    client = TestClient(app_main.app)

    missing = client.post(
        "/api/cases/CASE-REVIEW-NOTE/review",
        json={"action": "confirmed"},
    )
    assert missing.status_code == 422
    assert "review note is required" in missing.json()["detail"].lower()

    started = client.post(
        "/api/cases/CASE-REVIEW-NOTE/review",
        json={
            "action": "under_review",
            "note": "Evidence inspection started.",
        },
    )
    assert started.status_code == 200
    assert started.json()["status"] == "under_review"

    decided = client.post(
        "/api/cases/CASE-REVIEW-NOTE/review",
        json={
            "action": "confirmed",
            "note": "Reviewed evidence and confirmed the persistent gap.",
        },
    )
    assert decided.status_code == 200
    body = decided.json()
    assert body["status"] == "confirmed"
    assert body["review_history"][-1]["note"] == (
        "Reviewed evidence and confirmed the persistent gap."
    )
