"""Synthetic loopback OIDC authorization server for CI browser tests ONLY.

One-use authorization codes are bound to S256 PKCE, redirect URI and client ID.
Generates an ephemeral RSA key per boot. No accounts, live provider, or secrets.
Never log bearer tokens, authorization codes, or query strings.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

HOST = "127.0.0.1"
PORT = 8371
ISSUER = f"http://{HOST}:{PORT}/issuer"
AUD = "api://kaushalwatch"
CLIENT = "kaushalwatch-ci-client"
REDIRECT = "http://127.0.0.1:3003/api/auth/oidc/callback"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
PUBLIC.update({"kid": "ci-ephemeral-oidc-key", "kty": "RSA", "alg": "RS256", "use": "sig"})
CODES: dict[str, dict] = {}
LOCK = threading.Lock()


def single(q: dict, field: str) -> str:
    values = q.get(field, [])
    return values[0] if len(values) == 1 else ""


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _respond(self, status: int, payload: dict):
        data = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/jwks":
            return self._respond(200, {"keys": [PUBLIC]})
        if url.path == "/health":
            return self._respond(200, {"synthetic": True})
        if url.path != "/authorize":
            return self._respond(404, {"error": "not_found"})
        q = parse_qs(url.query, keep_blank_values=True)
        if (single(q, "client_id") != CLIENT or single(q, "redirect_uri") != REDIRECT
            or single(q, "response_type") != "code" or single(q, "scope") != "openid"
            or single(q, "code_challenge_method") != "S256"):
            return self._respond(400, {"error": "invalid_authorize_request"})
        challenge = single(q, "code_challenge")
        state = single(q, "state")
        if (len(state) != 43 or len(challenge) != 43
            or not state.isascii() or not challenge.isascii()):
            return self._respond(400, {"error": "invalid_state_or_pkce"})
        subject = single(q, "synthetic_subject") or "ci-admin-subject"
        audience = single(q, "synthetic_audience") or AUD
        if subject not in {"ci-admin-subject", "ci-viewer-subject", "ci-unprovisioned-subject"}:
            return self._respond(400, {"error": "invalid_synthetic_subject"})
        if audience not in {AUD, "api://wrong-audience"}:
            return self._respond(400, {"error": "invalid_synthetic_audience"})
        code = secrets.token_urlsafe(32)
        with LOCK:
            CODES[code] = {
                "state": state, "challenge": challenge, "subject": subject,
                "audience": audience, "issued": time.monotonic(),
            }
        target = REDIRECT + "?" + urlencode({"state": state, "code": code})
        self.send_response(303)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_POST(self):
        if urlsplit(self.path).path != "/token":
            return self._respond(404, {"error": "not_found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8000:
                raise ValueError("Invalid form length")
            q = parse_qs(self.rfile.read(size).decode("ascii"), keep_blank_values=True)
        except (ValueError, UnicodeDecodeError):
            return self._respond(400, {"error": "invalid_request"})
        if (single(q, "grant_type") != "authorization_code"
            or single(q, "client_id") != CLIENT
            or single(q, "redirect_uri") != REDIRECT):
            return self._respond(400, {"error": "invalid_grant"})
        code = single(q, "code")
        verifier = single(q, "code_verifier")
        if len(verifier) != 43:
            return self._respond(400, {"error": "invalid_grant"})
        # Remove first: repeated/parallel exchanges cannot mint a second token.
        with LOCK:
            pending = CODES.pop(code, None)
        if pending is None or time.monotonic() - pending["issued"] > 300:
            return self._respond(400, {"error": "invalid_grant"})
        digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        if not secrets.compare_digest(digest, pending["challenge"]):
            return self._respond(400, {"error": "invalid_grant"})
        now = int(time.time())
        claims = {
            "iss": ISSUER, "aud": pending["audience"],
            "sub": pending["subject"], "iat": now, "nbf": now,
            "exp": now + 900, "token_use": "access",
            # Must NOT grant administrative access on its own:
            "role": "network_admin", "groups": ["admin"],
        }
        access = jwt.encode(
            claims, KEY, algorithm="RS256",
            headers={"kid": PUBLIC["kid"], "typ": "at+jwt"},
        )
        self._respond(200, {
            "access_token": access, "token_type": "Bearer", "expires_in": 900,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    if args.host != HOST or args.port != PORT:
        parser.error("Synthetic OIDC provider is intentionally fixed to CI loopback")
    server = ThreadingHTTPServer((args.host, args.port), Provider)
    server.serve_forever()


if __name__ == "__main__":
    main()
