"""Reproducible real-loopback HTTP disconnect/reconnect/lost-ACK transport drill.

Uses the REAL current /api/edge/sync route, generated privacy-safe aggregate
event fixtures and actual HTTP request-body byte counts. No model, no footage,
no cloud, no claims of WAN or production compliance.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"backend")]
from fastapi.testclient import TestClient
import app.main as api
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.offline_queue import EdgeEventQueue
from app.services.edge_transport import read_sync_state
from edge import agent


def attempt(queue: Path, url: str) -> tuple[int, dict]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = agent.sync(SimpleNamespace(queue=str(queue),url=url,timeout=0.6))
    return result, json.loads(output.getvalue())


def run() -> dict:
    mode = os.getenv("KAUSHALWATCH_ENV", "development").lower()
    if mode not in {"development","local","test"}:
        raise ValueError("Offline fixture rehearsal forbidden in protected/pilot/production")
    if os.getenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "demo") != "demo":
        raise ValueError("Use isolated development/demo edge sync for local transport rehearsal")
    with TemporaryDirectory(prefix="kw-phase4-") as temp:
        root = Path(temp)
        api.DATA = root
        api.STORE = CaseStore(root/"cases.json")
        api.HISTORY = AnalysisHistoryStore(root/"history.json")
        api_client = TestClient(api.app)
        queue = EdgeEventQueue(root/"edge-queue.json")
        for _ in range(2):
            queue.enqueue("analysis_summary", {
                "centre_id":"DEMO-KA-207","batch_id":"FIXTURE-OFFLINE-01",
                "analysis_type":"attendance","outcome":"blocked",
                "summary":"Synthetic camera observation withheld; no attendance inference.",
                "details":{
                    "decision":"camera_evidence_insufficient",
                    "detector_authoritative":False,
                    "detector_failures":1,"trusted_sample_ratio":0.0,
                    "simulated":True,
                },
                "privacy":{"raw_video_included":False,"face_embeddings":False,
                           "individual_identification":False},
            })
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            offline_port = sock.getsockname()[1]
        cut_code, cut = attempt(queue.path, f"http://127.0.0.1:{offline_port}")
        if cut_code != 2 or len(EdgeEventQueue(queue.path).pending()) != 2:
            raise RuntimeError("Controlled socket outage did not retain durable queue")
        # New EdgeEventQueue instance stands in for device process restart.
        restarted = EdgeEventQueue(queue.path)
        received: list[int] = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/api/edge/sync":
                    self.send_error(404);return
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append(len(body))
                response = api_client.post(self.path, content=body,
                    headers={"Content-Type":"application/json"})
                if len(received) == 1:
                    # Server has committed the event; lose ONLY its first ACK.
                    code, out = 503, b'{"detail":"simulated lost HTTP acknowledgement"}'
                else:
                    code, out = response.status_code, response.content
                self.send_response(code)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(out)))
                self.end_headers()
                self.wfile.write(out)
            def log_message(self,*args):
                return
        server=HTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            address = f"http://127.0.0.1:{server.server_address[1]}"
            lost_code,lost = attempt(restarted.path,address)
            delivered_code,delivered=attempt(restarted.path,address)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        metrics=read_sync_state(queue.path)
        stored = len(api.HISTORY.list())
        if not (lost_code==2 and delivered_code==0
                and lost["remaining"]==2 and delivered["synced"]==2
                and delivered["already_accepted"]==2
                and stored==2 and not restarted.pending()
                and metrics["attempts"]==3 and metrics["failures"]==2
                and delivered["observed_request_body_bytes"]==received[-1]):
            raise RuntimeError("Offline delivery, source ledger or duplicate-replay verification failed")
        return {
            "schema":"KW_OFFLINE_TRANSPORT_DRILL_V1",
            "status":"measured_loopback_fixture_not_field_qualified",
            "fixture":True,
            "network_cut_verified":True,
            "queue_survived_restart":True,
            "lost_ack_idempotent_reack":True,
            "server_event_rows":stored,
            "queued_before":2,"delivered":2,"remaining":0,
            "attempts":metrics["attempts"],"failed_attempts":metrics["failures"],
            "duplicate_ack_count":metrics["duplicate_acks_total"],
            "observed_request_body_bytes_final":delivered["observed_request_body_bytes"],
            "observed_response_body_bytes_final":delivered["observed_response_body_bytes"],
            "observed_request_body_bytes_all_received":sum(received),
            "last_success_utc":metrics["last_success_utc"],
            "raw_video_uploaded":False,
            "measurement_boundary":"Actual localhost HTTP bodies. Excludes headers/TCP/TLS; no WAN, camera model or equipment accuracy claim.",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled actual loopback offline sync drill")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    target = args.out.expanduser().resolve()
    if target.exists():
        raise SystemExit("Refusing to overwrite an existing measured transport report")
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as output:
        json.dump(report,output,indent=2)
        output.write("\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
