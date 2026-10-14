"""Public, non-diagnostic orchestration readiness.

Liveness (/api/health) remains separate. Do not emit database host, bucket,
KMS key, exception messages or private connectivity details in the response.
"""
from __future__ import annotations

import os

from app.services.review_access import LOCAL_ENVS

REQUIRED_TABLES = (
    "kw_cases", "kw_analysis_history", "kw_centre_settings",
    "kw_edge_events", "kw_evidence_objects",
)


def dependencies_ready() -> bool:
    env = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    if env in LOCAL_ENVS:
        return True
    # The staging JSON configuration used by the synthetic browser suite is
    # not eligible to represent a real pilot. Production is always strict.
    if env not in {"pilot", "production", "prod"}:
        return True
    if os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json") != "postgres":
        return False
    if os.getenv("KAUSHALWATCH_EVIDENCE_BACKEND", "local") != "s3":
        return False
    try:
        from app.services.officer_permissions import configured_principals
        from app.services.object_evidence import configuration
        from app.services.postgres_store import connection
        configured_principals()
        configuration()  # Configuration check; real IAM requires cloud validation.
        with connection() as db:
            versions = db.execute(
                "SELECT version FROM kw_schema_migrations ORDER BY version"
            ).fetchall()
            if not {1, 2}.issubset({row["version"] for row in versions}):
                return False
            for table in REQUIRED_TABLES:
                if db.execute("SELECT to_regclass(%s) AS name", (table,)).fetchone()["name"] is None:
                    return False
    except Exception:
        return False
    return True
