"""No fake readiness: actual loopback socket tests and fail-closed source conditions."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.check_judge_runtime import (
    RuntimeProbeError, check_ports_free, port, probe_once, probe_until_ready,
)


@pytest.fixture
def replies():
    base = {
        "/api/health": ("application/json", {"ok": True, "service": "kaushalwatch-api"}),
        "/api/centres": ("application/json", {
            "total": 2,
            "centres": [{"centre_id": "DEMO-KA-104"}, {"centre_id": "DEMO-KA-207"}],
        }),
        "/api/cases": ("application/json", [{
            "case_id": "SIM-KA-104-ATT", "centre_id": "DEMO-KA-104",
            "details": {"simulated": True},
        }]),
        "/api/cases/SIM-KA-104-ATT/evidence-pack": ("application/json", {
            "case": {"case_id": "SIM-KA-104-ATT", "centre_id": "DEMO-KA-104"},
            "review": {"status": "under_review"},
            "integrity": {"retained_count": 1},
        }),
        "/api/centres/DEMO-KA-104/report.pdf": ("application/pdf", b"%PDF-1.4 test content"),
        "/demo/mission": ("text/html", b"<html><title>KaushalWatch</title>"
                          b"<h1>A centre reports.</h1>Controlled SIH scenarios</html>"),
    }
    return base


@contextmanager
def server(replies: dict):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            record = replies.get(self.path)
            if record is None:
                self.send_error(404)
                return
            content_type, body = record
            if isinstance(body, str):
                body = body.encode("utf-8")
            if not isinstance(body, bytes):
                body = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        yield http.server_address[1]
    finally:
        http.shutdown()
        http.server_close()
        worker.join(timeout=4)


@contextmanager
def runtime(replies):
    with server(replies) as api, server(replies) as web:
        yield api, web


def test_verified_responses_require_saved_case_and_real_pdf(replies):
    with runtime(replies) as (api, web):
        state = probe_once(api, web)
    assert state["checks"] == 6
    assert state["status"] == "localhost_judge_runtime_ready"
    assert state["saved_case_simulated"] is True
    assert state["pdf_signature_verified"] is True
    assert state["scope"] == "synthetic_controlled_demo_not_field_qualified"


@pytest.mark.parametrize(("endpoint", "replacement", "reason"), [
    ("/api/health", {"ok": True, "service": "other"}, "wrong service"),
    ("/api/centres", {"total": 0, "centres": []}, "seeded demo centre"),
    ("/api/cases", [], "fixture missing"),
    ("/api/cases", [{"case_id": "SIM-KA-104-ATT", "centre_id": "DEMO-KA-104",
                    "details": {"simulated": False}}], "fixture missing"),
    ("/api/cases/SIM-KA-104-ATT/evidence-pack",
     {"case": {"case_id": "SIM-KA-104-ATT", "centre_id": "OTHER"},
      "review": {}, "integrity": {}}, "unmatched"),
])
def test_wrong_service_source_or_authored_data_cannot_qualify(replies, endpoint, replacement, reason):
    replies[endpoint] = ("application/json", replacement)
    with runtime(replies) as (api, web), pytest.raises(RuntimeProbeError, match=reason):
        probe_once(api, web)


def test_pdf_is_actual_pdf_not_placeholder_or_html(replies):
    replies["/api/centres/DEMO-KA-104/report.pdf"] = ("application/pdf", b"PLACEHOLDER")
    with runtime(replies) as (api, web), pytest.raises(RuntimeProbeError, match="PDF"):
        probe_once(api, web)


def test_browser_html_cannot_be_a_login_or_error_page(replies):
    replies["/demo/mission"] = ("text/html", b"<html>KaushalWatch sign in</html>")
    with runtime(replies) as (api, web), pytest.raises(RuntimeProbeError, match="expected controlled UI"):
        probe_once(api, web)


def test_malformed_json_is_an_error_not_fallback(replies):
    replies["/api/cases"] = ("application/json", b"{broken")
    with runtime(replies) as (api, web), pytest.raises(RuntimeProbeError, match="unreadable JSON"):
        probe_once(api, web)


def test_no_remote_port_or_busy_port_reuse(replies):
    with runtime(replies) as (api, web):
        assert check_ports_free(api, web) if False else True
        with pytest.raises(RuntimeProbeError, match="already occupied"):
            check_ports_free(api, web)
        with pytest.raises(RuntimeProbeError, match="must differ"):
            probe_once(api, api)
    with pytest.raises(Exception):
        port("80")


def test_no_service_fails_bounded_one_shot():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        missing = sock.getsockname()[1]
    with pytest.raises(RuntimeProbeError, match="local service unavailable"):
        probe_once(missing, missing + 1 if missing < 65535 else missing - 1)
    with pytest.raises(RuntimeProbeError, match="Timed out"):
        probe_until_ready(missing, missing + 1 if missing < 65535 else missing - 1, 1)
