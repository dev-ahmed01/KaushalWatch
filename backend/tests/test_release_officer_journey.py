"""Synthetic, isolated API-level SIH officer journey contract.

Exercises a *real* locally generated CCTV-like video through the FastAPI
upload/pipeline, persisted privacy evidence, centre state, case review,
audit, insights and deterministic (non-provider) assistant query. This is
NOT validation of model accuracy or any actual training centre.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.centre_settings import CentreSettingsStore
from app.services.video_pipeline import VideoCompliancePipeline


def _dark_camera_clip(path: Path):
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120)
    )
    assert writer.isOpened()
    try:
        for _ in range(30):
            writer.write(np.zeros((120, 160, 3), dtype=np.uint8))
    finally:
        writer.release()
    assert path.stat().st_size > 0


def test_uploaded_unusable_camera_evidence_is_reviewed_not_attendance_truth(
    tmp_path, monkeypatch
):
    # Synthetic data and new stores are isolated from both the checked-in
    # stage configuration and existing operator data on disk.
    store = CaseStore(tmp_path / "cases.json")
    history = AnalysisHistoryStore(tmp_path / "history.json")
    settings = CentreSettingsStore(tmp_path / "settings.json")
    pipeline = VideoCompliancePipeline(
        tmp_path / "evidence", tmp_path / "evidence-index.json"
    )
    monkeypatch.setattr(app_main, "STORE", store)
    monkeypatch.setattr(app_main, "HISTORY", history)
    monkeypatch.setattr(app_main, "CENTRE_SETTINGS", settings)
    monkeypatch.setattr(app_main, "PIPELINE", pipeline)
    monkeypatch.setattr(app_main, "DATA", tmp_path)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    token = "SyntheticOnly_Officer_Key_0123456789ABCDEF"
    monkeypatch.setenv(
        "KAUSHALWATCH_REVIEW_TOKENS_JSON",
        json.dumps({"reviewer-test-01": token}),
    )

    source_video = tmp_path / "unusable-camera.avi"
    _dark_camera_clip(source_video)
    client = TestClient(app_main.app)
    upload = client.post(
        "/api/process-video",
        data={
            "centre_id": "DEMO-KA-207",
            "batch_id": "ELEC-2026-09",
            "camera_id": "WORKSHOP-CAM-SYNTHETIC",
            "reported_attendance": "21",
        },
        files={
            "file": (
                "unusable-camera.avi",
                source_video.read_bytes(),
                "video/x-msvideo",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    result = upload.json()
    assert result["trusted_sample_ratio"] < 0.5
    assert result["case"] is not None
    case = result["case"]
    assert case["case_type"] == "camera_integrity"
    assert "suspended" in case["summary"].lower()
    assert case["reported_attendance"] is None
    assert len(case["evidence"]) == 1

    evidence = case["evidence"][0]
    assert evidence["metadata"]["privacy_transform"] == (
        "full_frame_blur_due_untrusted_camera"
    )
    assert "frame_path" not in evidence
    case_id = case["case_id"]
    saved = store.get(case_id)
    assert saved is not None
    # The server retains its private local path for integrity and recovery,
    # but must never send that filesystem location to a browser/client.
    evidence_path = Path(saved.evidence[0].frame_path)
    assert evidence_path.is_file()
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == evidence["sha256"]
    assert evidence_path.is_relative_to(tmp_path / "evidence")
    assert saved.case_type == "camera_integrity"

    rows = client.get("/api/analysis-history?centre_id=DEMO-KA-207")
    assert rows.status_code == 200
    assert len(rows.json()["rows"]) == 1
    assert rows.json()["rows"][0]["analysis_type"] == "attendance"
    assert rows.json()["rows"][0]["outcome"] == "blocked"

    centre = client.get("/api/centres/DEMO-KA-207")
    assert centre.status_code == 200
    assert centre.json()["camera_status"] == "attention"

    pack = client.get(f"/api/cases/{case_id}/evidence-pack")
    assert pack.status_code == 200
    assert pack.json()["review"]["status"] == "open"
    assert pack.json()["integrity"]["retained_count"] == 1

    # Proof exists, but a keyless remote actor cannot record a decision.
    denied = client.post(
        f"/api/cases/{case_id}/review",
        json={"action": "under_review"},
    )
    assert denied.status_code == 401
    assert store.get(case_id).review_history == []

    started = client.post(
        f"/api/cases/{case_id}/review",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "under_review",
            "note": "Synthetic insufficient-evidence incident queued for review.",
        },
    )
    assert started.status_code == 200
    assert started.json()["review_history"][-1]["actor"] == "reviewer-test-01"

    virtual = client.post(
        f"/api/cases/{case_id}/review",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "virtual_verification",
            "note": "Synthetic camera visibility remains unsuitable.",
        },
    )
    assert virtual.status_code == 200
    assert virtual.json()["status"] == "virtual_verification"
    assert len(virtual.json()["review_history"]) == 2

    reloaded = CaseStore(tmp_path / "cases.json").get(case_id)
    assert reloaded is not None
    assert reloaded.status.value == "virtual_verification"
    assert len(reloaded.review_history) == 2

    actions = client.get("/api/actions")
    assert actions.status_code == 200
    assert any(
        item["case_id"] == case_id and item["kind"] == "camera"
        for item in actions.json()["actions"]
    )
    insights = client.get("/api/insights")
    assert insights.status_code == 200

    assistant = client.post(
        "/api/assistant/query",
        json={
            "centre_id": "DEMO-KA-207",
            "period": "7d",
            "question": "What is the latest camera evidence?",
        },
    )
    assert assistant.status_code == 200
    assert assistant.json()["grounded_in"]["centre_id"] == "DEMO-KA-207"

    report = client.get("/api/centres/DEMO-KA-207/report.pdf?period=7d")
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF-1.4")
