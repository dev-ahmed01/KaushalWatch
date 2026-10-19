"""Explicit prototype edge-ingest write authorization.

Development permits demo mode for local SIH rehearsal only. Protected
environments reject demo mode and require separately configured opaque tokens.
Not mutual TLS, hardware identity, or government-level device attestation.
"""
from __future__ import annotations

import hmac
import json
import os
import re

from fastapi import HTTPException, Request
from app.services.review_access import LOCAL_ENVS

AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
PROTECTED_ENVS = {"production", "prod", "pilot", "staging"}


def _config() -> tuple[str, dict[str, str]]:
    env = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    mode = os.getenv("KAUSHALWATCH_EDGE_SYNC_AUTH_MODE", "demo").strip().lower()
    if mode == "demo":
        if env not in LOCAL_ENVS:
            raise HTTPException(503, "Edge sync must be configured with device tokens.")
        return "demo", {}
    if mode != "token":
        raise HTTPException(503, "Edge sync authentication mode is not configured.")
    try:
        tokens = json.loads(os.getenv("KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON", ""))
    except (TypeError, ValueError):
        raise HTTPException(503, "Edge sync device tokens are not securely configured.") from None
    if not isinstance(tokens, dict) or not tokens:
        raise HTTPException(503, "Edge sync device tokens are not securely configured.")
    used: set[str] = set()
    for agent, token in tokens.items():
        if not isinstance(agent, str) or not AGENT_ID.fullmatch(agent):
            raise HTTPException(503, "Edge sync device tokens are not securely configured.")
        if (not isinstance(token, str) or len(token) < 32 or not token.isascii()
                or any(character.isspace() for character in token) or token in used):
            raise HTTPException(503, "Edge sync device tokens are not securely configured.")
        used.add(token)
    return mode, tokens


def resolve_edge_actor(request: Request) -> str:
    mode, tokens = _config()
    if mode == "demo":
        return "local_demo_edge"
    header = request.headers.get("authorization", "")
    scheme, sep, supplied = header.partition(" ")
    if (not sep or scheme.lower() != "bearer" or len(supplied) > 1024
            or not supplied.isascii() or not supplied or supplied != supplied.strip()):
        raise HTTPException(401, "Valid edge sync token required.", headers={"WWW-Authenticate": "Bearer"})
    for actor, secret in tokens.items():
        if hmac.compare_digest(secret, supplied):
            return actor
    raise HTTPException(401, "Valid edge sync token required.", headers={"WWW-Authenticate": "Bearer"})


def edge_centre_scope(actor: str) -> set[str] | None:
    """Optional explicit edge-device -> centre allowlist.

    None means unconfigured (legacy demo / blocked institutional acceptance);
    an empty set means that actor has NO access. Never accept wildcards.
    """
    raw = os.getenv("KAUSHALWATCH_EDGE_SYNC_CENTRES_JSON", "").strip()
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(503, "Invalid edge centre allowlist.") from None
    if not isinstance(mapping, dict):
        raise HTTPException(503, "Invalid edge centre allowlist.")
    for name, centres in mapping.items():
        if (not isinstance(name, str) or not AGENT_ID.fullmatch(name)
            or not isinstance(centres, list) or not centres
            or len(centres) > 500 or len(set(str(c) for c in centres)) != len(centres)
            or any(not isinstance(c, str) or not c or len(c) > 128
                   or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", c)
                   for c in centres)):
            raise HTTPException(503, "Invalid edge centre allowlist.")
    return set(mapping.get(actor, []))
