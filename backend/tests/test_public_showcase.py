"""Exercise the public read-only simulation service without exposing main FastAPI."""
from __future__ import annotations
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from app.public_showcase import Handler


def test_public_showcase_is_read_only() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        client = HTTPConnection(host, port, timeout=5)
        client.request("GET", "/healthz")
        response = client.getresponse()
        health = json.loads(response.read())
        assert response.status == 200
        assert health["simulation"] is True
        assert health["backend"] == "read-only-synthetic"

        client.request("GET", "/api/showcase/scenes")
        response = client.getresponse()
        result = json.loads(response.read())
        assert response.status == 200
        assert [r["id"] for r in result["scenes"]] == ["attendance", "infrastructure", "camera"]
        assert [(r["reported"], r["observed"]) for r in result["scenes"]] == [(28, 19), (3, 2), (21, None)]
        assert result["real_model_inference"] is False

        client.request("POST", "/api/showcase/scenes", body=b"{}", headers={"Content-Type": "application/json"})
        response = client.getresponse()
        response.read()
        assert response.status == 405

        client.request("GET", "/api/cases")
        response = client.getresponse()
        response.read()
        assert response.status == 404
        client.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
