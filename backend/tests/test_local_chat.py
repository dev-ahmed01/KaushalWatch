"""Text messages persist across actual demo roles; never expose another thread."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app.main as main

def test_chatbox_two_role_text_persistence_and_idempotency(tmp_path,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.setattr(main,"DATA",tmp_path)
    client=TestClient(main.app)
    officer={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-104"}
    head={"X-KW-Demo-Actor":"demo-head-DEMO-KA-104"}
    stranger={"X-KW-Demo-Actor":"demo-trainer-DEMO-KA-303"}
    thread="thread-DEMO-KA-104-head"
    assert client.get("/api/chatbox/threads",headers=officer).status_code==200
    first=client.post(f"/api/chatbox/threads/{thread}/messages",headers=officer,
                      json={"body":"Please verify the roster","idempotency_key":"send-001-a"})
    assert first.status_code==200, first.text
    again=client.post(f"/api/chatbox/threads/{thread}/messages",headers=officer,
                      json={"body":"Please verify the roster","idempotency_key":"send-001-a"})
    assert again.json()["message"]["id"]==first.json()["message"]["id"]
    reply=client.post(f"/api/chatbox/threads/{thread}/messages",headers=head,
                      json={"body":"I will check the centre log","idempotency_key":"reply-001-b"})
    assert reply.status_code==200
    history=client.get(f"/api/chatbox/threads/{thread}/messages",headers=officer)
    assert [x["body"] for x in history.json()["messages"]]==[
        "Please verify the roster","I will check the centre log"]
    assert client.get(f"/api/chatbox/threads/{thread}/messages",headers=stranger).status_code==404
    assert client.get(f"/api/chatbox/threads/{thread}/messages").status_code==403
    assert client.post(f"/api/chatbox/threads/{thread}/messages",headers=head,
                       json={"body":" ","idempotency_key":"blank-text"}).status_code==422

def test_chatbox_protected_environment_never_allows_client_selected_demo_actor(tmp_path,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","disabled")
    monkeypatch.setattr(main,"DATA",tmp_path)
    client=TestClient(main.app)
    response=client.get("/api/chatbox/threads",
        headers={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-104"})
    assert response.status_code!=200
