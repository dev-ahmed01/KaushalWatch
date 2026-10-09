"""JSON case-store integrity guarantees for the single-worker SIH prototype.

The store is not a multi-process, transactional audit database. These tests
cover atomic replacement and in-process competing officer transitions only.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import CaseStatus, ComplianceCase
from app.services.case_store import CaseStore
import app.services.case_store as case_store_module


def _case() -> ComplianceCase:
    return ComplianceCase(
        case_id="CASE-ATOMIC-1",
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO",
        case_type="attendance_discrepancy",
        severity="medium",
        summary="Synthetic review case",
    )


def test_atomic_write_failure_preserves_previous_audit_ledger(tmp_path, monkeypatch):
    path = tmp_path / "cases.json"
    store = CaseStore(path)
    store.save(_case())
    before = path.read_bytes()

    def failed_replace(_source, _dest):
        raise OSError("Synthetic replace interruption")

    monkeypatch.setattr(case_store_module.os, "replace", failed_replace)
    with pytest.raises(OSError, match="Synthetic replace interruption"):
        store.update_status(
            "CASE-ATOMIC-1",
            CaseStatus.under_review,
            note="Interrupted write.",
            actor="officer-test",
        )

    assert path.read_bytes() == before
    assert len(json.loads(path.read_text())) == 1
    assert CaseStore(path).get("CASE-ATOMIC-1").status == CaseStatus.open
    assert list(tmp_path.glob(".cases.json.*.tmp")) == []


def test_competing_officer_decisions_do_not_lose_or_rewrite_audit(tmp_path):
    path = tmp_path / "cases.json"
    store = CaseStore(path)
    store.save(_case())
    store.update_status(
        "CASE-ATOMIC-1",
        CaseStatus.under_review,
        note="Officer review started",
        actor="officer-start",
    )
    start = Barrier(2)

    def submit(status: CaseStatus):
        start.wait()
        try:
            return store.update_status(
                "CASE-ATOMIC-1", status,
                note=f"Decision {status.value}",
                actor=f"officer-{status.value}",
            )
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        actions = [
            pool.submit(submit, CaseStatus.confirmed),
            pool.submit(submit, CaseStatus.false_positive),
        ]
        results = [item.result() for item in actions]

    assert sum(result == "conflict" for result in results if isinstance(result, str)) == 1
    final = CaseStore(path).get("CASE-ATOMIC-1")
    assert final is not None
    assert final.status in {CaseStatus.confirmed, CaseStatus.false_positive}
    assert len(final.review_history) == 2
    assert final.review_history[0]["actor"] == "officer-start"
    assert final.review_history[1]["actor"].startswith("officer-")
    assert final.review_history[1]["from_status"] == "under_review"
    assert final.review_history[1]["to_status"] == final.status.value
    assert json.loads(path.read_text())[0]["status"] == final.status.value
