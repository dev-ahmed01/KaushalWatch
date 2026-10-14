"""Regression tests for the SIH route contract gate."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.check_frontend_api_contracts import (
    BACKEND_FILE,
    FRONTEND_FILE,
    backend_contracts,
    contract_errors,
    frontend_contracts,
)


def _sources() -> tuple[str, str]:
    return (
        BACKEND_FILE.read_text(encoding="utf-8"),
        FRONTEND_FILE.read_text(encoding="utf-8"),
    )


def test_release_api_route_contracts_are_present() -> None:
    backend, frontend = _sources()
    assert contract_errors(backend, frontend) == []


def test_contract_check_rejects_frontend_method_drift() -> None:
    backend, frontend = _sources()
    assert "method: 'PUT'" in frontend
    broken = frontend.replace("method: 'PUT'", "method: 'POST'", 1)
    assert any("saveSettings" in item for item in contract_errors(backend, broken))


def test_contract_check_rejects_missing_backend_route() -> None:
    backend, frontend = _sources()
    assert '@app.post("/api/cases/{case_id}/review")' in backend
    broken = backend.replace(
        '@app.post("/api/cases/{case_id}/review")',
        '@app.post("/api/cases/{case_id}/review-v2")',
        1,
    )
    assert "backend missing POST /api/cases/{case_id}/review" in contract_errors(
        broken, frontend
    )


def test_contract_check_distinguishes_read_write_paths() -> None:
    backend, frontend = _sources()
    assert ("GET", "/api/centres/{centre_id}/settings") in backend_contracts(backend)
    assert ("PUT", "/api/centres/{centre_id}/settings") in backend_contracts(backend)
    assert frontend_contracts(frontend)["getSettings"] == (
        "GET", "/api/centres/{centre_id}/settings"
    )
    assert frontend_contracts(frontend)["saveSettings"] == (
        "PUT", "/api/centres/{centre_id}/settings"
    )
