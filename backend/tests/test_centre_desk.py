"""Synthetic Centre Desk operational persistence and isolation."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as main

def test_centre_desk_batches_contacts_and_task_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setattr(main, "DATA", tmp_path)
    client = TestClient(main.app)
    first = client.get("/api/centre-desk?centre_id=DEMO-KA-104")
    assert first.status_code == 200, first.text
    day = first.json()["day"]
    assert day["simulated"] is True
    assert len(day["batches"]) == 2
    assert day["counts"]["trainers_present"] is None
    assert day["counts"]["messages_pending"] is None
    assert day["date_local"]
    assert len(day["contacts"]) == 3
    assert all(person["simulated"] for person in day["contacts"])
    task = day["tasks"][0]["id"]
    update = client.post(f"/api/centre-desk/DEMO-KA-104/tasks/{task}/status",
                         json={"status":"acknowledged"})
    assert update.status_code == 200, update.text
    assert update.json()["task"]["status"] == "acknowledged"
    assert len(update.json()["audit"]) == 1
    repeat = client.post(f"/api/centre-desk/DEMO-KA-104/tasks/{task}/status",
                         json={"status":"acknowledged"})
    assert repeat.status_code == 200
    assert len(repeat.json()["audit"]) == 1
    assert any(t["status"] == "acknowledged" for t in client.get(
        "/api/centre-desk?centre_id=DEMO-KA-104").json()["day"]["tasks"])
    assert all(t["status"] == "pending" for t in client.get(
        "/api/centre-desk?centre_id=DEMO-KA-303").json()["day"]["tasks"])
    assert client.post("/api/centre-desk/DEMO-KA-303/tasks/" + task + "/status",
                       json={"status":"resolved"}).status_code == 404

def test_centre_desk_rejects_unsafe_and_protected_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(main,"DATA",tmp_path)
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    client=TestClient(main.app)
    task="task-DEMO-KA-104-trainer"
    assert client.post(f"/api/centre-desk/DEMO-KA-104/tasks/{task}/status",
                       json={"status":"not_really_sent"}).status_code == 422
    assert client.get("/api/centre-desk?centre_id=unknown").status_code == 404
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","disabled")
    assert client.get("/api/centre-desk").status_code != 200
