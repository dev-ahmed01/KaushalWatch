"""Fail-closed protected API boundary and route-level officer authorisation.

Authenticates all sensitive requests; scoped readers are denied unknown routes
until an explicit policy is added. Endpoint-level filters then trim collection
results and validate form / JSON centre IDs before processing.
"""
from __future__ import annotations

import os
import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.review_access import LOCAL_ENVS, resolve_review_actor
from app.services.officer_permissions import (
    configured_principals, evidence_centre, require_centre, require_write,
)

PUBLIC_PATHS = frozenset({"/api/health", "/api/review-access"})
EDGE_ONLY_PATHS = frozenset({"/api/edge/sync"})
SCOPED_READS = frozenset({
    "/api/centres", "/api/cases", "/api/actions", "/api/insights",
    "/api/kaushalai/brief", "/api/analysis-history", "/api/dashboard",
    "/api/runtime-readiness", "/api/vision/governance", "/api/practical-work-zones",
    "/api/assistant/status", "/api/officer-validate", "/api/officer-context",
})
SCOPED_WRITES = frozenset({
    "/api/process-video", "/api/process-practical-activity",
    "/api/process-infrastructure-video",
})
SCOPED_ASSISTANT = frozenset({
    "/api/assistant/query", "/api/assistant/transcribe", "/api/assistant/speech",
})
EVIDENCE_PATH = re.compile(r"^/evidence/([A-Za-z0-9_-]{1,100})\.jpg$")


def is_sensitive_path(path: str) -> bool:
    return (
        path == "/api" or path.startswith("/api/")
        or path == "/evidence" or path.startswith("/evidence/")
        or path == "/docs" or path.startswith("/docs/")
        or path in {"/openapi.json", "/redoc", "/redoc/"}
    )


def _scoped_route_policy(request: Request) -> None:
    principal = request.state.officer_principal
    path = request.scope.get("path", "")
    method = request.method
    if path.startswith("/evidence/"):
        match = EVIDENCE_PATH.fullmatch(path)
        if not match:
            raise HTTPException(status_code=404, detail="Evidence not found")
        centre_id = evidence_centre(match.group(1))
        if not centre_id:
            raise HTTPException(status_code=404, detail="Evidence not found")
        require_centre(request, centre_id)
        return

    # A network administrator is the only officer allowed to access global
    # endpoints not explicitly enumerated for centre-scoped identities.
    if principal.is_admin:
        return

    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[:2] == ["api", "centres"]:
        require_centre(request, parts[2], write=method != "GET")
        return
    if len(parts) >= 3 and parts[:2] == ["api", "cases"]:
        import app.main as main
        case = main.STORE.get(parts[2])
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        require_centre(request, case.centre_id, write=method != "GET")
        return

    if method == "GET" and path in SCOPED_READS:
        return
    if method == "POST" and path in SCOPED_WRITES:
        require_write(request)
        return
    if method == "POST" and path in SCOPED_ASSISTANT:
        # Chat has a global toolset and can return network data; it remains
        # network-admin-only until all tool calls enforce caller scope.
        return
    raise HTTPException(status_code=403, detail="Route requires network administrator")


async def protected_read_boundary(request: Request, call_next):
    env = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    path = request.scope.get("path", "")
    if env in LOCAL_ENVS or request.method == "OPTIONS" or not is_sensitive_path(path):
        return await call_next(request)
    if path in PUBLIC_PATHS or path in EDGE_ONLY_PATHS:
        return await call_next(request)
    try:
        actor = resolve_review_actor(request)
        principal = configured_principals()[actor]
        request.state.protected_officer_actor = actor
        request.state.officer_principal = principal
        _scoped_route_policy(request)
    except (HTTPException, KeyError) as exc:
        if isinstance(exc, KeyError):
            exc = HTTPException(status_code=503, detail="Officer permissions are unavailable")
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )
        response.headers["Cache-Control"] = (
            "private, no-store" if exc.status_code in {403, 404} else "no-store"
        )
        return response
    response = await call_next(request)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return response
