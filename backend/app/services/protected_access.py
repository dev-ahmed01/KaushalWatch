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

PUBLIC_PATHS = frozenset({"/api/health", "/api/ready", "/api/review-access"})
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
    # Deterministic query is centre-scoped within the endpoint itself.
    "/api/assistant/query",
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
        # Only the deterministic centre-scoped query is accessible to
        # centre officers. Global chat and voice remain admin-only.
        return
    raise HTTPException(status_code=403, detail="Route requires network administrator")


async def protected_read_boundary(request: Request, call_next):
    env = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    path = request.scope.get("path", "")
    strict_staging = (
        env == "staging"
        and os.getenv("KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT") == "true"
    )
    if ((env in {"production", "prod", "pilot"} or strict_staging)
            and (
                os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json").strip().lower() != "postgres"
                or os.getenv("KAUSHALWATCH_EVIDENCE_BACKEND", "local").strip().lower() != "s3"
            )
            and request.method != "OPTIONS" and is_sensitive_path(path)
            and path not in {"/api/health", "/api/ready"}):
        return JSONResponse(
            status_code=503,
            content={"detail": "Protected pilot requires PostgreSQL and private evidence storage."},
            headers={"Cache-Control": "no-store"},
        )
    if ((env in {"production", "prod", "pilot"} or strict_staging)
            and request.method != "OPTIONS"
            and is_sensitive_path(path) and path not in {"/api/health", "/api/ready"}):
        try:
            from app.services.object_evidence import configuration
            configuration()
        except RuntimeError:
            return JSONResponse(
                status_code=503,
                content={"detail": "Private evidence storage is not configured."},
                headers={"Cache-Control": "no-store"},
            )
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
