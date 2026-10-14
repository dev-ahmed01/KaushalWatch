"""Real PostgreSQL transaction and multi-connection smoke checks.

Run only in dedicated GitHub CI job with disposable PostgreSQL service.
Never point this test suite at a real or shared database.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.models import CaseStatus, ComplianceCase, EdgeSyncRequest
from app.services.postgres_store import (
    PostgresCaseStore, PostgresAnalysisHistoryStore,
    PostgresCentreSettingsStore, PostgresEdgeEventLedger, unit_of_work,
)

C1 = "DEMO-KA-104"
C2 = "DEMO-KA-112"
OFFICER = "SyntheticPgAdmin_0123456789abcdefghijklmnopqrstuvwxyz"
VIEWER = "SyntheticPgViewer_0123456789abcdefghijklmnopqrstuvwxyz"
REVIEWER = "SyntheticPgReviewer_0123456789abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    dsn = os.environ.get("KAUSHALWATCH_DATABASE_URL", "")
    if not dsn and not os.environ.get("KAUSHALWATCH_TEST_DATABASE"):
        pytest.skip("PostgreSQL-only integration test (run in isolated DB job)")
    if (os.environ.get("KAUSHALWATCH_TEST_DATABASE") != "isolated_ci"
            or "kaushalwatch_ci" not in dsn):
        pytest.fail("PostgreSQL tests require explicitly isolated kaushalwatch_ci database")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",
                       json.dumps({"pg-admin": OFFICER, "pg-viewer": VIEWER, "pg-reviewer": REVIEWER}))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON", json.dumps({
        "pg-admin": {"role": "network_admin", "centres": []},
        "pg-viewer": {"role": "centre_viewer", "centres": [C1]},
        "pg-reviewer": {"role": "centre_reviewer", "centres": [C1]},
    }))
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON",
                       json.dumps({"pg-edge": "SyntheticPgEdge_0123456789abcdefghijklmnopqrstuvwxyz"}))
    with psycopg.connect(dsn) as db:
        db.execute("TRUNCATE kw_edge_events, kw_analysis_history, kw_cases, kw_centre_settings RESTART IDENTITY")
    yield


def _case(case_id: str, centre: str = C1) -> ComplianceCase:
    return ComplianceCase(
        case_id=case_id, centre_id=centre, batch_id="PG-BATCH",
        case_type="attendance_discrepancy", severity="medium",
        summary="Synthetic, isolated PostgreSQL case",
    )


def test_cases_and_review_audit_survive_new_store_instance():
    a, b = PostgresCaseStore(), PostgresCaseStore()
    assert a.save_if_absent(_case("PG-CASE-1")) is True
    assert b.save_if_absent(_case("PG-CASE-1")) is False
    assert b.get("PG-CASE-1").centre_id == C1
    reviewed = a.apply_review_action("PG-CASE-1", CaseStatus.confirmed,
                                     note="Synthetic reviewer accepted.", actor="pg-reviewer")
    assert reviewed.status == CaseStatus.confirmed
    assert [event["to_status"] for event in reviewed.review_history] == ["under_review", "confirmed"]
    persisted = b.get("PG-CASE-1")
    assert persisted.status == CaseStatus.confirmed
    assert persisted.review_history[-1]["actor"] == "pg-reviewer"
    with pytest.raises(ValueError, match="Invalid case transition"):
        b.update_status("PG-CASE-1", CaseStatus.under_review)
    assert len(a.get("PG-CASE-1").review_history) == 2
    # A delayed inference job or colliding case ID cannot erase audited state.
    collision = _case("PG-CASE-1", C2)
    persisted_collision = a.save(collision)
    assert persisted_collision.centre_id == C1
    assert persisted_collision.status == CaseStatus.confirmed
    assert len(b.get("PG-CASE-1").review_history) == 2


def test_concurrent_reviewers_cannot_both_finalize_case():
    PostgresCaseStore().save_if_absent(_case("PG-RACE"))
    def review(action: CaseStatus):
        try:
            return PostgresCaseStore().apply_review_action(
                "PG-RACE", action, note="Synthetic test decision", actor="pg-reviewer"
            ).status.value
        except ValueError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(review, (CaseStatus.confirmed, CaseStatus.resolved)))
    assert "rejected" in outcomes
    assert len([x for x in outcomes if x != "rejected"]) == 1
    assert len(PostgresCaseStore().get("PG-RACE").review_history) == 2


def test_history_edge_event_is_idempotent_across_connections():
    a, b = PostgresAnalysisHistoryStore(), PostgresAnalysisHistoryStore()
    fields = dict(edge_event_id="EDGE-PG-HISTORY-1", centre_id=C1,
                  batch_id="PG-BATCH", analysis_type="attendance",
                  outcome="blocked", summary="Synthetic edge signal",
                  details={"edge_synced": True})
    result = a.append_edge_once(**fields)
    replay = b.append_edge_once(**fields)
    assert result == replay
    assert len(a.list(centre_id=C1)) == 1
    other = b.append(centre_id=C2, batch_id="PG-BATCH", analysis_type="attendance",
                     outcome="attention", summary="other")
    assert other["analysis_id"] != result["analysis_id"]
    assert len(a.list(centre_id=C1)) == 1
    assert len(b.list(centre_id=C2)) == 1


def test_centre_settings_are_durable_and_merge_in_transaction():
    a, b = PostgresCentreSettingsStore(), PostgresCentreSettingsStore()
    assert a.get(C1)["automatic_analysis"] is True
    a.save(C1, {"frequency": "weekly"})
    b.save(C1, {"connectivity_mode": "normal"})
    assert a.get(C1)["frequency"] == "weekly"
    assert a.get(C1)["connectivity_mode"] == "normal"


def test_explicit_transaction_rollback_removes_all_derived_rows():
    case, history, ledger = (
        PostgresCaseStore(), PostgresAnalysisHistoryStore(), PostgresEdgeEventLedger()
    )
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        with unit_of_work(edge=True):
            case.save_if_absent(_case("PG-ROLLBACK"))
            history.append_edge_once(
                edge_event_id="EDGE-PG-ROLLBACK", centre_id=C1, batch_id="PG-BATCH",
                analysis_type="attendance", outcome="blocked",
                summary="Should be rolled back",
            )
            ledger.save([{"event_id": "EDGE-PG-ROLLBACK", "event_type": "analysis_summary"}])
            raise RuntimeError("synthetic rollback")
    assert case.get("PG-ROLLBACK") is None
    assert history.list() == []
    assert ledger.load() == []


def _edge_case_event(event_id: str, case_id: str) -> dict:
    return {
        "event_id": event_id, "event_type": "compliance_case",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "case_id": case_id, "centre_id": C1, "batch_id": "PG-BATCH",
            "case_type": "attendance_discrepancy", "severity": "medium",
            "summary": "Synthetic normalized edge discrepancy",
            "status": "confirmed",
            "privacy": {"raw_video_included": False, "individual_identification": False},
        },
    }


def test_edge_sync_is_atomic_and_idempotent_between_worker_requests():
    import app.main as main
    assert main.STORAGE_BACKEND == "postgres"
    req = EdgeSyncRequest(events=[_edge_case_event("EDGE-PG-MULTI-001", "PG-EDGE-CASE")])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: main._edge_sync_locked(req, "pg-edge"), range(2)))
    assert sum(x["accepted_count"] for x in results) == 1
    assert len(PostgresEdgeEventLedger().load()) == 1
    record = PostgresCaseStore().get("PG-EDGE-CASE")
    assert record is not None
    assert record.status == CaseStatus.open
    assert record.details["edge_reported_status_unverified"] == "confirmed"
    PostgresCaseStore().apply_review_action("PG-EDGE-CASE", CaseStatus.confirmed,
                                             note="Officer verified.", actor="pg-reviewer")
    second = main._edge_sync_locked(EdgeSyncRequest(events=[
        _edge_case_event("EDGE-PG-MULTI-002", "PG-EDGE-CASE")
    ]), "pg-edge")
    assert second["skipped_existing_case_ids"] == ["PG-EDGE-CASE"]
    assert PostgresCaseStore().get("PG-EDGE-CASE").status == CaseStatus.confirmed


def test_edge_sync_transaction_rolls_back_when_ledger_persistence_fails(monkeypatch):
    import app.main as main
    ledger_save = PostgresEdgeEventLedger.save
    def fail_after_insert(self, rows):
        ledger_save(self, rows)
        raise RuntimeError("synthetic storage failure")
    monkeypatch.setattr(PostgresEdgeEventLedger, "save", fail_after_insert)
    req = EdgeSyncRequest(events=[_edge_case_event("EDGE-PG-FAIL-001", "PG-FAIL-CASE")])
    with pytest.raises(RuntimeError, match="synthetic storage failure"):
        main._edge_sync_locked(req, "pg-edge")
    assert PostgresCaseStore().get("PG-FAIL-CASE") is None
    assert PostgresEdgeEventLedger().load() == []


def test_postgres_case_access_uses_existing_officer_centre_permissions():
    import app.main as main
    assert main.STORAGE_BACKEND == "postgres"
    PostgresCaseStore().save_if_absent(_case("PG-VIEW-1", C1))
    PostgresCaseStore().save_if_absent(_case("PG-HIDDEN-2", C2))
    client = TestClient(main.app)
    hview = {"Authorization": "Bearer " + VIEWER}
    hrev = {"Authorization": "Bearer " + REVIEWER}
    cases = client.get("/api/cases", headers=hview)
    assert cases.status_code == 200
    assert [c["case_id"] for c in cases.json()] == ["PG-VIEW-1"]
    assert client.get("/api/cases/PG-HIDDEN-2/evidence-pack", headers=hview).status_code == 404
    assert client.post("/api/cases/PG-VIEW-1/review", headers=hview,
                       json={"action": "under_review"}).status_code == 403
    allowed = client.post("/api/cases/PG-VIEW-1/review", headers=hrev,
                          json={"action": "under_review"})
    assert allowed.status_code == 200
    assert allowed.json()["review_history"][-1]["actor"] == "pg-reviewer"
