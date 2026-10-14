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
    return TestClient(app_main.app)


def test_bengaluru_centre_intelligence_surfaces_attendance_review(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/centres/DEMO-KA-104/intelligence?period=last_7_days")

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["simulated"] is True
    assert payload["centre"]["name"] == "Bengaluru TC-04"
    assert payload["brief"]["headline"] == "Attendance needs officer attention."

    engines = {item["key"]: item for item in payload["engines"]}
    assert len(engines) == 6
    assert engines["attendance"]["state"] == "review"
    assert "28 reported" in engines["attendance"]["summary"]
    assert engines["practical_activity"]["state"] == "verified"
    assert engines["camera_integrity"]["state"] == "verified"
    assert engines["apparent_operability"]["state"] == "unavailable"

    assert payload["actions"][0]["title"] == "Review attendance evidence"
    assert payload["contact"]["available"] is False
    assert payload["period_activity"]["analysis_runs"] == 3


def test_camera_trust_suspends_dependent_centre_engines(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/centres/DEMO-KA-207/intelligence?period=last_7_days")

    assert response.status_code == 200
    payload = response.json()
    engines = {item["key"]: item for item in payload["engines"]}

    assert payload["brief"]["headline"] == "Camera trust is limiting this centre's conclusions."
    assert engines["camera_integrity"]["state"] == "uncertain"
    assert engines["attendance"]["state"] == "uncertain"
    assert engines["practical_activity"]["state"] == "uncertain"
    assert engines["infrastructure"]["state"] == "uncertain"
    assert engines["apparent_operability"]["state"] == "uncertain"
    assert payload["actions"][0]["title"] == "Verify camera evidence"


def test_centre_intelligence_rejects_unknown_period(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/centres/DEMO-KA-104/intelligence?period=quarter")

    assert response.status_code == 422
    assert "period must be one of" in response.json()["detail"]
