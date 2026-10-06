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


def test_network_insights_uses_grounded_five_centre_state(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/insights?period=last_7_days")

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["simulated"] is True
    assert payload["counts"] == {
        "total": 5,
        "verified": 2,
        "review": 2,
        "uncertain": 1,
        "unavailable": 0,
        "analysis_runs": 15,
    }
    assert len(payload["centre_health"]) == 5
    assert payload["period_label"] == "Last 7 days"


def test_attendance_and_camera_charts_do_not_invent_blocked_values(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    payload = client.get("/api/insights?period=last_7_days").json()
    attendance = {row["centre_id"]: row for row in payload["attendance"]}

    assert attendance["DEMO-KA-104"]["reported"] == 28
    assert attendance["DEMO-KA-104"]["observed"] == 19
    assert attendance["DEMO-KA-104"]["difference"] == 9
    assert attendance["DEMO-KA-104"]["status"] == "review"

    assert attendance["DEMO-KA-112"]["reported"] == 24
    assert attendance["DEMO-KA-112"]["observed"] == 23
    assert attendance["DEMO-KA-509"]["reported"] == 18
    assert attendance["DEMO-KA-509"]["observed"] == 18

    assert attendance["DEMO-KA-207"]["available"] is False
    assert attendance["DEMO-KA-207"]["reported"] is None
    assert attendance["DEMO-KA-207"]["observed"] is None
    assert attendance["DEMO-KA-207"]["status"] == "uncertain"

    camera = {row["centre_id"]: row for row in payload["camera_trust"]}
    assert camera["DEMO-KA-207"]["state"] == "uncertain"


def test_activity_heatmap_uses_trusted_time_buckets_and_suspends_tumakuru(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    payload = client.get("/api/insights?period=last_7_days").json()
    assert payload["activity_heatmap"]["hours"] == [
        "09:00",
        "10:00",
        "11:00",
        "12:00",
        "13:00",
        "14:00",
        "15:00",
    ]
    rows = {row["centre_id"]: row for row in payload["activity_heatmap"]["rows"]}

    bengaluru = rows["DEMO-KA-104"]
    assert bengaluru["state"] == "available"
    assert bengaluru["values"][0] == 54.0
    assert bengaluru["values"][2] == 91.0
    assert bengaluru["values"][5] == 30.0

    tumakuru = rows["DEMO-KA-207"]
    assert tumakuru["state"] == "uncertain"
    assert tumakuru["values"] == [None, None, None, None, None, None, None]


def test_infrastructure_and_insight_cards_are_case_grounded(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    payload = client.get("/api/insights?period=last_7_days").json()
    infrastructure = {
        row["centre_id"]: row
        for row in payload["infrastructure"]
    }

    assert infrastructure["DEMO-KA-303"]["status"] == "review"
    assert infrastructure["DEMO-KA-303"]["missing_units"] == 3
    assert any(
        insight["kind"] == "attendance"
        and insight["centre_id"] == "DEMO-KA-104"
        for insight in payload["insights"]
    )
    assert any(
        insight["kind"] == "infrastructure"
        and insight["centre_id"] == "DEMO-KA-303"
        for insight in payload["insights"]
    )
    assert any(
        insight["kind"] == "camera"
        and insight["centre_id"] == "DEMO-KA-207"
        for insight in payload["insights"]
    )


def test_network_insights_rejects_unknown_period(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/insights?period=quarter")

    assert response.status_code == 422
    assert "period must be one of" in response.json()["detail"]
