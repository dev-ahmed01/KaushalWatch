"""Phase 4: real-loopback TCP loss, lost ACK, restart, re-ACK and byte proof."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
import io
import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/"backend")]
import app.main as app_main
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.offline_queue import EdgeEventQueue
from app.services.edge_transport import prepare_upload, read_sync_state
from edge import agent


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(app_main, "STORE", CaseStore(tmp_path/"cases.json"))
    monkeypatch.setattr(app_main, "HISTORY", AnalysisHistoryStore(tmp_path/"history.json"))
    monkeypatch.setattr(app_main, "DATA", tmp_path)
    monkeypatch.setenv("KAUSHALWATCH_ENV", "development")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "demo")
    monkeypatch.delenv("KAUSHALWATCH_EDGE_SYNC_CENTRES_JSON", raising=False)
    return TestClient(app_main.app)


def event_payload(centre="DEMO-KA-207"):
    return {
        "centre_id":centre,"batch_id":"SYNTHETIC-TRAINING-01",
        "analysis_type":"attendance","outcome":"blocked",
        "summary":"Camera-observation fixture; human review pending.",
        "details":{"decision":"camera_evidence_insufficient",
                   "detector_authoritative":False,"detector_failures":1,
                   "trusted_sample_ratio":0.0,"simulated":True},
        "privacy":{"raw_video_included":False,"face_embeddings":False,
                   "individual_identification":False},
    }


def call_sync(queue, url):
    stdout=io.StringIO()
    with redirect_stdout(stdout):
        code=agent.sync(SimpleNamespace(queue=str(queue.path),url=url,timeout=0.6))
    return code,json.loads(stdout.getvalue())


@contextmanager
def server(api, *, fail_first_ack=False):
    caught=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path=="/api/edge/sync"
            body=self.rfile.read(int(self.headers["Content-Length"]))
            caught.append(body)
            response=api.post(self.path,content=body,
                 headers={"Content-Type":"application/json"})
            if fail_first_ack and len(caught)==1:
                # The server has durably accepted the event but the HTTP
                # acknowledgement is lost, forcing an idempotent re-ACK.
                status,output=503,b'{"error":"ACK dropped after commit"}'
            else:
                status,output=response.status_code,response.content
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(output)))
            self.end_headers()
            self.wfile.write(output)
        def log_message(self,*args):
            pass
    http=HTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_address[1]}",caught
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def test_actual_socket_cut_restart_reconnect_and_duplicate_ack(tmp_path,monkeypatch):
    api=setup(tmp_path,monkeypatch)
    queue=EdgeEventQueue(tmp_path/"durable-queue.json")
    queue.enqueue("analysis_summary",event_payload())
    queue.enqueue("analysis_summary",event_payload())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        closed_port=sock.getsockname()[1]
    # No server is listening: a real refused local TCP connection.
    code,offline=call_sync(queue,f"http://127.0.0.1:{closed_port}")
    assert code==2 and offline["offline"] is True
    assert offline["observed_request_body_bytes"]==0
    assert len(queue.pending())==2
    # Edge process restart is represented by a fresh queue object on disk.
    restarted=EdgeEventQueue(queue.path)
    assert len(restarted.pending())==2
    with server(api,fail_first_ack=True) as (url,bodies):
        code,dropped=call_sync(restarted,url)
        assert code==2 and dropped["synced"]==0
        assert len(restarted.pending())==2
        assert len(app_main.HISTORY.list())==2
        code,received=call_sync(restarted,url)
        assert code==0
        assert received["synced"]==2 and received["remaining"]==0
        assert received["already_accepted"]==2
        assert received["observed_request_body_bytes"]==len(bodies[-1])
        assert len(bodies)==2
        assert all(b'"raw_video":' not in raw and b'"face_embeddings":' not in raw for raw in bodies)
        assert len(app_main.HISTORY.list())==2  # exactly once despite duplicate HTTP POST
    metrics=read_sync_state(queue.path)
    assert metrics["attempts"]==3 and metrics["failures"]==2
    assert metrics["acknowledged_total"]==2 and metrics["duplicate_acks_total"]==2
    assert metrics["observed_request_body_bytes"]==received["observed_request_body_bytes"]
    assert metrics["observed_response_body_bytes"]==received["observed_response_body_bytes"]
    assert metrics["last_success_utc"]
    assert len(EdgeEventQueue(queue.path).pending())==0


def test_replayed_event_id_from_different_centre_is_conflict(tmp_path,monkeypatch):
    client=setup(tmp_path,monkeypatch)
    queue=EdgeEventQueue(tmp_path/"q.json")
    original=queue.enqueue("analysis_summary",event_payload("CENTRE-A"))
    with server(client) as (url, _):
        assert call_sync(queue,url)[0]==0
    stolen=json.loads(json.dumps(original))
    stolen["payload"]["centre_id"]="CENTRE-B"
    response=client.post("/api/edge/sync",json={"events":[stolen]})
    assert response.status_code==200
    assert response.json()["accepted_event_ids"]==[]
    assert response.json()["rejected_events"][0]["reason"]=="event_id_conflict"
    assert len(app_main.HISTORY.list())==1


def test_centre_scope_policy_denies_other_centre(tmp_path,monkeypatch):
    client=setup(tmp_path,monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE","token")
    key="Synthetic_DeviceCredential_NotForUseOutsideTests_0123456789"
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON",json.dumps({"lab-edge-01":key}))
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_CENTRES_JSON",
                       json.dumps({"lab-edge-01":["CENTRE-A"]}))
    e=EdgeEventQueue(tmp_path/"q.json").enqueue("analysis_summary",event_payload("CENTRE-B"))
    response=client.post("/api/edge/sync",json={"events":[e]},
                         headers={"Authorization":f"Bearer {key}"})
    assert response.status_code==200
    assert response.json()["rejected_events"][0]["reason"]=="device_centre_scope_denied"
    assert app_main.HISTORY.list()==[]
    e2=EdgeEventQueue(tmp_path/"q2.json").enqueue("analysis_summary",event_payload("CENTRE-A"))
    permitted=client.post("/api/edge/sync",json={"events":[e2]},
                          headers={"Authorization":f"Bearer {key}"})
    assert permitted.status_code==200 and permitted.json()["accepted_count"]==1


def test_no_private_payload_leaves_edge_or_mixed_centre_batch(tmp_path,monkeypatch):
    client=setup(tmp_path,monkeypatch)
    q=EdgeEventQueue(tmp_path/"queue.json")
    unsafe=event_payload()
    unsafe["raw_video"]="BASE64_SHOULD_NEVER_TRANSFER"
    q.enqueue("analysis_summary",unsafe)
    with server(client) as (url,raw):
        code,result=call_sync(q,url)
        assert code==2 and result["privacy"]=="blocked_before_transport"
        assert raw==[]
    assert len(q.pending())==1
    q2=EdgeEventQueue(tmp_path/"multi.json")
    q2.enqueue("analysis_summary",event_payload("CENTRE-A"))
    q2.enqueue("analysis_summary",event_payload("CENTRE-B"))
    with pytest.raises(ValueError,match="Cross-centre"):
        prepare_upload(q2.pending())


def test_oversized_metadata_queue_cannot_silently_evict(tmp_path,monkeypatch):
    import app.services.offline_queue as module
    monkeypatch.setattr(module,"MAX_EDGE_QUEUE_EVENTS",1)
    q=EdgeEventQueue(tmp_path/"queue.json")
    original=q.enqueue("analysis_summary",event_payload())
    with pytest.raises(ValueError,match="capacity"):
        q.enqueue("analysis_summary",event_payload())
    assert [e["event_id"] for e in q.pending()]==[original["event_id"]]


def test_lost_ack_same_event_from_other_device_does_not_reack(tmp_path,monkeypatch):
    client=setup(tmp_path,monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE","token")
    a="A_Synthetic_DeviceToken_0123456789abcdef0123456789"
    b="B_Synthetic_DeviceToken_0123456789abcdef0123456789"
    monkeypatch.setenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON",
                       json.dumps({"edge-a":a,"edge-b":b}))
    e=EdgeEventQueue(tmp_path/"q.json").enqueue("analysis_summary",event_payload())
    first=client.post("/api/edge/sync",json={"events":[e]},
                      headers={"Authorization":f"Bearer {a}"})
    assert first.json()["accepted_count"]==1
    second=client.post("/api/edge/sync",json={"events":[e]},
                       headers={"Authorization":f"Bearer {b}"})
    assert second.json()["accepted_event_ids"]==[]
    assert second.json()["rejected_events"][0]["reason"]=="event_id_conflict"
