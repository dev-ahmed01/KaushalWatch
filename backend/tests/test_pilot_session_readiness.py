"""Protected HTTPS preflight must reject a browser with broken Redis."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import check_protected_staging as preflight


class _Response:
    def __init__(self, code, data=None, headers=None):
        self.status_code = code
        self._data = data
        self.headers = headers or {}

    def json(self):
        return self._data


class _Client:
    def __init__(self, session_status: int, session_payload: dict, cache: str):
        self.session_status = session_status
        self.session_payload = session_payload
        self.cache = cache

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def get(self, url: str, headers: dict):
        path = urlsplit(url).path
        if path == "/api/ready":
            return _Response(200, {"ready": True}, {"cache-control": "no-store"})
        if path == "/api/health":
            return _Response(200, {"ok": True})
        if path == "/api/review-access":
            return _Response(200, {"mode": "oidc", "required": True, "prototype_only": False})
        if path == "/api/cases":
            return _Response(401, headers={"www-authenticate": "Bearer"})
        if path == "/api/auth/status":
            return _Response(200, {"mode": "protected", "identityMode": "oidc",
                                   "authenticated": False}, {"cache-control": "no-store"})
        if path == "/api/auth/readiness":
            return _Response(self.session_status, self.session_payload,
                             {"cache-control": self.cache})
        if path == "/api/proxy/api/cases":
            return _Response(401, {"detail": "Officer session required."})
        if path == "/api/auth/oidc/start":
            return _Response(303, headers={
                "location": "http://127.0.0.1:8371/authorize?state=s&code_challenge=x&code_challenge_method=S256",
                "set-cookie": "kw_oidc_transaction=synthetic; HttpOnly; Max-Age=300",
            })
        raise AssertionError(f"unexpected request path: {path}")


@pytest.mark.parametrize(
    ("status", "payload", "cache", "accepted"),
    [
        (200, {"ready": True, "mode": "protected"}, "no-store", True),
        (503, {"ready": False, "mode": "protected"}, "no-store", False),
        (200, {"ready": True, "mode": "demo"}, "no-store", False),
        (200, {"ready": True, "mode": "protected"}, "public, max-age=30", False),
    ],
)
def test_session_dependency_controls_real_preflight(monkeypatch, status, payload, cache, accepted):
    monkeypatch.setattr(preflight.httpx, "Client", lambda **_: _Client(status, payload, cache))
    report = preflight.run_check("http://127.0.0.1:8013",
                                 "http://127.0.0.1:3003", synthetic=True)
    assert report["checks"]["browser_durable_session_store_reachable"] is accepted
    assert report["passed"] is accepted
    assert report["real_cloud_certified"] is False
    assert report["status"] == "synthetic_transport_check_only"
