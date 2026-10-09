"""Fail-closed protected-environment API/evidence boundary.

A local SIH demo stays open only in development. Protected deployments require
a configured officer bearer key for all sensitive reads and writes. Edge tokens
are scoped ONLY to /api/edge/sync. This is a deliberate deployment safety gate,
not a web-session/login replacement, centre-level RBAC or production readiness.
"""
from __future__ import annotations

import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.review_access import LOCAL_ENVS, resolve_review_actor

PUBLIC_PATHS = frozenset({"/api/health", "/api/review-access"})
EDGE_ONLY_PATHS = frozenset({"/api/edge/sync"})


def is_sensitive_path(path: str) -> bool:
    return (
        path == "/api" or path.startswith("/api/")
        or path == "/evidence" or path.startswith("/evidence/")
        or path == "/docs" or path.startswith("/docs/")
        or path in {"/openapi.json", "/redoc", "/redoc/"}
    )


async def protected_read_boundary(request: Request, call_next):
    """Authorize before hitting any API handler or static evidence mount."""
    env = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    path = request.scope.get("path", "")
    if env in LOCAL_ENVS or request.method == "OPTIONS" or not is_sensitive_path(path):
        return await call_next(request)
    if path in PUBLIC_PATHS or path in EDGE_ONLY_PATHS:
        # Edge ingestion authenticates its own device identity downstream;
        # the officer bearer MUST NOT be accepted as a device token.
        return await call_next(request)
    try:
        actor = resolve_review_actor(request)
    except HTTPException as exc:
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    request.state.protected_officer_actor = actor
    response = await call_next(request)
    # Sensitive read material (including evidence and report PDFs) must not
    # be cached in a shared browser/proxy after logout or key rotation.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return response
