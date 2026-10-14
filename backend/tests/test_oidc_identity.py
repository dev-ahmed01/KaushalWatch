"""JWT/OIDC identity boundary regression tests with ephemeral RSA signing keys.

No real identity provider, network account, or production key is accessed.
Tests assert the cryptographic signature and the separately provisioned
centre grants; token roles/emails are never used to authorize requests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as main
from app.models import ComplianceCase
from app.services.case_store import CaseStore
from app.services import oidc_identity as ident

ISSUER = "https://login.example.org/organizations/kaushalwatch"
JWKS = "https://login.example.org/.well-known/jwks.json"
AUDIENCE = "api://kaushalwatch"
SUBJECT = "officer-subject-001"
VIEWER = "officer-subject-002"


@pytest.fixture
def oidc(monkeypatch, tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update({"kid": "synthetic-rsa-1", "alg": "RS256", "use": "sig"})
    monkeypatch.setattr(ident, "_load_jwks", lambda url: {"keys": [public]})
    monkeypatch.setenv("KAUSHALWATCH_ENV", "staging")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "oidc")
    monkeypatch.setenv("KAUSHALWATCH_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("KAUSHALWATCH_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("KAUSHALWATCH_OIDC_JWKS_URL", JWKS)
    monkeypatch.setenv("KAUSHALWATCH_OIDC_GRANTS_JSON", json.dumps({
        SUBJECT: {"actor": "oidc-network-admin", "role": "network_admin", "centres": []},
        VIEWER: {"actor": "oidc-centre-viewer", "role": "centre_viewer", "centres": ["DEMO-KA-104"]},
    }))
    store = CaseStore(tmp_path / "cases.json")
    for centre, case_id in (("DEMO-KA-104", "OIDC-IN-SCOPE"),
                            ("DEMO-KA-112", "OIDC-OUT-OF-SCOPE")):
        store.save(ComplianceCase(
            case_id=case_id, centre_id=centre, batch_id="TEST-BATCH",
            case_type="attendance_discrepancy", severity="medium",
            summary="OIDC synthetic audit fixture",
        ))
    monkeypatch.setattr(main, "STORE", store)
    return {"private": private, "public": public, "client": TestClient(main.app),
            "store": store}


def issue(oidc, *, subject=SUBJECT, overrides=None, algorithm="RS256", key=None):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "sub": subject, "iss": ISSUER, "aud": AUDIENCE,
        "iat": now - 2, "nbf": now - 2, "exp": now + 900,
        "token_use": "access", "role": "network_admin",
        "email": "untrusted-admin@example.org",
    }
    if overrides:
        claims.update(overrides)
    signing_key = key or oidc["private"]
    headers = {"kid": "synthetic-rsa-1", "typ": "at+jwt"}
    if algorithm == "HS256":
        signing_key = "not-a-real-oidc-signature-secret"
    return jwt.encode(claims, signing_key, algorithm=algorithm, headers=headers)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_verified_signed_jwt_allows_admin_and_server_side_officer_actor(oidc):
    client = oidc["client"]
    token = issue(oidc)
    assert client.get("/api/officer-validate", headers=auth(token)).json() == {"authenticated": True}
    status = client.get("/api/review-access")
    assert status.json() == {"mode": "oidc", "required": True, "prototype_only": False}
    context = client.get("/api/officer-context", headers=auth(token))
    assert context.status_code == 200
    assert context.json()["role"] == "network_admin"
    result = client.post("/api/cases/OIDC-IN-SCOPE/review",
                         headers=auth(token), json={"action": "under_review", "actor": "spoof"})
    assert result.status_code == 200
    assert result.json()["review_history"][-1]["actor"] == "oidc-network-admin"
    assert token not in result.text


def test_idp_claimed_admin_role_cannot_escape_local_viewer_centre(oidc):
    client = oidc["client"]
    token = issue(oidc, subject=VIEWER, overrides={"role": "network_admin", "groups": ["admin"]})
    cases = client.get("/api/cases", headers=auth(token))
    assert cases.status_code == 200
    assert [c["case_id"] for c in cases.json()] == ["OIDC-IN-SCOPE"]
    assert client.get("/api/cases/OIDC-OUT-OF-SCOPE/evidence-pack",
                      headers=auth(token)).status_code == 404
    assert client.post("/api/cases/OIDC-IN-SCOPE/review",
                       headers=auth(token), json={"action": "under_review"}).status_code == 403
    # Deterministic assistant is scoped to the requested centre; global
    # unrestricted AI chat is denied to centre officers.
    assert client.post("/api/assistant/query", headers=auth(token),
                       json={"centre_id": "DEMO-KA-112", "question": "cases"}).status_code == 404
    assert client.post("/api/assistant/chat", headers=auth(token),
                       json={"message": "network reports"}).status_code == 403


def test_signed_unprovisioned_identity_is_not_an_authorized_officer(oidc):
    response = oidc["client"].get("/api/cases", headers=auth(issue(oidc, subject="other-valid-sub")))
    assert response.status_code == 403
    assert oidc["store"].get("OIDC-IN-SCOPE").review_history == []


@pytest.mark.parametrize("overrides", [
    {"aud": "api://unrelated"}, {"iss": "https://attacker.example.com"},
    {"exp": 100}, {"nbf": 4_000_000_000}, {"iat": 10},
    {"exp": 4_000_000_000}, {"token_use": "id"},
    {"typ": "id"}, {"sub": "a"}, {"sub": ""},
])
def test_invalid_claims_rejected_even_when_signed(oidc, overrides):
    response = oidc["client"].get("/api/cases",
                                  headers=auth(issue(oidc, overrides=overrides)))
    assert response.status_code == 401, (overrides, response.text)


def test_signed_by_different_rsa_key_is_rejected(oidc):
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = oidc["client"].get("/api/cases", headers=auth(issue(oidc, key=attacker)))
    assert response.status_code == 401


def test_hs256_algorithm_confusion_is_rejected(oidc):
    response = oidc["client"].get("/api/cases",
                                  headers=auth(issue(oidc, algorithm="HS256")))
    assert response.status_code == 401


def test_duplicate_jwks_key_ids_refused(oidc, monkeypatch):
    key = oidc["public"]
    monkeypatch.setattr(ident, "_load_jwks", lambda _: {"keys": [key, dict(key)]})
    response = oidc["client"].get("/api/cases", headers=auth(issue(oidc)))
    assert response.status_code == 401


@pytest.mark.parametrize("malicious", [
    "http://login.example.org/.well-known/jwks.json",
    "https://untrusted.example.org/.well-known/jwks.json",
    "https://login.example.org/.well-known/jwks.json?redirect=evil",
    "https://example.org@evil.example.com/.well-known/jwks.json",
])
def test_untrusted_jwks_location_fails_closed(oidc, monkeypatch, malicious):
    monkeypatch.setenv("KAUSHALWATCH_OIDC_JWKS_URL", malicious)
    response = oidc["client"].get("/api/cases", headers=auth(issue(oidc)))
    assert response.status_code == 503


def test_revoking_a_subject_in_server_registry_works_on_next_request(oidc, monkeypatch):
    token = issue(oidc)
    assert oidc["client"].get("/api/cases", headers=auth(token)).status_code == 200
    monkeypatch.setenv("KAUSHALWATCH_OIDC_GRANTS_JSON", json.dumps({
        VIEWER: {"actor": "oidc-centre-viewer", "role": "centre_viewer",
                 "centres": ["DEMO-KA-104"]},
    }))
    assert oidc["client"].get("/api/cases", headers=auth(token)).status_code == 403


@pytest.mark.parametrize("mapping", [
    '{"officer-subject-001":{"actor":"x","role":"network_admin","centres":[]}}',
    '{"officer-subject-001":{"actor":"valid-officer","role":"network_admin","centres":["DEMO-KA-104"]}}',
    '{"officer-subject-001":{"actor":"valid-officer","role":"centre_viewer","centres":[]}}',
    '{"officer-subject-001":{"actor":"valid-officer","role":"system_admin","centres":[]}}',
    '{"officer-subject-001":{"actor":"valid-officer","role":"centre_viewer","centres":["INVALID-CENTRE"]}}',
    '{}', 'not-json',
])
def test_invalid_provisioning_fails_closed(oidc, monkeypatch, mapping):
    monkeypatch.setenv("KAUSHALWATCH_OIDC_GRANTS_JSON", mapping)
    assert oidc["client"].get("/api/cases", headers=auth(issue(oidc))).status_code == 503


@pytest.mark.parametrize("environment", ["production", "pilot", "prod"])
def test_production_does_not_accept_static_keys(oidc, monkeypatch, environment):
    monkeypatch.setenv("KAUSHALWATCH_ENV", environment)
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "token")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",
                       json.dumps({"test-officer": "SyntheticStaticLongSecret0123456789AbcDeF"}))
    assert oidc["client"].get("/api/review-access").status_code == 503
    # A production API with no DB/S3 cannot pass its separate infrastructure gate.
    # Its identity configuration independently fails closed.


def test_missing_authorization_header_is_unauthorized(oidc):
    response = oidc["client"].get("/api/cases")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
