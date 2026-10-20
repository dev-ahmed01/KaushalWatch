"""Private recorded voice note transport: validation, ACL, stored SHA, read after refresh."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app.main as main

def test_voice_note_two_role_storage_private_playback_and_integrity(tmp_path,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.setattr(main,"DATA",tmp_path)
    client=TestClient(main.app)
    sender={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-104"}
    recipient={"X-KW-Demo-Actor":"demo-head-DEMO-KA-104"}
    outsider={"X-KW-Demo-Actor":"demo-head-DEMO-KA-303"}
    thread="thread-DEMO-KA-104-head"
    audio=bytes.fromhex("1a45dfa3")+"synthetic media byte fixture".encode()
    res=client.post(f"/api/chatbox/threads/{thread}/voice",headers=sender,
        data={"duration_ms":"2000","idempotency_key":"audio-note-demo-001"},
        files={"audio":("note.webm",audio,"audio/webm")})
    assert res.status_code==200,res.text
    msg=res.json()["message"]
    assert msg["kind"]=="voice"
    assert msg["sha256"]
    assert msg["byte_size"]==len(audio)
    got=client.get(f"/api/chatbox/threads/{thread}/voice/{msg['id']}",headers=recipient)
    assert got.status_code==200
    assert got.content==audio
    assert got.headers["cache-control"].startswith("private")
    assert client.get(f"/api/chatbox/threads/{thread}/voice/{msg['id']}",headers=outsider).status_code==404
    assert client.get(f"/api/chatbox/threads/{thread}/voice/{msg['id']}").status_code==403
    assert not any((tmp_path/"evidence").glob("*")) if (tmp_path/"evidence").exists() else True
    saved=list((tmp_path/"private_chat_voice").iterdir())
    assert len(saved)==1
    assert msg["id"] in saved[0].name
    saved[0].write_bytes(b"tampered")
    assert client.get(f"/api/chatbox/threads/{thread}/voice/{msg['id']}",headers=recipient).status_code==503

def test_voice_note_rejects_invalid_audio_and_untrusted_user(tmp_path,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.setattr(main,"DATA",tmp_path)
    client=TestClient(main.app)
    sender={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-104"}
    thread="thread-DEMO-KA-104-head"
    def send(payload,mime="audio/webm",duration="2000"):
        return client.post(f"/api/chatbox/threads/{thread}/voice",headers=sender,
            data={"duration_ms":duration,"idempotency_key":"invalid-audio-123"},
            files={"audio":("note.webm",payload,mime)})
    assert send(b"not-a-media-file").status_code==415
    assert send(bytes.fromhex("1a45dfa3")+b"x",duration="90001").status_code==415
    assert send(bytes.fromhex("1a45dfa3")+b"x",mime="application/octet-stream").status_code==415
    assert client.post(f"/api/chatbox/threads/{thread}/voice",
        data={"duration_ms":"1000","idempotency_key":"missing-actor"},
        files={"audio":("note.webm",bytes.fromhex("1a45dfa3")+b"x","audio/webm")}).status_code==403
