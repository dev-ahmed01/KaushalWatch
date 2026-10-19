"""PostgreSQL must use verified TLS in every protected rollout path.

No external database is contacted. Errors/receipts never expose credentials.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from app.services.postgres_transport import (
    postgres_tls_configured, require_postgres_transport, requires_verified_postgres_tls,
)

SAFE = "postgresql://pilot:SECRET-DO-NOT-ECHO@db.example.invalid:5432/kw?sslmode=verify-full&gssencmode=disable"


@pytest.mark.parametrize("dsn", [
    SAFE,
    "postgres://pilot@db.example.invalid/kw?sslmode=verify-full&gssencmode=disable",
    "postgresql://db.example.invalid/kw?sslmode=verify-full&gssencmode=disable&sslrootcert=/private/ca.pem",
])
def test_verified_explicit_host_and_disabled_gss_is_accepted(dsn):
    assert postgres_tls_configured(dsn) is True


@pytest.mark.parametrize("dsn", [
    "postgresql://pilot:SECRET-DO-NOT-ECHO@db.example.invalid/kw",
    "postgresql://db.example.invalid/kw?sslmode=require&gssencmode=disable",
    "postgresql://db.example.invalid/kw?sslmode=verify-ca&gssencmode=disable",
    "postgresql://db.example.invalid/kw?sslmode=verify-full",
    "postgresql://db.example.invalid/kw?sslmode=prefer&gssencmode=disable",
    "postgresql:///kw?sslmode=verify-full&gssencmode=disable",
    "postgresql://db.example.invalid/kw?service=other&sslmode=verify-full&gssencmode=disable",
    "postgresql://db.example.invalid/kw?sslmode=disable&gssencmode=disable",
    "postgresql://db.example.invalid/kw?sslmode=verify-full&gssencmode=prefer",
    "postgresql://db.example.invalid/kw?sslmode=verify-full&gssencmode=disable&host=/tmp",
    "postgresql://db.example.invalid/kw?sslmode=verify-full&gssencmode=disable&host=one,two",
    "postgresql://db.example.invalid/kw?sslmode=verify-full&gssencmode=disable&servicefile=/tmp/config",
    "",
])
def test_unsafe_transport_fails_without_disclosing_dsn(dsn):
    assert postgres_tls_configured(dsn) is False
    with pytest.raises(RuntimeError) as e:
        require_postgres_transport(dsn, {"KAUSHALWATCH_ENV": "pilot"})
    assert "SECRET-DO-NOT-ECHO" not in str(e.value)


@pytest.mark.parametrize(("env", "expected"), [
    ({"KAUSHALWATCH_ENV": "pilot"}, True),
    ({"KAUSHALWATCH_ENV": "production"}, True),
    ({"KAUSHALWATCH_ENV": "prod"}, True),
    ({"KAUSHALWATCH_ENV": "staging", "KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT": "true"}, True),
    ({"KAUSHALWATCH_ENV": "staging"}, False),
    ({"KAUSHALWATCH_ENV": "development"}, False),
    ({"KAUSHALWATCH_ENV": "test"}, False),
])
def test_tls_policy_environment_boundary(env, expected):
    assert requires_verified_postgres_tls(env) is expected


def test_runtime_store_rejects_unsafe_transport_before_network(monkeypatch):
    import psycopg
    from app.services.postgres_store import connection
    attempts = []
    monkeypatch.setenv("KAUSHALWATCH_ENV", "pilot")
    monkeypatch.setenv("KAUSHALWATCH_DATABASE_URL",
                       "postgresql://pilot:SECRET-DO-NOT-ECHO@db.example.invalid/kw")
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: attempts.append(1))
    with pytest.raises(RuntimeError):
        with connection():
            pass
    assert attempts == []


def test_preflight_blocks_unverified_tls_without_attempting_connection(monkeypatch):
    import psycopg
    from scripts.check_camera_trust_deployment import check_environment
    attempts = []
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: attempts.append(1))
    result = check_environment("web", {
        "KAUSHALWATCH_ENV": "pilot",
        "KAUSHALWATCH_STORAGE_BACKEND": "postgres",
        "KAUSHALWATCH_DATABASE_URL":
            "postgresql://pilot:SECRET-DO-NOT-ECHO@db.example.invalid/kw",
    }, probe_db=True)
    assert result["checks"]["postgres_tls_hostname_validation"] == "BLOCKED"
    assert result["checks"]["postgres_camera_schema_v3"] == "BLOCKED"
    assert attempts == []
    assert "SECRET-DO-NOT-ECHO" not in str(result)


@pytest.mark.parametrize("mode", ["--check", "--apply"])
def test_migration_cli_blocks_plain_transport_before_attempting_network(mode):
    env = dict(os.environ, KAUSHALWATCH_ENV="pilot",
               KAUSHALWATCH_DATABASE_URL=
               "postgresql://pilot:SECRET-DO-NOT-ECHO@db.example.invalid/kw")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/migrate_postgres.py"), mode],
        capture_output=True, text=True, cwd=ROOT, timeout=15, env=env
    )
    assert result.returncode != 0
    assert "verified TLS" in result.stderr
    assert "SECRET-DO-NOT-ECHO" not in result.stdout + result.stderr
