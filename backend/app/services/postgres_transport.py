"""Require host-verified PostgreSQL TLS on protected pilot connections.

This is a pre-connection configuration gate, not independent certificate/cloud
attestation. The actual libpq connection still performs certificate and hostname
verification. Never include the raw DSN in an error, receipt or log.
"""
from __future__ import annotations

from psycopg.conninfo import conninfo_to_dict


PROTECTED_ENVS = frozenset({"pilot", "production", "prod"})


def requires_verified_postgres_tls(env: dict[str, str]) -> bool:
    mode = env.get("KAUSHALWATCH_ENV", "").strip().lower()
    return mode in PROTECTED_ENVS or (
        mode == "staging"
        and env.get("KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT") == "true"
    )


def postgres_tls_configured(dsn: str) -> bool:
    """Reject plaintext/fallback modes and implicit host/service resolution.

    verify-full verifies the server certificate and expected hostname.
    Explicit gssencmode=disable prevents GSS encryption from silently
    taking precedence over the requested TLS transport.
    """
    if not isinstance(dsn, str) or not dsn.startswith(
        ("postgresql://", "postgres://")
    ):
        return False
    try:
        options = conninfo_to_dict(dsn)
        host = options.get("host", "")
        return (
            options.get("sslmode") == "verify-full"
            and options.get("gssencmode") == "disable"
            and isinstance(host, str)
            and bool(host)
            and not host.startswith("/")
            and "," not in host
            and not options.get("service")
            and not options.get("servicefile")
        )
    except Exception:
        # psycopg may raise a ProgrammingError for malformed/unsupported
        # connection options. Invalid configuration always fails closed.
        return False


def require_postgres_transport(dsn: str, env: dict[str, str]) -> None:
    if requires_verified_postgres_tls(env) and not postgres_tls_configured(dsn):
        raise RuntimeError(
            "Protected PostgreSQL requires explicit verified TLS transport"
        )
