import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

import app.main as app_main
from app.services.activity_intelligence import activity_bucket_for_practical_run
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


def test_bengaluru_activity_intelligence_finds_peak_low_and_follow_up(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get(
        "/api/centres/DEMO-KA-104/activity-intelligence?period=yesterday"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["simulated"] is True
    assert payload["state"] == "available"
    assert payload["summary"]["bucket_count"] == 7
    assert payload["summary"]["trusted_bucket_count"] == 7
    assert payload["summary"]["peak"]["label"] == "10:45–12:00"
    assert payload["summary"]["peak"]["activity_percent"] == 91.0
    assert payload["summary"]["lowest"]["label"] == "14:00–14:45"
    assert payload["summary"]["lowest"]["activity_percent"] == 18.0
    assert payload["summary"]["longest_low_period"]["minutes"] == 45.0
    assert payload["follow_up"]["recommended"] is True
    assert payload["follow_up"]["action_label"] == "Contact Centre Head"
    assert "scheduled break" in payload["follow_up"]["reason"]


def test_steady_activity_does_not_trigger_centre_head_follow_up(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get(
        "/api/centres/DEMO-KA-112/activity-intelligence?period=yesterday"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["follow_up"]["recommended"] is False
    assert payload["summary"]["lowest"]["activity_percent"] == 58.0


def test_untrusted_camera_suspends_activity_conclusions(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get(
        "/api/centres/DEMO-KA-207/activity-intelligence?period=yesterday"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "uncertain"
    assert payload["summary"]["trusted_bucket_count"] == 0
    assert payload["summary"]["peak"] is None
    assert payload["follow_up"]["recommended"] is False
    assert payload["follow_up"]["action_label"] == "Verify camera evidence"


def test_live_practical_bucket_preserves_real_duration_and_trust():
    start = datetime(2026, 10, 6, 4, 30, tzinfo=timezone.utc)

    bucket = activity_bucket_for_practical_run(
        start_at=start,
        duration_sec=600,
        activity_score=0.64,
        trusted_frame_ratio=0.92,
        active_work_cells=3,
    )

    start_at = datetime.fromisoformat(bucket["start_at"])
    end_at = datetime.fromisoformat(bucket["end_at"])
    assert (end_at - start_at) == timedelta(minutes=10)
    assert bucket["activity_score"] == 0.64
    assert bucket["trusted_frame_ratio"] == 0.92
    assert bucket["active_work_cells"] == 3
    assert bucket["simulated"] is False


def test_activity_intelligence_rejects_unknown_period(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get(
        "/api/centres/DEMO-KA-104/activity-intelligence?period=quarter"
    )

    assert response.status_code == 422
    assert "period must be one of" in response.json()["detail"]
