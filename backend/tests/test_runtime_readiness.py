import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as app_main


def test_runtime_readiness_marks_practical_unavailable_without_yolo(tmp_path, monkeypatch):
    zones = tmp_path / "work_zones.json"
    zones.write_text('{"default": []}', encoding="utf-8")
    monkeypatch.setattr(app_main, "DEFAULT_WORK_ZONES", zones)
    monkeypatch.setattr(
        app_main.importlib.util,
        "find_spec",
        lambda name: None if name == "ultralytics" else object(),
    )

    client = TestClient(app_main.app)
    response = client.get("/api/runtime-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["practical_work"]["ready"] is False
    assert body["practical_work"]["backend"] == "yolo11"
    assert "install backend/requirements-yolo-demo.txt" in body["practical_work"]["message"].lower()


def test_runtime_readiness_marks_practical_ready_with_yolo_and_zones(tmp_path, monkeypatch):
    zones = tmp_path / "work_zones.json"
    zones.write_text('{"default": []}', encoding="utf-8")
    monkeypatch.setattr(app_main, "DEFAULT_WORK_ZONES", zones)
    monkeypatch.setattr(
        app_main.importlib.util,
        "find_spec",
        lambda name: object(),
    )

    client = TestClient(app_main.app)
    response = client.get("/api/runtime-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["practical_work"]["ready"] is True
    assert "yolo runtime" in body["practical_work"]["message"].lower()
