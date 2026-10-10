"""Protected API and evidence read boundary (synthetic credentials only).

A review write key also gates all other sensitive reads in protected deployments.
Device keys are explicitly NOT substitutes for an officer key. Development
retains the local offline-friendly SIH walkthrough.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore

OFFICER = "SyntheticOnly_ReadReviewer_0123456789abcdefghABCDEFGH"
EDGE = "SyntheticOnly_EdgeDevice_0123456789abcdefghABCDEFGH"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", json.dumps({"reviewer-01": OFFICER}))
    monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",
                       json.dumps({"reviewer-01": {"role": "network_admin", "centres": []}}))
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON", json.dumps({"edge-01": EDGE}))
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(main, "STORE", CaseStore(tmp_path / "cases.json"))
    monkeypatch.setattr(main, "HISTORY", AnalysisHistoryStore(tmp_path / "history.json"))
    return TestClient(main.app)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/cases"),
    ("GET", "/api/cases/nonexistent/evidence-pack"),
    ("GET", "/api/centres"),
    ("GET", "/api/centres/DEMO-KA-104/report.pdf"),
    ("GET", "/api/analysis-history"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/insights"),
    ("GET", "/api/runtime-readiness"),
    ("GET", "/evidence/unlisted-frame.jpg"),
    ("GET", "/openapi.json"),
    ("PUT", "/api/centres/DEMO-KA-104/settings"),
    ("POST", "/api/process-video"),
    ("POST", "/api/assistant/query"),
    ("POST", "/api/demo/infrastructure/create-case"),
])
def test_sensitive_protected_routes_refuse_unauthenticated_reads_and_writes(tmp_path, monkeypatch, method, path):
    client = _client(tmp_path, monkeypatch)
    response = client.request(method, path)
    assert response.status_code == 401, (method, path, response.text)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["www-authenticate"] == "Bearer"


def test_officer_token_allows_read_but_never_stores_or_returns_token(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    unauthorized = client.get("/api/cases", headers={"Authorization": f"Bearer {EDGE}"})
    assert unauthorized.status_code == 401
    incorrect = client.get("/api/cases", headers={"Authorization": "Bearer bad"})
    assert incorrect.status_code == 401
    authorized = client.get("/api/cases", headers={"Authorization": f"Bearer {OFFICER}"})
    assert authorized.status_code == 200
    assert authorized.json() == []
    assert authorized.headers["cache-control"] == "private, no-store"
    assert authorized.headers["pragma"] == "no-cache"
    assert OFFICER not in authorized.text
    not_found_evidence = client.get("/evidence/nonexistent.jpg",
                                    headers={"Authorization": f"Bearer {OFFICER}"})
    assert not_found_evidence.status_code == 404
    assert not_found_evidence.headers["cache-control"] == "private, no-store"


def test_anonymous_health_and_nonsecret_access_status_remain_accessible(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/health").status_code == 200
    status = client.get("/api/review-access")
    assert status.status_code == 200
    assert status.json() == {"mode": "token", "required": True, "prototype_only": True}
    assert OFFICER not in status.text
    cors = client.options("/api/cases", headers={
        "Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "GET",
    })
    assert cors.status_code == 200
    assert cors.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"


def test_edge_device_token_works_only_on_sync_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    event = {
        "event_id": "EDGE-READ-ACCESS-01001",
        "event_type": "analysis_summary",
        "payload": {
            "centre_id": "DEMO-KA-207", "batch_id": "SYNTHETIC-BATCH",
            "analysis_type": "attendance", "outcome": "compliant",
            "summary": "Client claims compliance with insufficient camera trust.",
            "details": {"decision": "camera_evidence_insufficient", "trusted_sample_ratio": 0.1,
                        "detector_authoritative": True, "detector_failures": 0},
            "privacy": {"raw_video_included": False, "individual_identification": False},
        },
    }
    wrong_role = client.post("/api/edge/sync", json={"events": [event]},
                             headers={"Authorization": f"Bearer {OFFICER}"})
    assert wrong_role.status_code == 401
    result = client.post("/api/edge/sync", json={"events": [event]},
                         headers={"Authorization": f"Bearer {EDGE}"})
    assert result.status_code == 200, result.text
    assert result.json()["accepted_count"] == 1
    assert main.HISTORY.list()[0]["outcome"] == "blocked"
    read_with_edge_key = client.get("/api/analysis-history",
                                    headers={"Authorization": f"Bearer {EDGE}"})
    assert read_with_edge_key.status_code == 401


def test_protected_mode_without_configured_reviewer_key_fails_closed(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    assert client.get("/api/cases").status_code == 503
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.delenv("KAUSHALWATCH_REVIEW_TOKENS_JSON")
    assert client.get("/api/cases").status_code == 503


def test_development_preserves_clearly_marked_simulated_read_only_walkthrough(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    assert client.get("/api/cases").status_code == 200
    assert client.get("/api/centres").status_code == 200


@pytest.mark.parametrize("typo", ["producton", "stagin", "unknown", ""])
def test_unknown_deployment_environment_fails_closed_instead_of_becoming_demo(
    tmp_path, monkeypatch, typo
):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_ENV", typo)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "demo")
    assert client.get("/api/cases").status_code == 503
    assert client.get("/api/review-access").status_code == 503
    assert client.post("/api/edge/sync", json={"events": []}).status_code == 503
    assert client.get("/api/health").status_code == 200


def test_explicit_demo_local_environments_are_allowed(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "demo")
    for local in ("development", "dev", "local", "test"):
        monkeypatch.setenv("KAUSHALWATCH_ENV", local)
        assert client.get("/api/cases").status_code == 200
        assert client.get("/api/review-access").status_code == 200


def test_login_validation_refuses_demo_server_even_with_a_configured_officer_token(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    token = client.get("/api/officer-validate", headers={"Authorization": f"Bearer {OFFICER}"})
    assert token.status_code == 503
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    assert client.get("/api/officer-validate").status_code == 401
    assert client.get("/api/officer-validate", headers={"Authorization": f"Bearer {EDGE}"}).status_code == 401
    valid = client.get("/api/officer-validate", headers={"Authorization": f"Bearer {OFFICER}"})
    assert valid.status_code == 200
    assert valid.json() == {"authenticated": True}
    assert OFFICER not in valid.text
