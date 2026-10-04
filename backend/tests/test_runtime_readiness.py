import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as app_main
from app.services.person_detector import DetectorInfo


def test_runtime_readiness_marks_practical_processing_but_non_authoritative(tmp_path, monkeypatch):
    zones = tmp_path / "work_zones.json"
    zones.write_text('{"default": [], "authorized": []}', encoding="utf-8")
    monkeypatch.setattr(app_main, "DEFAULT_WORK_ZONES", zones)
    monkeypatch.setattr(
        app_main.PRACTICAL_PIPELINE.detector,
        "info",
        DetectorInfo(
            backend="hog",
            mode="fallback",
            authoritative=False,
            message="Non-authoritative fallback detector active.",
        ),
    )

    client = TestClient(app_main.app)
    response = client.get("/api/runtime-readiness")

    assert response.status_code == 200
    body = response.json()
    practical = body["practical_work"]
    assert practical["ready"] is False
    assert practical["processing_available"] is True
    assert practical["backend"] == "hog"
    assert practical["authoritative"] is False
    assert "conclusions are withheld" in practical["message"].lower()


def test_runtime_readiness_marks_practical_ready_with_authoritative_detector(tmp_path, monkeypatch):
    zones = tmp_path / "work_zones.json"
    zones.write_text('{"default": [], "authorized": []}', encoding="utf-8")
    monkeypatch.setattr(app_main, "DEFAULT_WORK_ZONES", zones)
    monkeypatch.setattr(
        app_main.PRACTICAL_PIPELINE.detector,
        "info",
        DetectorInfo(
            backend="openvino",
            mode="primary",
            authoritative=True,
            message="Validated OpenVINO detector active.",
        ),
    )

    client = TestClient(app_main.app)
    response = client.get("/api/runtime-readiness")

    assert response.status_code == 200
    body = response.json()
    practical = body["practical_work"]
    assert practical["ready"] is True
    assert practical["processing_available"] is True
    assert practical["backend"] == "openvino"
    assert practical["authoritative"] is True
    assert "openvino detector" in practical["message"].lower()
