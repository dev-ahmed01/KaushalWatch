"""Public read-only sample API for the KaushalWatch recorded demonstration.

This deliberately does not import the FastAPI compliance application, touch
private media, accept uploads, or create officer/case/chat writes.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

SCENES = [
    {"id": "attendance", "source": "training-bay", "reported": 28, "observed": 19, "unit": "trainees", "kind": "simulated"},
    {"id": "infrastructure", "source": "workshop-floor", "reported": 3, "observed": 2, "unit": "training panels", "kind": "simulated"},
    {"id": "camera", "source": "east-corridor", "reported": 21, "observed": None, "unit": "trainees", "kind": "simulated"},
]

class Handler(BaseHTTPRequestHandler):
    server_version = "KaushalWatchSample/1.0"

    def _reply(self, status: int, data: dict, *, body: bool = True) -> None:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "public, max-age=30")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if body:
            self.wfile.write(raw)

    def _get(self, *, body: bool = True) -> None:
        path = urlsplit(self.path).path
        if path in ("/", "/healthz"):
            return self._reply(200, {
                "service": "kaushalwatch-public-showcase",
                "status": "ok",
                "simulation": True,
                "backend": "read-only-synthetic",
            }, body=body)
        if path == "/api/showcase/scenes":
            return self._reply(200, {
                "schema": "KW_PUBLIC_SYNTHETIC_SHOWCASE_V1",
                "simulation": True,
                "source": "procedural-recording-timed-scenario",
                "real_model_inference": False,
                "scenes": SCENES,
            }, body=body)
        return self._reply(404, {"detail": "Not found"}, body=body)

    def do_GET(self) -> None: self._get()

    def do_HEAD(self) -> None: self._get(body=False)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None: self._reply(405, {"detail": "Read-only demo API"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise SystemExit("Invalid PORT")
    print("Starting public read-only KaushalWatch simulation service", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
