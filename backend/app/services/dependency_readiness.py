"""Public, non-diagnostic orchestration readiness.

Liveness (/api/health) remains separate. Do not emit database host, bucket,
KMS key, exception messages or private connectivity details in the response.
"""
from __future__ import annotations

import os

from app.services.review_access import LOCAL_ENVS
from app.services.postgres_transport import require_postgres_transport

# Production readiness must cover the *same* schema contract as the
# explicit migration checker, including the Camera Trust shadow workflow.
# A v2 database cannot serve a v3 API merely because its legacy tables exist.
REQUIRED_MIGRATIONS = frozenset({1, 2, 3})
REQUIRED_TABLES = (
    "kw_cases", "kw_analysis_history", "kw_centre_settings",
    "kw_edge_events", "kw_evidence_objects", "kw_camera_registry",
    "kw_camera_jobs", "kw_camera_observations", "kw_camera_audit",
    "kw_camera_references",
)


def dependencies_ready() -> bool:
    env = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    if env in LOCAL_ENVS:
        return True
    # Synthetic staging without PostgreSQL has only process-level readiness.
    # If staging explicitly selects PostgreSQL+S3, verify those dependencies.
    # Production and pilot always require every protected dependency.
    if (env == "staging" and
            os.getenv("KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT") != "true" and
            os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json") != "postgres"):
        return True
    if os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json") != "postgres":
        return False
    if os.getenv("KAUSHALWATCH_EVIDENCE_BACKEND", "local") != "s3":
        return False
    try:
        # Ensure /api/ready cannot report green with a plaintext PostgreSQL
        # DSN even if another dependency is stubbed or has a live connection.
        require_postgres_transport(os.getenv("KAUSHALWATCH_DATABASE_URL", ""),
                                   dict(os.environ))
        from app.services.officer_permissions import configured_principals
        from app.services.object_evidence import configuration
        from app.services.postgres_store import connection
        configured_principals()
        if os.getenv("KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT") == "true" or env in {
            "pilot", "production", "prod"
        }:
            from app.services.review_access import _configuration
            if _configuration()[0] != "oidc":
                return False
        configuration()  # Configuration check; real IAM requires cloud validation.
        with connection() as db:
            versions = db.execute(
                "SELECT version FROM kw_schema_migrations ORDER BY version"
            ).fetchall()
            if not REQUIRED_MIGRATIONS.issubset({row["version"] for row in versions}):
                return False
            for table in REQUIRED_TABLES:
                if db.execute("SELECT to_regclass(%s) AS name", (table,)).fetchone()["name"] is None:
                    return False
    except Exception:
        return False
    return True
