"""Prototype officer-review write authorization.

Mode "demo" preserves the deterministic local SIH walkthrough, but must not be
used on an externally exposed deployment. "token" binds each write to a
server-configured officer label and a distinct strong opaque bearer token.
This is NOT full authentication/RBAC for government or multi-tenant operation.
"""
from __future__ import annotations

import hmac
import json
import os
import re

from fastapi import HTTPException, Request

OFFICER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
PROTECTED_ENVS = {"production", "prod", "pilot", "staging"}


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Officer review access is not securely configured.",
    )


def _configuration() -> tuple[str, dict[str, str]]:
    mode = os.getenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "demo").strip().lower()
    environment = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    if mode == "demo":
        if environment in PROTECTED_ENVS:
            raise _unavailable()
        return mode, {}
    if mode != "token":
        raise _unavailable()

    raw = os.getenv("KAUSHALWATCH_REVIEW_TOKENS_JSON", "")
    try:
        tokens = json.loads(raw)
    except (TypeError, ValueError):
        raise _unavailable() from None
    if not isinstance(tokens, dict) or not tokens:
        raise _unavailable()

    seen: set[str] = set()
    for actor, token in tokens.items():
        if not isinstance(actor, str) or not OFFICER_ID.fullmatch(actor):
            raise _unavailable()
        if (not isinstance(token, str) or len(token) < 32
                or not token.isascii() or any(char.isspace() for char in token)):
            raise _unavailable()
        if token in seen:
            raise _unavailable()
        seen.add(token)
    return mode, tokens


def review_access_status() -> dict[str, str | bool]:
    mode, _ = _configuration()
    return {
        "mode": mode,
        "required": mode == "token",
        "prototype_only": True,
    }


def resolve_review_actor(request: Request) -> str:
    """Authorize review writes, deriving the audit actor only server-side."""
    mode, tokens = _configuration()
    if mode == "demo":
        return "prototype_officer"

    header = request.headers.get("authorization", "")
    scheme, delimiter, supplied = header.partition(" ")
    if (
        not delimiter
        or scheme.lower() != "bearer"
        or not supplied
        or supplied != supplied.strip()
        or len(supplied) > 1024
        or not supplied.isascii()
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid officer access key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Compare all configured tokens and never accept client-supplied actor IDs.
    matched_actor: str | None = None
    for actor, expected in tokens.items():
        if hmac.compare_digest(supplied, expected):
            matched_actor = actor
    if matched_actor is None:
        raise HTTPException(
            status_code=401,
            detail="A valid officer access key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return matched_actor
