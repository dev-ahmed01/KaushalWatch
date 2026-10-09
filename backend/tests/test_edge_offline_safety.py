"""Camera-insufficient and offline edge sync release regressions (synthetic only).

The server receives untrusted telemetry: it may neither rewrite an officer's
status nor turn insufficient camera evidence into verified compliance.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

import app.main as app_main
import app.services.offline_queue as offline_module
from app.services.case_store import CaseStore
from app.services.analysis_history import AnalysisHistoryStore
from app.services.offline_queue import EdgeEventQueue
from edge.agent import analysis_to_edge_payload


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_main, "STORE", CaseStore(tmp_path / "cases.json"))
    monkeypatch.setattr(app_main, "HISTORY", AnalysisHistoryStore(tmp_path / "history.json"))
    monkeypatch.setattr(app_main, "DATA", tmp_path)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    return TestClient(app_main.app)


def _summary_event(event_id, *, decision="camera_evidence_insufficient",
                   trust=0.1, claimed="compliant", authoritative=True):
    return {
        "event_id": event_id,
        "event_type": "analysis_summary",
        "created_at": "2026-10-10T00:00:00+00:00",
        "payload": {
            "centre_id": "DEMO-KA-207", "batch_id": "ELEC-2026-09",
            "analysis_type": "attendance", "outcome": claimed,
            "summary": "Untrusted edge claims compliance.",
            "details": {
                "decision": decision, "trusted_sample_ratio": trust,
                "detector_authoritative": authoritative,
                "detector_failures": 0,
                "detector_backend": "openvino",
                "raw_video_path": "/sensitive/local/camera-frame.jpg",
                "face_image": "UNTRUSTED_IDENTIFYING_BYTES",
            },
            "privacy": {"raw_video_included": False, "individual_identification": False},
        },
    }


def _case_event(event_id, *, case_id="CASE-EDGE-SAFETY-01"):
    return {
        "event_id": event_id,
        "event_type": "compliance_case",
        "created_at": "2026-10-10T00:00:00+00:00",
        "payload": {
            "case_id": case_id, "centre_id": "DEMO-KA-207",
            "batch_id": "ELEC-2026-09", "case_type": "camera_integrity",
            "severity": "medium", "summary": "Synthetic camera trust failure",
            "status": "confirmed",
            "details": {"simulated": True, "visibility": "insufficient",
                        "face_snapshot": "PRIVATE_FACE_BYTES",
                        "local_video": "/private/worker-video.mp4"},
            "evidence_integrity": [
                {"evidence_id": "EV-EDGE-01", "sha256": "a" * 64,
                 "frame_path": "/private/worker-video.jpg"}
            ],
            "privacy": {"raw_video_included": False},
        },
    }


def test_edge_generated_summary_fails_closed_for_unusable_camera_or_detector():
    base = {
        "detector_authoritative": True, "detector_failures": 0,
        "trusted_sample_ratio": 0.05, "decision": "camera_evidence_insufficient",
        "case": None, "detector_message": "OpenVINO active",
        "reported_attendance": 15, "estimated_occupancy": None, "discrepancy_pct": None,
        "detector_backend": "openvino",
    }
    payload = analysis_to_edge_payload(SimpleNamespace(**base), centre_id="DEMO-KA-207", batch_id="X")
    assert payload["outcome"] == "blocked"
    assert "matched" not in payload["summary"].lower()
    assert payload["details"]["trusted_sample_ratio"] == 0.05
    valid = analysis_to_edge_payload(SimpleNamespace(**{**base, "trusted_sample_ratio": 0.9,
        "decision": "compliant"}), centre_id="DEMO-KA-207", batch_id="X")
    assert valid["outcome"] == "compliant"
    unavailable = analysis_to_edge_payload(SimpleNamespace(**{**base,
        "detector_authoritative": False, "decision": "compliant"}), centre_id="DEMO-KA-207", batch_id="X")
    assert unavailable["outcome"] == "blocked"


def test_server_normalizes_edge_claims_and_does_not_persist_private_fields(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    spoof = _summary_event("EDGE-CAMERA-FAIL-001")
    result = client.post("/api/edge/sync", json={"events": [spoof]})
    assert result.status_code == 200, result.text
    assert result.json()["accepted_count"] == 1
    history = app_main.HISTORY.list(centre_id="DEMO-KA-207")
    assert history[0]["outcome"] == "blocked"
    assert history[0]["details"]["edge_reported_outcome_unverified"] == "compliant"
    assert history[0]["details"]["edge_outcome_normalized"] == "blocked"
    safe_log = (tmp_path / "edge_events.json").read_text()
    assert "/sensitive/local/" not in safe_log
    assert "UNTRUSTED_IDENTIFYING_BYTES" not in safe_log

    missing_trust = _summary_event("EDGE-MISSING-TRUST-002", decision="compliant", trust=None)
    accepted = client.post("/api/edge/sync", json={"events": [missing_trust]})
    assert accepted.status_code == 200
    assert app_main.HISTORY.list()[0]["outcome"] == "blocked"

    good = _summary_event("EDGE-TRUST-ENOUGH-003", decision="compliant", trust=0.95)
    response = client.post("/api/edge/sync", json={"events": [good]})
    assert response.status_code == 200
    assert app_main.HISTORY.list()[0]["outcome"] == "compliant"


def test_edge_case_import_strips_person_paths_and_never_replays_officer_status(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/edge/sync", json={"events": [_case_event("EDGE-CASE-PROTECTED-01")]})
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1
    case = app_main.STORE.get("CASE-EDGE-SAFETY-01")
    assert case.status.value == "open"
    assert case.review_history == []
    assert case.details["edge_reported_status_unverified"] == "confirmed"
    assert case.details["edge_evidence_integrity"][0]["sha256"] == "a" * 64
    assert "frame_path" not in case.details["edge_evidence_integrity"][0]
    data = (tmp_path / "edge_events.json").read_text()
    assert "PRIVATE_FACE_BYTES" not in data
    assert "/private/" not in data

    resolved = client.post("/api/cases/CASE-EDGE-SAFETY-01/review",
        json={"action": "under_review", "note": "Started synthetic review"})
    assert resolved.status_code == 200
    second = client.post("/api/cases/CASE-EDGE-SAFETY-01/review",
        json={"action": "resolved", "note": "Video feed restored"})
    assert second.status_code == 200
    replay = _case_event("EDGE-CASE-PROTECTED-02")
    replay["payload"]["summary"] = "Attempts to replace verified officer case."
    result = client.post("/api/edge/sync", json={"events": [replay]})
    assert result.status_code == 200
    assert result.json()["skipped_existing_case_ids"] == ["CASE-EDGE-SAFETY-01"]
    assert app_main.STORE.get("CASE-EDGE-SAFETY-01").review_history == second.json()["review_history"]
    assert app_main.STORE.get("CASE-EDGE-SAFETY-01").summary == "Synthetic camera trust failure"


def test_server_rejects_video_or_identity_payload_and_unsupported_event(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    raw = _case_event("EDGE-RAW-VIDEO-0001")
    raw["payload"]["raw_video"] = "ABC123"
    privacy = _case_event("EDGE-PRIVACY-FALSE-02")
    privacy["payload"]["privacy"]["raw_video_included"] = True
    invalid = _summary_event("EDGE-UNKNOWN-TYPE-03")
    invalid["event_type"] = "officer_review"
    reply = client.post("/api/edge/sync", json={"events": [raw, privacy, invalid]})
    assert reply.status_code == 200
    report = reply.json()
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 3
    assert {x["reason"] for x in report["rejected_events"]} == {
        "raw_or_identity_data_not_accepted", "unsafe_privacy_claim", "unsupported_event_type"
    }
    assert not (tmp_path / "edge_events.json").exists()
    assert app_main.STORE.list() == []


def test_concurrent_replay_is_idempotent_in_single_worker(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    event = _case_event("EDGE-CONCURRENT-CASE-01", case_id="CASE-RACE-1")
    def deliver(_):
        result = client.post("/api/edge/sync", json={"events": [event]})
        assert result.status_code == 200
        return result.json()["accepted_count"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(pool.map(deliver, range(16)))
    assert sum(counts) == 1
    assert len(json.loads((tmp_path / "edge_events.json").read_text())) == 1
    assert len(app_main.STORE.list()) == 1


def test_queue_atomic_replace_failure_preserves_pending_events(tmp_path, monkeypatch):
    path = tmp_path / "edge-queue.json"
    queue = EdgeEventQueue(path)
    original = queue.enqueue("analysis_summary", {"centre_id": "DEMO-KA-207"})
    before = path.read_bytes()
    def interrupted(_src, _dst):
        raise OSError("synthetic edge disk interruption")
    monkeypatch.setattr(offline_module.os, "replace", interrupted)
    with pytest.raises(OSError, match="synthetic edge disk interruption"):
        queue.enqueue("analysis_summary", {"centre_id": "DEMO-KA-207"})
    assert path.read_bytes() == before
    assert [row["event_id"] for row in queue.pending()] == [original["event_id"]]
    assert list(tmp_path.glob(".edge-queue.json.*.tmp")) == []


def test_edge_queue_parallel_enqueue_ack_and_reload_is_consistent(tmp_path):
    queue = EdgeEventQueue(tmp_path / "edge-queue.json")
    def add(i):
        return queue.enqueue("analysis_summary", {"index": i})["event_id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(add, range(30)))
    assert len(queue.pending()) == 30
    assert len({e["event_id"] for e in queue.pending()}) == 30
    assert queue.acknowledge(ids[:15]) == 15
    assert queue.acknowledge(ids[:15]) == 0
    assert set(row["event_id"] for row in EdgeEventQueue(queue.path).pending()) == set(ids[15:])


def test_agent_keeps_unsent_events_if_central_acknowledgement_is_invalid(tmp_path, monkeypatch):
    from edge import agent
    from types import SimpleNamespace
    queue_path = tmp_path / "queue.json"
    queue = EdgeEventQueue(queue_path)
    queue.enqueue("analysis_summary", {"centre_id": "DEMO-KA-207"})
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"accepted_event_ids":"should_not_be_string"}'
    monkeypatch.setattr(agent, "urlopen", lambda request, timeout: Response())
    args = SimpleNamespace(queue=str(queue_path), url="http://127.0.0.1:8000", timeout=10)
    assert agent.sync(args) == 2
    assert len(queue.pending()) == 1



def test_server_blocks_claimed_compliance_after_detector_failure(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    event = _summary_event("EDGE-DETECT-FAILURE-04", decision="compliant", trust=0.95)
    event["payload"]["details"]["detector_failures"] = 1
    response = client.post("/api/edge/sync", json={"events": [event]})
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1
    assert app_main.HISTORY.list()[0]["outcome"] == "blocked"



def test_agent_rejects_ack_for_a_different_unsent_event(tmp_path, monkeypatch):
    from edge import agent
    queue_path = tmp_path / "queue.json"
    queue = EdgeEventQueue(queue_path)
    queue.enqueue("analysis_summary", {"centre_id": "DEMO-KA-207"})
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"accepted_event_ids":["EDGE-NOT-SENT-0001"]}'
    monkeypatch.setattr(agent, "urlopen", lambda request, timeout: Response())
    args = SimpleNamespace(queue=str(queue_path), url="http://127.0.0.1:8000", timeout=10)
    assert agent.sync(args) == 2
    assert len(queue.pending()) == 1



def test_edge_sync_protected_environment_rejects_demo_or_missing_auth(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "demo")
    case = _case_event("EDGE-PROTECTED-AUTH-01")
    denied_demo = client.post("/api/edge/sync", json={"events": [case]})
    assert denied_demo.status_code == 503
    assert not (tmp_path / "edge_events.json").exists()

    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "token")
    monkeypatch.delenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON", raising=False)
    denied_unconfigured = client.post("/api/edge/sync", json={"events": [case]})
    assert denied_unconfigured.status_code == 503

    token = "SyntheticOnly_DeviceToken_0123456789abcdef_987"
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON",
                       json.dumps({"workshop-edge-01": token}))
    denied_missing = client.post("/api/edge/sync", json={"events": [case]})
    assert denied_missing.status_code == 401
    denied_wrong = client.post("/api/edge/sync", json={"events": [case]},
                               headers={"Authorization": "Bearer incorrect"})
    assert denied_wrong.status_code == 401
    authenticated = client.post("/api/edge/sync", json={"events": [case]},
                                headers={"Authorization": f"Bearer {token}"})
    assert authenticated.status_code == 200
    assert authenticated.json()["accepted_count"] == 1
    stored = json.loads((tmp_path / "edge_events.json").read_text())
    assert stored[0]["server_resolved_edge_actor"] == "workshop-edge-01"
    imported = app_main.STORE.get("CASE-EDGE-SAFETY-01")
    assert imported.details["edge_actor"] == "workshop-edge-01"
    assert imported.details["edge_receipt_unverified"] is True
    assert token not in (tmp_path / "edge_events.json").read_text()


def test_edge_agent_uses_environment_credential_without_printing_secret(
    tmp_path, monkeypatch, capsys
):
    from edge import agent
    queue_path = tmp_path / "queue.json"
    queue = EdgeEventQueue(queue_path)
    queued = queue.enqueue("analysis_summary", {"centre_id": "DEMO-KA-207"})
    token = "SyntheticOnly_DeviceToken_0123456789abcdef_987"
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_TOKEN", token)
    captured_headers = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self):
            return json.dumps({"accepted_event_ids": [queued["event_id"]]}).encode()

    def fake_urlopen(request, timeout):
        captured_headers.append(request.get_header("Authorization"))
        return Response()

    monkeypatch.setattr(agent, "urlopen", fake_urlopen)
    args = SimpleNamespace(queue=str(queue_path), url="http://127.0.0.1:8000", timeout=10)
    assert agent.sync(args) == 0
    assert queue.pending() == []
    assert captured_headers == [f"Bearer {token}"]
    assert token not in capsys.readouterr().out



def test_edge_history_retry_does_not_duplicate_after_receipt_ledger_crash(tmp_path, monkeypatch):
    import app.services.edge_event_ledger as ledger_module

    client = _client(tmp_path, monkeypatch)
    event = _summary_event(
        "EDGE-SYNTHETIC-Crash-01", decision="camera_evidence_insufficient",
        trust=0.05, claimed="compliant",
    )
    original = ledger_module.EdgeEventLedger.save

    def simulated_crash(self, rows):
        raise OSError("simulated failure after history append")

    monkeypatch.setattr(ledger_module.EdgeEventLedger, "save", simulated_crash)
    with pytest.raises(OSError, match="after history append"):
        client.post("/api/edge/sync", json={"events": [event]})
    assert not (tmp_path / "edge_events.json").exists()
    first = app_main.HISTORY.list(centre_id="DEMO-KA-207")
    assert len(first) == 1
    assert first[0]["outcome"] == "blocked"

    monkeypatch.setattr(ledger_module.EdgeEventLedger, "save", original)
    retry = client.post("/api/edge/sync", json={"events": [event]})
    assert retry.status_code == 200
    assert retry.json()["accepted_count"] == 1
    assert len(app_main.HISTORY.list(centre_id="DEMO-KA-207")) == 1
    duplicate = client.post("/api/edge/sync", json={"events": [event]})
    assert duplicate.status_code == 200
    assert duplicate.json()["accepted_count"] == 0
    assert len(app_main.HISTORY.list(centre_id="DEMO-KA-207")) == 1


def test_history_atomic_replace_failure_keeps_original_synthetic_ledger(tmp_path, monkeypatch):
    from app.services.analysis_history import AnalysisHistoryStore
    import app.services.analysis_history as history_module

    store = AnalysisHistoryStore(tmp_path / "history.json")
    store.append(centre_id="DEMO-KA-104", batch_id="TEST",
                 analysis_type="attendance", outcome="blocked",
                 summary="Synthetic camera review", details={"simulated": True})
    previous = store.path.read_bytes()
    def fail_write(_src, _dst):
        raise OSError("history atomic replacement interrupted")
    monkeypatch.setattr(history_module.os, "replace", fail_write)
    with pytest.raises(OSError, match="replacement interrupted"):
        store.append_edge_once(
            edge_event_id="EDGE-CI-HISTORY-001",
            centre_id="DEMO-KA-104", batch_id="TEST",
            analysis_type="attendance", outcome="compliant",
            summary="Untrusted synthetic edge history",
        )
    assert store.path.read_bytes() == previous
    assert len(store.list()) == 1
    assert not list(tmp_path.glob(".history.json.*.tmp"))
