"""API must never expose local evidence paths to browser consumers.

Backend internal evidence records keep filesystem paths for integrity and
recovery. Public records keep opaque evidence IDs and SHA for retrieval.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as main
from app.models import ComplianceCase, EvidenceRecord
from app.services.api_redaction import redact_local_evidence_paths
from app.services.case_store import CaseStore
from app.services.analysis_history import AnalysisHistoryStore


def _client(tmp_path, monkeypatch):
    path = "/private/edge/camera-07/secret-frame.jpg"
    source = EvidenceRecord(
        evidence_id="SYN-EVIDENCE-001",
        created_at="2026-10-10T00:00:00+00:00",
        frame_path=path,
        sha256="a" * 64,
        perceptual_hash="b" * 16,
        metadata={"simulated": True, "path_note": "not an identity claim"},
    )
    case = ComplianceCase(
        case_id="SYN-PRIVATE-PATH-01",
        centre_id="DEMO-KA-104", batch_id="SYN-TEST",
        case_type="camera_integrity", severity="medium",
        summary="Synthetic camera review", evidence=[source],
        details={"simulated": True},
    )
    store = CaseStore(tmp_path / "cases.json")
    store.save(case)
    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "HISTORY", AnalysisHistoryStore(tmp_path / "history.json"))
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo")
    return TestClient(main.app), store, path


def test_nested_redaction_does_not_mutate_internal_record():
    data = {
        "case": {"evidence": [{"evidence_id": "EV-ONE",
                                "frame_path": "C:\\private\\sensitive.jpg",
                                "sha256": "b" * 64}]},
        "cases": [{"details": {"local_video_path": "/private/raw.mp4"}}],
    }
    filtered = redact_local_evidence_paths(data)
    assert filtered["case"]["evidence"][0]["evidence_id"] == "EV-ONE"
    assert filtered["case"]["evidence"][0]["sha256"] == "b" * 64
    assert "frame_path" not in filtered["case"]["evidence"][0]
    assert "local_video_path" not in filtered["cases"][0]["details"]
    assert data["case"]["evidence"][0]["frame_path"] == "C:\\private\\sensitive.jpg"


def test_central_case_and_review_json_never_disclose_filesystem_locations(tmp_path, monkeypatch):
    client, store, secret = _client(tmp_path, monkeypatch)
    cases = client.get("/api/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["evidence"][0]["evidence_id"] == "SYN-EVIDENCE-001"
    assert "frame_path" not in cases.json()[0]["evidence"][0]
    assert secret not in cases.text

    pack = client.get("/api/cases/SYN-PRIVATE-PATH-01/evidence-pack")
    assert pack.status_code == 200
    assert "frame_path" not in pack.json()["case"]["evidence"][0]
    assert secret not in pack.text
    assert pack.json()["integrity"]["retained_count"] == 1

    review = client.post(
        "/api/cases/SYN-PRIVATE-PATH-01/review",
        json={"action": "under_review", "note": "Synthetic evidence inspection"},
    )
    assert review.status_code == 200
    assert "frame_path" not in review.json()["evidence"][0]
    assert secret not in review.text
    assert store.get("SYN-PRIVATE-PATH-01").evidence[0].frame_path == secret


def test_dashboard_does_not_expose_case_filesystem_path(tmp_path, monkeypatch):
    client, _, secret = _client(tmp_path, monkeypatch)
    result = client.get("/api/dashboard?centre_id=DEMO-KA-104")
    assert result.status_code == 200
    assert secret not in result.text
