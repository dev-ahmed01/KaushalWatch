"""Single-commit officer decisions: synthetic regression evidence only.

One user action must not leave a case 'under review' if the final status write
fails; the two audit transitions are committed or rolled back together.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as app_main
from app.models import CaseStatus, ComplianceCase
from app.services.case_store import CaseStore
import app.services.case_store as store_module


def _store(tmp_path):
    store = CaseStore(tmp_path / "cases.json")
    store.save(ComplianceCase(
        case_id="CASE-ATOMIC-OFFICER-01",
        centre_id="DEMO-KA-104",
        batch_id="TEST-BATCH",
        case_type="camera_integrity",
        severity="high",
        summary="Synthetic camera evidence insufficient",
    ))
    return store


def test_atomic_open_to_final_emits_both_audit_steps_with_one_write(tmp_path):
    store = _store(tmp_path)
    result = store.apply_review_action(
        "CASE-ATOMIC-OFFICER-01", CaseStatus.confirmed,
        note="Synthetic frame evidence independently reviewed.",
        actor="reviewer-01",
    )
    assert result.status == CaseStatus.confirmed
    assert [(r["from_status"], r["to_status"]) for r in result.review_history] == [
        ("open", "under_review"), ("under_review", "confirmed"),
    ]
    assert [r["actor"] for r in result.review_history] == ["reviewer-01"] * 2
    assert result.review_history[-1]["note"] == "Synthetic frame evidence independently reviewed."
    reloaded = CaseStore(tmp_path / "cases.json").get("CASE-ATOMIC-OFFICER-01")
    assert reloaded.review_history == result.review_history


def test_interrupted_final_review_write_preserves_initial_case_and_empty_audit(
    tmp_path, monkeypatch
):
    store = _store(tmp_path)
    previous = store.path.read_bytes()

    def crash(_src, _dst):
        raise OSError("synthetic crash before commit")

    monkeypatch.setattr(store_module.os, "replace", crash)
    with pytest.raises(OSError, match="before commit"):
        store.apply_review_action(
            "CASE-ATOMIC-OFFICER-01", CaseStatus.resolved,
            note="Synthetic officer attempted final decision.",
            actor="reviewer-01",
        )
    assert store.path.read_bytes() == previous
    assert CaseStore(store.path).get("CASE-ATOMIC-OFFICER-01").status == CaseStatus.open
    assert CaseStore(store.path).get("CASE-ATOMIC-OFFICER-01").review_history == []
    assert not list(tmp_path.glob(".cases.json.*.tmp"))


def test_simultaneous_final_decisions_cannot_overwrite_one_another(tmp_path):
    store = _store(tmp_path)
    barrier = Barrier(2)

    def decide(action):
        barrier.wait()
        try:
            return store.apply_review_action(
                "CASE-ATOMIC-OFFICER-01", action,
                note=f"Synthetic decision: {action.value}", actor=action.value,
            )
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(decide, CaseStatus.confirmed)
        second = pool.submit(decide, CaseStatus.false_positive)
        results = [first.result(), second.result()]
    assert sum(value == "conflict" for value in results if isinstance(value, str)) == 1
    stored = CaseStore(store.path).get("CASE-ATOMIC-OFFICER-01")
    assert stored.status in (CaseStatus.confirmed, CaseStatus.false_positive)
    assert len(stored.review_history) == 2
    assert stored.review_history[-1]["to_status"] == stored.status.value


def test_one_http_request_commits_both_steps_and_replay_is_not_new_audit(tmp_path, monkeypatch):
    store = _store(tmp_path)
    monkeypatch.setattr(app_main, "STORE", store)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    key = "synthetic_atomic_officer_key_0123456789abcdef"
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", json.dumps({"reviewer-01": key}))
    client = TestClient(app_main.app)
    req = {"action": "confirmed", "note": "Rechecked blurred footage; decision confirmed."}
    unauthorized = client.post("/api/cases/CASE-ATOMIC-OFFICER-01/review", json=req)
    assert unauthorized.status_code == 401
    assert store.get("CASE-ATOMIC-OFFICER-01").review_history == []

    first = client.post("/api/cases/CASE-ATOMIC-OFFICER-01/review",
                        headers={"Authorization": f"Bearer {key}"}, json=req)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "confirmed"
    assert len(first.json()["review_history"]) == 2
    assert all(event["actor"] == "reviewer-01" for event in first.json()["review_history"])
    assert key not in first.text
    duplicate = client.post("/api/cases/CASE-ATOMIC-OFFICER-01/review",
                            headers={"Authorization": f"Bearer {key}"}, json=req)
    assert duplicate.status_code == 200
    assert len(store.get("CASE-ATOMIC-OFFICER-01").review_history) == 2
    conflicting = client.post("/api/cases/CASE-ATOMIC-OFFICER-01/review",
                              headers={"Authorization": f"Bearer {key}"},
                              json={"action": "false_positive", "note": "Stale competing action"})
    assert conflicting.status_code == 409
    assert store.get("CASE-ATOMIC-OFFICER-01").status == CaseStatus.confirmed
