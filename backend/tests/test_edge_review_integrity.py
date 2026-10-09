"""Release-level offline edge sync regression tests.

All events are synthetic. They exercise the real HTTP endpoints and durable
stores while ensuring edge reports cannot impersonate an officer or roll back
an officer's audit decision.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.services.case_store import CaseStore
from app.services.analysis_history import AnalysisHistoryStore


CASE_ID = "CASE-EDGE-AUDIT-01"


def _client(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases.json")
    history = AnalysisHistoryStore(tmp_path / "analysis_history.json")
    monkeypatch.setattr(app_main, "STORE", store)
    monkeypatch.setattr(app_main, "HISTORY", history)
    monkeypatch.setattr(app_main, "DATA", tmp_path)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    return TestClient(app_main.app), store


def _edge_case_event(event_id, *, status="open", summary="Synthetic edge camera review"):
    return {
        "event_id": event_id,
        "event_type": "compliance_case",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "case_id": CASE_ID,
            "centre_id": "DEMO-KA-207",
            "batch_id": "ELEC-2026-09",
            "case_type": "camera_integrity",
            "severity": "medium",
            "summary": summary,
            "status": status,
            "details": {"simulated": True, "visibility": "insufficient"},
            "evidence_integrity": [],
            "privacy": {"raw_video_included": False},
        },
    }


def test_synced_edge_inference_cannot_claim_final_officer_status(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    result = client.post(
        "/api/edge/sync",
        json={"events": [_edge_case_event("EDGE-NEW-01", status="confirmed")]},
    )
    assert result.status_code == 200
    assert result.json()["accepted_count"] == 1
    assert result.json()["skipped_existing_case_ids"] == []
    case = store.get(CASE_ID)
    assert case is not None
    assert case.status.value == "open"
    assert case.review_history == []
    assert case.details["edge_reported_status_unverified"] == "confirmed"
    assert case.details["raw_video_uploaded"] is False

    # Reusing the same delivery identifier is idempotent.
    replay = client.post(
        "/api/edge/sync",
        json={"events": [_edge_case_event("EDGE-NEW-01", status="confirmed")]},
    )
    assert replay.status_code == 200
    assert replay.json()["accepted_count"] == 0
    assert len(store.list()) == 1


def test_new_edge_event_id_cannot_erase_an_existing_officer_decision(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    first = client.post(
        "/api/edge/sync",
        json={"events": [_edge_case_event("EDGE-NEW-02")]},
    )
    assert first.status_code == 200
    assert first.json()["accepted_count"] == 1

    start = client.post(
        f"/api/cases/{CASE_ID}/review",
        json={"action": "under_review", "note": "Synthetic officer inspection started."},
    )
    assert start.status_code == 200
    resolved = client.post(
        f"/api/cases/{CASE_ID}/review",
        json={"action": "resolved", "note": "Synthetic camera feed restored."},
    )
    assert resolved.status_code == 200
    expected_history = resolved.json()["review_history"]
    assert len(expected_history) == 2

    # The same source case can be delivered under a new event_id. It must
    # remain acknowledged to avoid an infinite edge retry, but MUST NOT
    # mutate the existing reviewed case.
    replay = client.post(
        "/api/edge/sync",
        json={
            "events": [_edge_case_event(
                "EDGE-NEW-03",
                status="open",
                summary="Stale edge telemetry must not overwrite officer evidence",
            )]
        },
    )
    assert replay.status_code == 200
    assert replay.json()["accepted_count"] == 1
    assert replay.json()["skipped_existing_case_ids"] == [CASE_ID]
    assert store.get(CASE_ID).status.value == "resolved"
    assert store.get(CASE_ID).review_history == expected_history
    assert store.get(CASE_ID).summary == "Synthetic edge camera review"
    assert len(store.list()) == 1

    pack = client.get(f"/api/cases/{CASE_ID}/evidence-pack")
    assert pack.status_code == 200
    assert pack.json()["review"]["terminal"] is True
    assert pack.json()["review"]["history"] == list(reversed(expected_history))

    action_queue = client.get("/api/actions")
    assert action_queue.status_code == 200
    assert not any(
        item["case_id"] == CASE_ID
        for item in action_queue.json()["actions"]
    )

    # The new event is now idempotent too, even though its mutation was skipped.
    duplicate_delivery = client.post(
        "/api/edge/sync",
        json={"events": [_edge_case_event("EDGE-NEW-03")]},
    )
    assert duplicate_delivery.status_code == 200
    assert duplicate_delivery.json()["accepted_count"] == 0
    assert duplicate_delivery.json()["skipped_existing_case_ids"] == []
