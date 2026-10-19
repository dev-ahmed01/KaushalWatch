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


def test_action_queue_is_evidence_ranked_and_contains_no_healthy_filler(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    response = client.get("/api/actions?period=yesterday")

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["simulated"] is True
    assert payload["counts"]["total"] == 4
    assert payload["counts"]["centres"] == 3
    assert payload["counts"]["camera_blockers"] == 1

    actions = payload["actions"]
    assert [item["centre_id"] for item in actions] == [
        "DEMO-KA-303",
        "DEMO-KA-207",
        "DEMO-KA-104",
        "DEMO-KA-104",
    ]
    assert actions[0]["title"] == "Review infrastructure exception"
    assert actions[0]["priority"] == "high"
    assert actions[0]["case_id"] == "SIM-KA-303-INF"
    assert "4 days open" in actions[0]["evidence_basis"]
    assert "Regional escalation" in actions[0]["evidence_basis"]

    assert actions[1]["title"] == "Verify camera evidence"
    assert actions[1]["priority"] == "high"
    assert "Blocks dependent visual conclusions" in actions[1]["evidence_basis"]

    assert actions[2]["title"] == "Review attendance evidence"
    assert actions[2]["case_id"] == "SIM-KA-104-ATT"

    assert actions[3]["kind"] == "activity_follow_up"
    assert actions[3]["title"] == "Confirm low-activity context"
    assert "45 minute low-activity period" in actions[3]["evidence_basis"]

    assert all(item["centre_id"] not in {"DEMO-KA-112", "DEMO-KA-509"} for item in actions)


def test_action_queue_today_keeps_cases_but_drops_period_activity_follow_up(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    payload = client.get("/api/actions?period=today").json()

    assert payload["counts"]["total"] == 3
    assert all(item["source"] == "case" for item in payload["actions"])
    assert payload["scope_note"].startswith("Unresolved cases stay in the queue")


def test_reviewed_case_changes_queue_state_without_hardcoded_page_data(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    start = client.post(
        "/api/cases/SIM-KA-104-ATT/review",
        json={"action": "under_review", "note": "Officer started review."},
    )
    assert start.status_code == 200

    payload = client.get("/api/actions?period=yesterday").json()
    attendance = next(
        item for item in payload["actions"]
        if item.get("case_id") == "SIM-KA-104-ATT"
    )
    assert attendance["case_status"] == "under_review"
    assert "Officer review started" in attendance["evidence_basis"]

    confirm = client.post(
        "/api/cases/SIM-KA-104-ATT/review",
        json={"action": "confirmed", "note": "Evidence confirms the discrepancy."},
    )
    assert confirm.status_code == 200

    payload = client.get("/api/actions?period=yesterday").json()
    assert all(item.get("case_id") != "SIM-KA-104-ATT" for item in payload["actions"])


def test_action_queue_rejects_unknown_period(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    response = client.get("/api/actions?period=quarter")

    assert response.status_code == 422
    assert "period must be one of" in response.json()["detail"]


def test_provisioned_real_centre_is_included_in_action_queue():
    from app.services.action_queue import build_action_queue
    from app.services.demo_network import centre_rows
    from app.models import ComplianceCase, CaseStatus
    from datetime import datetime, timezone
    original=centre_rows([])[0]
    real={**original,"centre_id":"SITE-KA-001","name":"Approved pilot site"}
    case=ComplianceCase(
        case_id="REAL-SITE-CASE-001",centre_id="SITE-KA-001",
        batch_id=real["batch_id"],case_type="attendance_discrepancy",
        status=CaseStatus.open,severity="medium",summary="Centre-only attendance review"
    )
    result=build_action_queue(
        centres=[real],cases=[case],history=[],
        period="last_7_days",now=datetime(2026,10,19,tzinfo=timezone.utc))
    assert result["counts"]["total"]==1
    assert result["actions"][0]["case_id"]=="REAL-SITE-CASE-001"
    assert result["actions"][0]["centre_id"]=="SITE-KA-001"


def test_action_queue_does_not_include_ungranted_real_centre():
    from app.services.action_queue import build_action_queue
    from app.services.demo_network import centre_rows
    from app.models import ComplianceCase
    from datetime import datetime, timezone
    permitted={**centre_rows([])[0],"centre_id":"SITE-KA-001"}
    forbidden=ComplianceCase(
        case_id="OUTSIDE-SITE-CASE",centre_id="SITE-KA-999",
        batch_id=permitted["batch_id"],case_type="camera_integrity",
        severity="high",summary="Must not leak"
    )
    result=build_action_queue(
        centres=[permitted],cases=[forbidden],history=[],
        period="last_7_days",now=datetime(2026,10,19,tzinfo=timezone.utc))
    assert result["counts"]["total"]==0
    assert "OUTSIDE-SITE-CASE" not in str(result)
