import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

import app.main as app_main
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.centre_settings import CentreSettingsStore
from scripts.prepare_demo_state import prepare_demo_state


def _client(tmp_path, monkeypatch):
    data = tmp_path / "data"
    prepare_demo_state(data)
    store = CaseStore(data / "cases.json")
    history = AnalysisHistoryStore(data / "analysis_history.json")
    settings = CentreSettingsStore(data / "centre_settings.json")
    monkeypatch.setattr(app_main, "STORE", store)
    monkeypatch.setattr(app_main, "HISTORY", history)
    monkeypatch.setattr(app_main, "CENTRE_SETTINGS", settings)
    monkeypatch.setattr(app_main, "DATA", data)
    return TestClient(app_main.app), store


def test_attendance_evidence_pack_unifies_facts_temporal_integrity_and_review(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    response = client.get("/api/cases/SIM-KA-104-ATT/evidence-pack")

    assert response.status_code == 200
    payload = response.json()
    assert payload["prototype"] is True
    assert payload["case"]["case_id"] == "SIM-KA-104-ATT"
    assert payload["facts"][0]["label"] == "Reported"
    assert payload["facts"][0]["value"] == "28"
    assert payload["facts"][1]["label"] == "Observed"
    assert payload["facts"][1]["value"] == "19"
    assert payload["facts"][2]["label"] == "Difference"
    assert payload["facts"][2]["value"] == "9"

    temporal = payload["temporal_proof"]
    assert [point["label"] for point in temporal["points"]] == ["10:30", "11:15", "12:00"]
    assert [point["state"] for point in temporal["points"]] == ["ok", "miss", "miss"]
    assert temporal["rule"] == "A single frame never creates a case."

    integrity = payload["integrity"]
    assert integrity["retained_count"] == 1
    assert integrity["state"] == "verified"
    assert integrity["checks"]["sha256_retained"] is True
    assert integrity["checks"]["duplicate_review_clear"] is True

    review = payload["review"]
    assert review["status"] == "open"
    assert review["terminal"] is False
    assert {item["action"] for item in review["allowed_actions"]} == {
        "under_review",
        "virtual_verification",
    }


def test_duplicate_evidence_pack_requires_integrity_review(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    response = client.get("/api/cases/SIM-KA-104-DUP/evidence-pack")

    assert response.status_code == 200
    integrity = response.json()["integrity"]
    assert integrity["state"] == "review"
    assert integrity["possible_duplicate_count"] == 1
    assert integrity["checks"]["duplicate_review_clear"] is False
    assert integrity["items"][0]["duplicate_of"] == "SIM-EV-KA104-01"


def test_simulated_officer_review_persists_through_backend(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)

    start = client.post(
        "/api/cases/SIM-KA-104-ATT/review",
        json={"action": "under_review", "note": "Officer opened the evidence review."},
    )
    assert start.status_code == 200

    confirm = client.post(
        "/api/cases/SIM-KA-104-ATT/review",
        json={"action": "confirmed", "note": "Trusted evidence confirms the attendance gap."},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"
    assert len(confirm.json()["review_history"]) == 2

    persisted = store.get("SIM-KA-104-ATT")
    assert persisted is not None
    assert persisted.status.value == "confirmed"
    assert len(persisted.review_history) == 2

    reread = client.get("/api/cases/SIM-KA-104-ATT/evidence-pack")
    assert reread.status_code == 200
    assert reread.json()["review"]["status"] == "confirmed"
    assert reread.json()["review"]["terminal"] is True
    assert len(reread.json()["review"]["history"]) == 2
