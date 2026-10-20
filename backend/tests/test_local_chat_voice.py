"""Two-role private audio transport, idempotency and corruption denial."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app.main as main

def test_voice_round_trip_and_cross_centre_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.setattr(main,"DATA",tmp_path)
    client=TestClient(main.app)
    officer={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-104"}
    head={"X-KW-Demo-Actor":"demo-head-DEMO-KA-104"}
    stranger={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-303"}
    thread="thread-DEMO-KA-104-head"
    # A minimal matching EBML header is enough for transport validation.
    # This fixture does not assert that the payload decodes as audio.
    media=b"\x1a\x45\xdf\xa3"+b"\x80"*96
    def upload(actor):
        return client.post(f"/api/chatbox/threads/{thread}/voice",headers=actor,
            data={"idempotency_key":"voice-test-001","duration_ms":"1200"},
            files={"audio":("note.webm",media,"audio/webm")})
    sent=upload(officer)
    assert sent.status_code==200, sent.text
    message=sent.json()["message"]
    assert message["kind"]=="voice"
    assert message["body"] is None
    assert message["duration_ms"]==1200
    assert upload(officer).json()["message"]["id"]==message["id"]
    assert len(client.get(f"/api/chatbox/threads/{thread}/messages",
                 headers=head).json()["messages"])==1
    read=client.get("/api/chatbox/voice/"+message["id"],headers=head)
    assert read.status_code==200 and read.content==media
    assert read.headers["cache-control"]=="private, no-store"
    assert client.get("/api/chatbox/voice/"+message["id"],headers=stranger).status_code==404
    assert client.get("/api/chatbox/voice/"+message["id"]).status_code==403
    media_path=next((tmp_path/"chatbox_voice").glob("*.webm"))
    media_path.write_bytes(media+b"tampered")
    assert client.get("/api/chatbox/voice/"+message["id"],headers=officer).status_code==503

def test_voice_rejects_oversize_unknown_content_and_other_thread(tmp_path,monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    monkeypatch.setattr(main,"DATA",tmp_path)
    client=TestClient(main.app)
    actor={"X-KW-Demo-Actor":"demo-officer-DEMO-KA-104"}
    url="/api/chatbox/threads/thread-DEMO-KA-104-head/voice"
    params={"idempotency_key":"voice-test-002","duration_ms":"1200"}
    assert client.post(url,headers=actor,data=params,
        files={"audio":("bad.webm",b"wrong-signature-123","audio/webm")}).status_code==422
    assert client.post(url,headers=actor,data=params,
        files={"audio":("bad.txt",b"a"*100,"text/plain")}).status_code==422
    assert client.post(url,headers=actor,data=params,
        files={"audio":("huge.webm",b"\x1a\x45\xdf\xa3"+b"x"*(4*1024*1024),"audio/webm")}).status_code==422
    assert client.post("/api/chatbox/threads/thread-DEMO-KA-303-head/voice",
        headers=actor,data=params,files={"audio":("note.webm",b"\x1a\x45\xdf\xa3"+b"x"*50,"audio/webm")}).status_code==404
