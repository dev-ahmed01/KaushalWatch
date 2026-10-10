"""Check API persists *whole-video* attendance disposition, not detector presence.

All media and detector results here are explicit test fixtures, not inference.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as app_main
from app.services.analysis_history import AnalysisHistoryStore


@pytest.mark.parametrize(
    "decision,authoritative,failures,trust,expected",
    [
        ("compliant", True, 0, 0.96, "compliant"),
        ("camera_integrity_exception", True, 0, 0.1, "blocked"),
        ("camera_evidence_insufficient", True, 0, 0.1, "blocked"),
        ("compliant", True, 1, 0.95, "blocked"),
        ("compliant", True, 0, 0.1, "blocked"),
        ("compliant", False, 0, 0.95, "blocked"),
        ("detector_unavailable", False, 1, 0.95, "blocked"),
        ("unknown_new_state", True, 0, 0.95, "blocked"),
    ],
)
def test_attendance_upload_never_equates_authoritative_detector_with_trusted_result(
    tmp_path, monkeypatch, decision, authoritative, failures, trust, expected
):
    history = AnalysisHistoryStore(tmp_path / "analysis.json")
    monkeypatch.setattr(app_main, "HISTORY", history)

    synthetic_result = SimpleNamespace(
        case=None, reported_attendance=20, estimated_occupancy=20,
        discrepancy_pct=0, detector_authoritative=authoritative,
        detector_failures=failures, trusted_sample_ratio=trust,
        detector_message="Synthetic detector event; not real model output",
        decision=decision,
        model_dump=lambda **_: {"decision": decision, "case": None},
    )
    monkeypatch.setattr(
        app_main, "PIPELINE", SimpleNamespace(run=lambda *a, **k: synthetic_result)
    )
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    result = TestClient(app_main.app).post(
        "/api/process-video",
        data={"centre_id": "DEMO-KA-104", "batch_id": "SYNTHETIC-TEST",
              "reported_attendance": "20"},
        files={"file": ("synthetic.mp4", b"synthetic-no-real-video", "video/mp4")},
    )
    assert result.status_code == 200, result.text
    assert result.json()["decision"] == decision
    rows = history.list(centre_id="DEMO-KA-104")
    assert len(rows) == 1
    assert rows[0]["outcome"] == expected
    if expected != "compliant":
        assert "matched" not in rows[0]["summary"].lower()
