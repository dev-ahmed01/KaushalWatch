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



def test_demo_reset_requires_confirmation_and_clears_only_generated_state(
    tmp_path,
    monkeypatch,
):
    data = tmp_path / "data"
    evidence = data / "evidence"
    evidence.mkdir(parents=True)
    store = CaseStore(data / "cases.json")
    store.save(
        ComplianceCase(
            case_id="CASE-DEMO-RESET",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-DEMO-01",
            case_type="camera_integrity",
            severity="medium",
            summary="demo case",
        )
    )
    (data / "edge_events.json").write_text('[{"event_id":"EDGE-1"}]')
    (data / "evidence_index.json").write_text("[]")
    (evidence / "EV-DEMO.jpg").write_bytes(b"demo")
    source_asset = tmp_path / "source-video.mp4"
    source_asset.write_bytes(b"source")

    monkeypatch.setattr(app_main, "DATA", data)
    monkeypatch.setattr(app_main, "EVIDENCE", evidence)
    monkeypatch.setattr(app_main, "STORE", store)
    client = TestClient(app_main.app)

    denied = client.post("/api/demo/reset", json={"confirm": False})
    assert denied.status_code == 400
    assert source_asset.exists()

    reset = client.post("/api/demo/reset", json={"confirm": True})
    assert reset.status_code == 200
    body = reset.json()
    assert body["cases_cleared"] == 1
    assert body["evidence_files_cleared"] == 1
    assert not (data / "cases.json").exists()
    assert not (data / "edge_events.json").exists()
    assert not (data / "evidence_index.json").exists()
    assert list(evidence.glob("*.jpg")) == []
    assert source_asset.exists()
