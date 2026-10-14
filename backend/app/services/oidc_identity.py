"""OIDC access-token validation for production officer API requests.

Only RS256 JWT *access tokens* for a pinned issuer/audience and an explicitly
provisioned subject are accepted. Claims never confer permissions: the local
server grant registry is the authority. This is an API trust boundary, not a
browser PKCE login implementation or an IdP provisioning service.
"""
from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import urlsplit

from fastapi import HTTPException
import httpx
import jwt

INVALID = "An active verified officer identity is required."
SUB_PATTERN = re.compile(r"^[A-Za-z0-9._@|:-]{3,256}$")


def unavailable() -> HTTPException:
    return HTTPException(503, "Production officer identity is not securely configured.")


def unauthorized() -> HTTPException:
    return HTTPException(401, INVALID, headers={"WWW-Authenticate": "Bearer"})


def identity_settings() -> tuple[str, str, str]:
    issuer = os.getenv("KAUSHALWATCH_OIDC_ISSUER", "").strip()
    audience = os.getenv("KAUSHALWATCH_OIDC_AUDIENCE", "").strip()
    jwks = os.getenv("KAUSHALWATCH_OIDC_JWKS_URL", "").strip()
    try:
        origin = urlsplit(issuer)
        keys = urlsplit(jwks)
        # Require HTTPS, the same trusted host and ports for JWKS, and no
        # credentials, fragments, query strings, or wildcard audiences.
        if (origin.scheme != "https" or keys.scheme != "https"
            or not origin.hostname or origin.hostname != keys.hostname
            or origin.port != keys.port or origin.username or keys.username
            or origin.password or keys.password
            or origin.query or origin.fragment or keys.query or keys.fragment
            or not keys.path.startswith("/") or not audience
            or len(audience) > 256 or any(x.isspace() for x in audience)
            or not issuer.startswith("https://") or not jwks.startswith("https://")):
            raise ValueError("Bad identity configuration")
    except (TypeError, ValueError):
        raise unavailable() from None
    return issuer, audience, jwks


def _load_jwks(uri: str) -> dict:
    """Never follow redirects; only fetch a fully configured HTTPS JWKS URL."""
    try:
        with httpx.Client(follow_redirects=False, timeout=4.0, trust_env=False) as client:
            response = client.get(uri, headers={"Accept": "application/json"})
            if response.status_code != 200 or len(response.content) > 128_000:
                raise ValueError("JWKS request was not a bounded successful response")
            data = response.json()
    except (httpx.HTTPError, ValueError):
        raise unavailable() from None
    if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
        raise unavailable()
    if len(data["keys"]) > 30:
        raise unavailable()
    return data


def verified_subject(token: str) -> str:
    if (not isinstance(token, str) or len(token) > 8192 or len(token) < 50
        or not token.isascii() or any(x.isspace() for x in token)):
        raise unauthorized()
    issuer, audience, jwks_url = identity_settings()
    try:
        header = jwt.get_unverified_header(token)
        if (header.get("alg") != "RS256" or header.get("typ", "JWT") not in {"JWT", "at+jwt"}
            or not isinstance(header.get("kid"), str)
            or not 1 <= len(header["kid"]) <= 128):
            raise ValueError("Unsupported JWT header")
    except (jwt.PyJWTError, ValueError, TypeError):
        raise unauthorized() from None
    document = _load_jwks(jwks_url)
    matches = [
        entry for entry in document["keys"]
        if isinstance(entry, dict) and entry.get("kid") == header["kid"]
        and entry.get("kty") == "RSA"
        and entry.get("use", "sig") == "sig"
        and entry.get("alg", "RS256") == "RS256"
    ]
    if len(matches) != 1:
        raise unauthorized()
    try:
        public = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matches[0]))
        claims = jwt.decode(
            token, key=public, algorithms=["RS256"],
            issuer=issuer, audience=audience,
            options={"require": ["sub", "iss", "aud", "exp", "iat", "nbf"], "leeway": 0},
            leeway=30,
        )
        subject = claims.get("sub")
        issued = claims.get("iat")
        expiration = claims.get("exp")
        if (not isinstance(subject, str) or not SUB_PATTERN.fullmatch(subject)
            or type(issued) not in {int, float} or type(expiration) not in {int, float}
            or expiration - issued > 3600 or expiration <= issued
            or claims.get("token_use", "access") != "access"
            or claims.get("typ", "access") != "access"):
            raise ValueError("Invalid access-token claims")
        return subject
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise unauthorized() from None
