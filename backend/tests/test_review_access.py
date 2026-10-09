"""Officer-review access regression tests; no live credentials are used."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main
from app.models import ComplianceCase
from app.services.case_store import CaseStore

REVIEW_PATH = "/api/cases/CASE-REVIEW-AUTH/review"
OFFICER_1 = "officer-01"
OFFICER_2 = "officer-02"
TOKEN_1 = "uBCf53ftwLdqVMtzPRDzJ3o7vU66sXjkW1"
TOKEN_2 = "udLYGHXeEqcvbnmsDRfTHIvKP200eZZzW2"


def _client(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases.json")
    store.save(
        ComplianceCase(
            case_id="CASE-REVIEW-AUTH",
            centre_id="DEMO-KA-104",
            batch_id="DEMO-BATCH",
            case_type="attendance_discrepancy",
            severity="medium",
            summary="Reviewable demonstration case",
        )
    )
    monkeypatch.setattr(main, "STORE", store)
    return TestClient(main.app), store


def _enable_token_mode(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.setenv(
        "KAUSHALWATCH_REVIEW_TOKENS_JSON",
        json.dumps({OFFICER_1: TOKEN_1, OFFICER_2: TOKEN_2}),
    )


def test_configured_review_requires_bearer_and_records_server_actor(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _enable_token_mode(monkeypatch)

    status = client.get("/api/review-access")
    assert status.status_code == 200
    assert status.json() == {"mode": "token", "required": True, "prototype_only": True}
    assert TOKEN_1 not in status.text

    missing = client.post(REVIEW_PATH, json={"action": "under_review"})
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert store.get("CASE-REVIEW-AUTH").status.value == "open"

    incorrect = client.post(
        REVIEW_PATH, headers={"Authorization": "Bearer invalid"},
        json={"action": "under_review"},
    )
    assert incorrect.status_code == 401
    assert store.get("CASE-REVIEW-AUTH").review_history == []

    started = client.post(
        REVIEW_PATH, headers={"Authorization": f"Bearer {TOKEN_1}"},
        json={"action": "under_review", "actor": "fake-admin"},
    )
    assert started.status_code == 200
    assert started.json()["review_history"][-1]["actor"] == OFFICER_1

    decided = client.post(
        REVIEW_PATH, headers={"Authorization": f"Bearer {TOKEN_2}"},
        json={"action": "confirmed", "note": "Independently checked the evidence."},
    )
    assert decided.status_code == 200
    assert [e["actor"] for e in decided.json()["review_history"]] == [
        OFFICER_1, OFFICER_2
    ]
    assert TOKEN_1 not in decided.text
    assert TOKEN_2 not in decided.text


def test_protected_environment_never_falls_back_to_demo(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    monkeypatch.setenv("KAUSHALWATCH_ENV", "production")

    assert client.get("/api/review-access").status_code == 503
    response = client.post(REVIEW_PATH, json={"action": "under_review"})
    assert response.status_code == 503
    assert store.get("CASE-REVIEW-AUTH").review_history == []


def test_missing_or_bad_credentials_configuration_fails_closed(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    for value in ("", "not-json", "{}", '{"officer-01":"weak"}'):
        monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", value)
        response = client.post(
            REVIEW_PATH,
            headers={"Authorization": f"Bearer {TOKEN_1}"},
            json={"action": "under_review"},
        )
        assert response.status_code == 503
    assert store.get("CASE-REVIEW-AUTH").review_history == []


def test_duplicate_or_invalid_actor_mapping_fails_closed(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    for mapping in (
        {"officer-01": TOKEN_1, "officer-02": TOKEN_1},
        {"admin name with spaces": TOKEN_1},
    ):
        monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", json.dumps(mapping))
        assert client.get("/api/review-access").status_code == 503


def test_explicit_local_demo_has_marked_prototype_actor(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    assert client.get("/api/review-access").json() == {
        "mode": "demo", "required": False, "prototype_only": True,
    }
    response = client.post(REVIEW_PATH, json={"action": "under_review"})
    assert response.status_code == 200
    assert response.json()["review_history"][-1]["actor"] == "prototype_officer"
