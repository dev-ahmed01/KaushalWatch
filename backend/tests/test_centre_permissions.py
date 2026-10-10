"""Centre RBAC integration tests. Synthetic officers and records only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main
from app.models import ComplianceCase, EvidenceRecord
from app.services.case_store import CaseStore
from app.services.analysis_history import AnalysisHistoryStore

C1 = "DEMO-KA-104"
C2 = "DEMO-KA-112"
KEYS = {
    "net-admin": "SyntheticScopeAdmin_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "centre-reviewer": "SyntheticScopeReviewer_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "centre-viewer": "SyntheticScopeViewer_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
}
GRANTS = {
    "net-admin": {"role": "network_admin", "centres": []},
    "centre-reviewer": {"role": "centre_reviewer", "centres": [C1]},
    "centre-viewer": {"role": "centre_viewer", "centres": [C2]},
}


def auth(actor: str) -> dict:
    return {"Authorization": "Bearer " + KEYS[actor]}


@pytest.fixture
def protected(tmp_path, monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", json.dumps(KEYS))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON", json.dumps(GRANTS))
    monkeypatch.setattr(main, "DATA", tmp_path)
    store = CaseStore(tmp_path / "cases.json")
    monkeypatch.setattr(main, "STORE", store)
    history = AnalysisHistoryStore(tmp_path / "history.json")
    monkeypatch.setattr(main, "HISTORY", history)

    path = main.EVIDENCE / "RBAC_SYNTHETIC_A_2026.jpg"
    assert not path.exists(), "Test evidence must never replace an existing asset"
    path.write_bytes(b"synthetic jpeg fixture content only")
    store.save(ComplianceCase(
        case_id="RBAC-CASE-A", centre_id=C1, batch_id="TEST-A",
        case_type="camera_integrity", severity="medium",
        summary="Synthetic scoped A record",
        evidence=[EvidenceRecord(
            evidence_id="RBAC_SYNTHETIC_A_2026",
            frame_path=str(path),
            created_at="2026-10-01T00:00:00+00:00",
            sha256="a" * 64, perceptual_hash="b" * 16,
        )],
    ))
    store.save(ComplianceCase(
        case_id="RBAC-CASE-B", centre_id=C2, batch_id="TEST-B",
        case_type="attendance_discrepancy", severity="high",
        summary="Synthetic scoped B record",
    ))
    for centre, marker in ((C1, "ONLY_A"), (C2, "ONLY_B")):
        history.append(
            centre_id=centre, batch_id="TEST", analysis_type="attendance",
            outcome="attention", summary=marker, details={"marker": marker},
        )
    try:
        yield TestClient(main.app), store, history
    finally:
        path.unlink(missing_ok=True)


def test_protected_centre_lists_cases_history_and_dashboard_isolate_data(protected):
    client, _, _ = protected
    for actor, only, excluded, onlycase, excludedcase in [
        ("centre-reviewer", C1, C2, "RBAC-CASE-A", "RBAC-CASE-B"),
        ("centre-viewer", C2, C1, "RBAC-CASE-B", "RBAC-CASE-A"),
    ]:
        centres = client.get("/api/centres", headers=auth(actor))
        assert centres.status_code == 200
        assert centres.json()["total"] == 1
        assert centres.json()["centres"][0]["centre_id"] == only
        cases = client.get("/api/cases", headers=auth(actor))
        assert [c["case_id"] for c in cases.json()] == [onlycase]
        history = client.get("/api/analysis-history", headers=auth(actor))
        assert history.status_code == 200
        assert len(history.json()["rows"]) == 1
        assert history.json()["rows"][0]["centre_id"] == only
        dashboard = client.get("/api/dashboard", headers=auth(actor))
        assert dashboard.status_code == 200
        assert dashboard.json()["centres_monitored"] == 1
        assert onlycase in dashboard.text
        assert excludedcase not in dashboard.text
        assert excluded not in centres.text + cases.text + history.text + dashboard.text
        assert client.get("/api/analysis-history?centre_id=" + excluded,
                          headers=auth(actor)).status_code == 404
        assert client.get("/api/dashboard?centre_id=" + excluded,
                          headers=auth(actor)).status_code == 404
    net = client.get("/api/cases", headers=auth("net-admin"))
    assert {r["centre_id"] for r in net.json()} == {C1, C2}


@pytest.mark.parametrize("endpoint", [
    "/api/actions?period=last_7_days",
    "/api/insights?period=last_7_days",
    "/api/kaushalai/brief?period=last_7_days",
])
def test_network_aggregates_cannot_leak_other_centre(protected, endpoint):
    client, _, _ = protected
    response = client.get(endpoint, headers=auth("centre-reviewer"))
    assert response.status_code == 200, response.text
    assert C2 not in response.text
    assert "RBAC-CASE-B" not in response.text
    assert "ONLY_B" not in response.text


@pytest.mark.parametrize("path", [
    f"/api/centres/{C2}",
    f"/api/centres/{C2}/settings",
    f"/api/centres/{C2}/report",
    f"/api/centres/{C2}/report.pdf",
    f"/api/centres/{C2}/activity-intelligence",
    f"/api/centres/{C2}/intelligence",
    "/api/cases/RBAC-CASE-B/evidence-pack",
    "/evidence/RBAC_SYNTHETIC_A_2026.jpg",  # tested separately for matching role
])
def test_cross_centre_direct_reads_denied(protected, path):
    client, _, _ = protected
    if path.startswith("/evidence/"):
        assert client.get(path, headers=auth("centre-viewer")).status_code == 404
    else:
        assert client.get(path, headers=auth("centre-reviewer")).status_code == 404


def test_evidence_is_bound_to_own_case_and_orphan_not_public(protected):
    client, _, _ = protected
    allowed = client.get("/evidence/RBAC_SYNTHETIC_A_2026.jpg",
                         headers=auth("centre-reviewer"))
    assert allowed.status_code == 200
    assert allowed.content.startswith(b"synthetic jpeg")
    assert client.get("/evidence/RBAC_SYNTHETIC_A_2026.jpg",
                      headers=auth("centre-viewer")).status_code == 404
    assert client.get("/evidence/UNKNOWN_TEST_EVIDENCE.jpg",
                      headers=auth("net-admin")).status_code == 404
    pack = client.get("/api/cases/RBAC-CASE-A/evidence-pack",
                      headers=auth("centre-reviewer"))
    assert pack.status_code == 200
    assert "RBAC_SYNTHETIC_A_2026" in pack.text
    assert client.get("/api/cases/RBAC-CASE-A/evidence-pack",
                      headers=auth("centre-viewer")).status_code == 404


def test_reviewer_can_review_own_case_but_cannot_cross_centre(protected):
    client, store, _ = protected
    denied = client.post("/api/cases/RBAC-CASE-B/review",
                         headers=auth("centre-reviewer"), json={"action": "under_review"})
    assert denied.status_code == 404
    assert store.get("RBAC-CASE-B").status.value == "open"
    permitted = client.post("/api/cases/RBAC-CASE-A/review",
                            headers=auth("centre-reviewer"), json={"action": "under_review"})
    assert permitted.status_code == 200
    assert permitted.json()["review_history"][-1]["actor"] == "centre-reviewer"
    readonly = client.post("/api/cases/RBAC-CASE-B/review",
                           headers=auth("centre-viewer"), json={"action": "under_review"})
    assert readonly.status_code == 403
    assert store.get("RBAC-CASE-B").status.value == "open"
    assert store.get("RBAC-CASE-B").review_history == []


def test_settings_and_form_uploads_are_checked_before_mutations(protected):
    client, store, history = protected
    before = len(history.list())
    assert client.put(f"/api/centres/{C2}/settings",
                      headers=auth("centre-reviewer"), json={}).status_code == 404
    assert client.put(f"/api/centres/{C2}/settings",
                      headers=auth("centre-viewer"), json={}).status_code == 403
    for route in (
        "/api/process-video",
        "/api/process-practical-activity",
        "/api/process-infrastructure-video",
    ):
        forbidden = client.post(
            route, headers=auth("centre-reviewer"),
            data={"centre_id": C2, "reported_attendance": "10"},
            files={"file": ("bad.mp4", b"not a real video", "video/mp4")},
        )
        assert forbidden.status_code == 404, (route, forbidden.text)
        readonly = client.post(
            route, headers=auth("centre-viewer"),
            data={"centre_id": C2, "reported_attendance": "10"},
            files={"file": ("bad.mp4", b"not a real video", "video/mp4")},
        )
        assert readonly.status_code == 403, (route, readonly.text)
    assert store.get("RBAC-CASE-B").status.value == "open"
    assert len(history.list()) == before


def test_assistant_queries_and_unscoped_routes_fail_closed(protected):
    client, _, _ = protected
    wrong = client.post("/api/assistant/query", headers=auth("centre-reviewer"),
                        json={"centre_id": C2, "question": "show cases"})
    assert wrong.status_code == 404
    scoped = client.post("/api/assistant/query", headers=auth("centre-reviewer"),
                         json={"centre_id": C1, "question": "show current status"})
    assert scoped.status_code == 200
    assert C2 not in scoped.text
    for method, path in [
        ("POST", "/api/assistant/chat"),
        ("POST", "/api/operability-check"),
        ("POST", "/api/demo/infrastructure/create-case"),
        ("GET", "/openapi.json"),
        ("GET", "/api/unreviewed-future-route"),
    ]:
        response = client.request(method, path, headers=auth("centre-reviewer"))
        assert response.status_code == 403, (method, path, response.text)


@pytest.mark.parametrize("bad", [
    None,
    "{not valid",
    "{}",
    json.dumps({"centre-reviewer": GRANTS["centre-reviewer"]}),
    json.dumps({**GRANTS, "extra": {"role": "network_admin", "centres": []}}),
    json.dumps({**GRANTS, "centre-reviewer": {"role": "centre_reviewer", "centres": ["*"]}}),
    json.dumps({**GRANTS, "centre-viewer": {"role": "centre_viewer", "centres": []}}),
    json.dumps({**GRANTS, "net-admin": {"role": "network_admin", "centres": [C1]}}),
])
def test_missing_or_malformed_permission_map_fails_closed(protected, monkeypatch, bad):
    client, _, _ = protected
    if bad is None:
        monkeypatch.delenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON")
    else:
        monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON", bad)
    response = client.get("/api/cases", headers=auth("centre-reviewer"))
    assert response.status_code == 503
    assert "RBAC-CASE" not in response.text


def test_anonymous_and_edge_key_cannot_enter_officer_boundary(protected):
    client, _, _ = protected
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/cases", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_duplicate_evidence_id_across_centres_is_ambiguous_and_denied(protected):
    client, store, _ = protected
    original = store.get("RBAC-CASE-A").evidence[0]
    store.save(ComplianceCase(
        case_id="RBAC-DUPLICATE-ID-B", centre_id=C2, batch_id="TEST-B",
        case_type="evidence_integrity", severity="low",
        summary="Synthetic ambiguous evidence reference",
        evidence=[EvidenceRecord(**original.model_dump())],
    ))
    for actor in KEYS:
        response = client.get("/evidence/RBAC_SYNTHETIC_A_2026.jpg", headers=auth(actor))
        assert response.status_code == 404


def test_dashboard_scopes_nested_edge_payload_counts(protected, tmp_path):
    client, _, _ = protected
    (tmp_path / "edge_events.json").write_text(json.dumps([
        {"event_id": "EDGE-A", "payload": {"centre_id": C1}},
        {"event_id": "EDGE-B", "payload": {"centre_id": C2}},
        {"event_id": "NO-CENTRE", "payload": {}},
    ]), encoding="utf-8")
    assert client.get("/api/dashboard", headers=auth("centre-reviewer")).json()["synced_edge_events"] == 1
    assert client.get("/api/dashboard", headers=auth("centre-viewer")).json()["synced_edge_events"] == 1
    assert client.get("/api/dashboard", headers=auth("net-admin")).json()["synced_edge_events"] == 3


def test_role_context_returns_capabilities_without_any_secret(protected):
    client, _, _ = protected
    admin = client.get("/api/officer-context", headers=auth("net-admin"))
    assert admin.status_code == 200
    assert admin.json()["can_use_network_assistant"] is True
    viewer = client.get("/api/officer-context", headers=auth("centre-viewer"))
    assert viewer.status_code == 200
    assert viewer.json()["role"] == "centre_viewer"
    assert viewer.json()["centre_ids"] == [C2]
    assert viewer.json()["can_review"] is False
    assert viewer.json()["can_use_network_assistant"] is False
    assert all(secret not in viewer.text + admin.text for secret in KEYS.values())


def test_live_role_reassignment_applies_to_next_request(protected, monkeypatch):
    client, _, _ = protected
    assert client.get(f"/api/centres/{C1}", headers=auth("centre-reviewer")).status_code == 200
    new_grants = {**GRANTS, "centre-reviewer": {"role": "centre_viewer", "centres": [C2]}}
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON", json.dumps(new_grants))
    assert client.get(f"/api/centres/{C1}", headers=auth("centre-reviewer")).status_code == 404
    assert client.get(f"/api/centres/{C2}", headers=auth("centre-reviewer")).status_code == 200
    assert client.post("/api/cases/RBAC-CASE-B/review", headers=auth("centre-reviewer"),
                       json={"action": "under_review"}).status_code == 403
