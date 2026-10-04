import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as app_main
from app.models import ComplianceCase
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.centre_settings import CentreSettingsStore


def _client(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases.json")
    history = AnalysisHistoryStore(tmp_path / "analysis_history.json")
    settings = CentreSettingsStore(tmp_path / "centre_settings.json")
    monkeypatch.setattr(app_main, "STORE", store)
    monkeypatch.setattr(app_main, "HISTORY", history)
    monkeypatch.setattr(app_main, "CENTRE_SETTINGS", settings)
    monkeypatch.setattr(app_main, "DATA", tmp_path)
    return TestClient(app_main.app), store, history


def test_network_centres_and_centre_detail(tmp_path, monkeypatch):
    client, store, history = _client(tmp_path, monkeypatch)
    store.save(
        ComplianceCase(
            case_id="CASE-NETWORK-1",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-2026-08",
            case_type="attendance_discrepancy",
            severity="high",
            summary="Attendance mismatch",
        )
    )

    network = client.get("/api/centres")
    assert network.status_code == 200
    body = network.json()
    assert body["total"] >= 6

    bengaluru = next(row for row in body["centres"] if row["centre_id"] == "DEMO-KA-104")
    assert bengaluru["pending_cases"] == 1
    assert bengaluru["attendance_status"] == "attention"
    assert bengaluru["escalation"]["level"] >= 1

    detail = client.get("/api/centres/DEMO-KA-104")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Bengaluru TC-04"
    assert "settings" in detail.json()
    assert "recent_analyses" in detail.json()


def test_analysis_history_assistant_and_report(tmp_path, monkeypatch):
    client, store, history = _client(tmp_path, monkeypatch)
    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="attendance",
        outcome="compliant",
        summary="3 people were consistently visible and the centre reported 3.",
        details={"estimated_occupancy": 3},
    )
    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="infrastructure",
        outcome="attention",
        summary="One camera-verifiable item requires review.",
        details={},
    )

    rows = client.get("/api/analysis-history?centre_id=DEMO-KA-104")
    assert rows.status_code == 200
    assert len(rows.json()["rows"]) == 2

    assistant = client.post(
        "/api/assistant/query",
        json={
            "centre_id": "DEMO-KA-104",
            "period": "7d",
            "question": "What happened in the last week?",
        },
    )
    assert assistant.status_code == 200
    answer = assistant.json()["answer"]
    assert "2 recorded analyses" in answer
    assert "attendance 1" in answer.lower()
    assert assistant.json()["grounded_in"]["centre_id"] == "DEMO-KA-104"

    report = client.get("/api/centres/DEMO-KA-104/report?period=7d")
    assert report.status_code == 200
    body = report.json()
    assert body["title"] == "KaushalWatch Centre Verification Report"
    assert body["summary"]["analysis_runs"] == 2
    assert "privacy_note" in body
    assert len(body["limitations"]) >= 1


def test_centre_settings_round_trip(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)

    current = client.get("/api/centres/DEMO-KA-104/settings")
    assert current.status_code == 200
    assert current.json()["automatic_analysis"] is True

    updated = client.put(
        "/api/centres/DEMO-KA-104/settings",
        json={
            "automatic_analysis": False,
            "frequency": "manual",
            "connectivity_mode": "low_bandwidth",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["automatic_analysis"] is False
    assert updated.json()["frequency"] == "manual"

    reread = client.get("/api/centres/DEMO-KA-104/settings")
    assert reread.status_code == 200
    assert reread.json()["frequency"] == "manual"



def test_assistant_infers_today_and_report_matches_window(tmp_path, monkeypatch):
    client, _, history = _client(tmp_path, monkeypatch)
    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="attendance",
        outcome="compliant",
        summary="Attendance matched today.",
        details={},
    )

    assistant = client.post(
        "/api/assistant/query",
        json={
            "centre_id": "DEMO-KA-104",
            "period": "7d",
            "question": "What happened today?",
        },
    )
    assert assistant.status_code == 200
    assert assistant.json()["period"] == "today"
    assert "1 recorded analyses" in assistant.json()["answer"]

    report = client.get("/api/centres/DEMO-KA-104/report?period=today")
    assert report.status_code == 200
    assert report.json()["period"] == "today"
    assert report.json()["summary"]["analysis_runs"] == 1


def test_saved_escalation_policy_changes_network_result(tmp_path, monkeypatch):
    client, store, _ = _client(tmp_path, monkeypatch)
    store.save(
        ComplianceCase(
            case_id="CASE-ESC-POLICY",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-2026-08",
            case_type="attendance_discrepancy",
            severity="high",
            summary="Repeated attendance mismatch",
        )
    )

    updated = client.put(
        "/api/centres/DEMO-KA-104/settings",
        json={
            "escalation_rules": {
                "repeated_attendance_days": 1,
                "unresolved_case_days": 30,
                "multi_signal_escalation": True,
                "duplicate_evidence_escalation": True,
            }
        },
    )
    assert updated.status_code == 200

    network = client.get("/api/centres")
    assert network.status_code == 200
    bengaluru = next(
        row for row in network.json()["centres"]
        if row["centre_id"] == "DEMO-KA-104"
    )
    assert bengaluru["escalation"]["level"] >= 2
    assert any(
        "attendance discrepancy repeated" in reason
        for reason in bengaluru["escalation"]["reasons"]
    )
    assert bengaluru["escalation"]["next_action"]



def test_unanalysed_centre_is_incomplete_not_compliant(tmp_path, monkeypatch):
    client, _, history = _client(tmp_path, monkeypatch)

    network = client.get("/api/centres")
    assert network.status_code == 200
    bengaluru = next(
        row for row in network.json()["centres"]
        if row["centre_id"] == "DEMO-KA-104"
    )
    assert bengaluru["status"] == "incomplete"
    assert bengaluru["attendance_status"] == "pending"
    assert bengaluru["practical_status"] == "pending"
    assert bengaluru["infrastructure_status"] == "pending"
    assert bengaluru["camera_status"] == "pending"
    assert bengaluru["evidence_integrity_status"] == "pending"

    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="attendance",
        outcome="blocked",
        summary="Detector unavailable.",
        details={},
    )
    detail = client.get("/api/centres/DEMO-KA-104")
    assert detail.status_code == 200
    assert detail.json()["status"] == "incomplete"
    assert detail.json()["attendance_status"] == "blocked"


def test_report_pdf_and_custom_range_are_real_outputs(tmp_path, monkeypatch):
    client, _, history = _client(tmp_path, monkeypatch)
    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="attendance",
        outcome="compliant",
        summary="Attendance matched.",
        details={},
    )
    today = datetime.now(timezone.utc).date().isoformat()

    custom = client.get(
        f"/api/centres/DEMO-KA-104/report?period=custom&start_date={today}&end_date={today}"
    )
    assert custom.status_code == 200
    assert custom.json()["summary"]["analysis_runs"] == 1
    assert custom.json()["period_label"] == f"{today} to {today}"

    pdf = client.get(
        f"/api/centres/DEMO-KA-104/report.pdf?period=custom&start_date={today}&end_date={today}"
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert "attachment;" in pdf.headers["content-disposition"]
    assert pdf.content.startswith(b"%PDF-1.4")


def test_practical_runtime_unavailable_becomes_blocked_history(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)

    def unavailable(**kwargs):
        raise RuntimeError("Practical-work runtime unavailable for test")

    monkeypatch.setattr(app_main.PRACTICAL_PIPELINE, "run", unavailable)
    response = client.post(
        "/api/process-practical-activity",
        data={
            "centre_id": "DEMO-KA-104",
            "batch_id": "ELEC-2026-08",
            "authorization": "valid",
            "zone_profile": "authorized",
        },
        files={"file": ("sample.avi", b"not-empty", "video/x-msvideo")},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "detector_unavailable"
    assert response.json()["detector_authoritative"] is False

    history = client.get("/api/analysis-history?centre_id=DEMO-KA-104")
    assert history.status_code == 200
    latest = history.json()["rows"][0]
    assert latest["analysis_type"] == "practical_work"
    assert latest["outcome"] == "blocked"



def test_edge_sync_updates_history_without_raw_video(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/edge/sync",
        json={
            "events": [
                {
                    "event_id": "EDGE-SUMMARY-1",
                    "event_type": "analysis_summary",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "centre_id": "DEMO-KA-104",
                        "batch_id": "ELEC-2026-08",
                        "analysis_type": "attendance",
                        "outcome": "blocked",
                        "summary": "Primary detector unavailable on edge device.",
                        "details": {"detector_authoritative": False},
                        "privacy": {"raw_video_included": False},
                    },
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1
    assert response.json()["raw_video_required"] is False

    history = client.get("/api/analysis-history?centre_id=DEMO-KA-104").json()["rows"]
    assert history[0]["outcome"] == "blocked"
    assert history[0]["details"]["edge_synced"] is True
    assert history[0]["details"]["raw_video_uploaded"] is False

    centre = client.get("/api/centres/DEMO-KA-104").json()
    assert centre["attendance_status"] == "blocked"
    assert centre["status"] == "incomplete"
