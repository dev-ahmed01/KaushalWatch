"""Local-only post-start judge-day smoke probe.

Checks actual FastAPI + Next responses instead of assuming a process that
survived two seconds can present evidence. Never calls remote services,
downloads footage, modifies cases, or infers real model/field accuracy.
"""
from __future__ import annotations

import argparse
import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_JSON = 1024 * 1024
MAX_HTML = 1024 * 1024
MAX_PDF = 2 * 1024 * 1024
EXPECTED_CASE = "SIM-KA-104-ATT"
EXPECTED_CENTRE = "DEMO-KA-104"


class RuntimeProbeError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(ProxyHandler({}), NoRedirect())


def port(value: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("Not an integer port") from exc
    if not (1024 <= n <= 65535):
        raise argparse.ArgumentTypeError("Use an unprivileged TCP port (1024..65535)")
    return n


def check_ports_free(api_port: int, web_port: int) -> dict:
    if api_port == web_port:
        raise RuntimeProbeError("Web and API must use different ports")
    for number, label in ((api_port, "API"), (web_port, "web")):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", number))
            except OSError as exc:
                raise RuntimeProbeError(f"{label} port {number} already occupied; cannot trust a previous process") from exc
    return {"ports_available": True, "api_port": api_port, "web_port": web_port}


def _read(port_number: int, url_path: str, *, label: str, limit: int) -> tuple[bytes, str]:
    request = Request(f"http://127.0.0.1:{port_number}{url_path}",
                      headers={"Cache-Control": "no-cache", "Accept": "*/*"},
                      method="GET")
    try:
        with OPENER.open(request, timeout=3) as response:
            if response.status != 200:
                raise RuntimeProbeError(f"{label}: unexpected HTTP response")
            body = response.read(limit + 1)
            mime = response.headers.get("Content-Type", "").lower()
    except (OSError, HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeProbeError(f"{label}: local service unavailable") from exc
    if len(body) > limit:
        raise RuntimeProbeError(f"{label}: unexpected oversized response")
    return body, mime


def _json_endpoint(port_number: int, url_path: str, label: str):
    raw, mime = _read(port_number, url_path, label=label, limit=MAX_JSON)
    if "application/json" not in mime:
        raise RuntimeProbeError(f"{label}: JSON content type missing")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeProbeError(f"{label}: unreadable JSON") from exc


def probe_once(api_port: int, web_port: int) -> dict:
    if api_port == web_port:
        raise RuntimeProbeError("Web and API ports must differ")
    started = time.monotonic()

    health = _json_endpoint(api_port, "/api/health", "API health")
    if (not isinstance(health, dict) or health.get("ok") is not True
            or health.get("service") != "kaushalwatch-api"):
        raise RuntimeProbeError("API health: wrong service/health result")

    listing = _json_endpoint(api_port, "/api/centres", "Centre list")
    if (not isinstance(listing, dict) or not isinstance(listing.get("centres"), list)
            or not isinstance(listing.get("total"), int)
            or listing["total"] != len(listing["centres"])
            or not any(isinstance(c, dict) and c.get("centre_id") == EXPECTED_CENTRE
                       for c in listing["centres"])):
        raise RuntimeProbeError("Centre list: required seeded demo centre is missing")

    cases = _json_endpoint(api_port, "/api/cases", "Saved case list")
    if not isinstance(cases, list):
        raise RuntimeProbeError("Saved case list: unexpected data type")
    case = next((c for c in cases if isinstance(c, dict)
                 and c.get("case_id") == EXPECTED_CASE), None)
    if (case is None or case.get("centre_id") != EXPECTED_CENTRE
            or not isinstance(case.get("details"), dict)
            or case["details"].get("simulated") is not True):
        raise RuntimeProbeError("Saved case list: approved synthetic review fixture missing")

    evidence = _json_endpoint(api_port,
                              f"/api/cases/{EXPECTED_CASE}/evidence-pack",
                              "Saved evidence pack")
    if (not isinstance(evidence, dict) or not isinstance(evidence.get("case"), dict)
            or evidence["case"].get("case_id") != EXPECTED_CASE
            or evidence["case"].get("centre_id") != EXPECTED_CENTRE
            or not isinstance(evidence.get("review"), dict)
            or not isinstance(evidence.get("integrity"), dict)):
        raise RuntimeProbeError("Saved evidence pack: unmatched case/review source")

    pdf, mime = _read(api_port, f"/api/centres/{EXPECTED_CENTRE}/report.pdf",
                      label="Centre PDF", limit=MAX_PDF)
    if "application/pdf" not in mime or not pdf.startswith(b"%PDF-"):
        raise RuntimeProbeError("Centre PDF: real PDF data unavailable")

    html, mime = _read(web_port, "/demo/mission",
                       label="Judge mission page", limit=MAX_HTML)
    if ("text/html" not in mime or b"KaushalWatch" not in html
            or b"A centre reports." not in html
            or b"Controlled SIH scenarios" not in html):
        raise RuntimeProbeError("Judge mission page: expected controlled UI not served")

    return {
        "status": "localhost_judge_runtime_ready",
        "scope": "synthetic_controlled_demo_not_field_qualified",
        "api_health": True,
        "seeded_centre": EXPECTED_CENTRE,
        "saved_case": EXPECTED_CASE,
        "saved_case_simulated": True,
        "evidence_pack_bound_to_case": True,
        "pdf_signature_verified": True,
        "mission_html_served": True,
        "checks": 6,
        "elapsed_probe_seconds": round(time.monotonic() - started, 3),
        "limitations": "Checks local HTTP responses only, not browser JS, independent camera accuracy, GPU or authorised real-centre data.",
    }


def probe_until_ready(api_port: int, web_port: int, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last = "No response"
    while True:
        try:
            return probe_once(api_port, web_port)
        except RuntimeProbeError as exc:
            last = str(exc)
        if time.monotonic() >= deadline:
            raise RuntimeProbeError(f"Timed out waiting for real judge runtime: {last}")
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))


def main() -> None:
    p = argparse.ArgumentParser(description="Validate actual localhost controlled presentation API + web")
    p.add_argument("--api-port", type=port, default=8000)
    p.add_argument("--web-port", type=port, default=3000)
    p.add_argument("--timeout-seconds", type=int, default=60)
    p.add_argument("--once", action="store_true")
    p.add_argument("--check-ports-free", action="store_true")
    args = p.parse_args()
    if not (1 <= args.timeout_seconds <= 180):
        p.error("Timeout must be 1..180 seconds")
    try:
        result = (check_ports_free(args.api_port, args.web_port) if args.check_ports_free
                  else probe_once(args.api_port, args.web_port) if args.once
                  else probe_until_ready(args.api_port, args.web_port, args.timeout_seconds))
    except RuntimeProbeError as exc:
        print(json.dumps({"ready": False, "reason": str(exc)[:250]}))
        raise SystemExit(2) from exc
    print(json.dumps({"ready": True, **result}, indent=2))


if __name__ == "__main__":
    main()
