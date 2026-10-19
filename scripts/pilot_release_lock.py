"""Nonsecret pilot release evidence and immutable image-reference format gate.

CI local Docker image IDs are NOT registry manifests or deployable digests.
An operator-supplied registry reference is only syntax-checked here; actual
registry provenance, deployed revision and independent sign-off remain external.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any

CI_SCHEMA = "KW_CI_IMAGE_BUILD_V1"
LOCK_SCHEMA = "KW_PILOT_RELEASE_LOCK_V1"
BLOCKED = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
LOCAL_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
# Format-only: a lowercase registry/repository plus an immutable manifest digest.
REGISTRY_REPO = re.compile(r"[a-z0-9]+(?:[a-z0-9._:/-]*[a-z0-9])?\Z")
MAX_BYTES = 16 * 1024


def _pairs_unique(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def load_lock(path: Path) -> dict:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("Invalid release lock file")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs_unique)
    if not isinstance(value, dict):
        raise ValueError("Release lock must be an object")
    return value


def _pinned(ref: Any) -> bool:
    if not isinstance(ref, str) or len(ref) > 512 or ref.count("@sha256:") != 1:
        return False
    repo, digest = ref.split("@sha256:")
    if not SHA256.fullmatch(digest) or not REGISTRY_REPO.fullmatch(repo):
        return False
    if "//" in repo or "/./" in repo or "/../" in repo or ".." in repo:
        return False
    if "@" in repo or not repo:
        return False
    return True


def valid_lock(value: Any, expected_commit: str) -> bool:
    """Validate only operator reference format/ordering, not deployment authenticity."""
    if not isinstance(expected_commit, str) or not SHA40.fullmatch(expected_commit):
        return False
    if not isinstance(value, dict) or set(value) != {
        "schema", "source_commit", "images", "database", "rollback"
    }:
        return False
    if value["schema"] != LOCK_SCHEMA or value["source_commit"] != expected_commit:
        return False
    images = value["images"]
    if not isinstance(images, dict) or set(images) != {"api", "web"}:
        return False
    if not all(_pinned(images[k]) for k in ("api", "web")):
        return False
    if images["api"] == images["web"]:
        return False
    if value["database"] != {
        "required_migrations": [1, 2, 3],
        "apply": "separate_approved_migration_only_role",
        "verify": "scripts/migrate_postgres.py --check",
    }:
        return False
    if value["rollback"] != {
        "on_failed_readiness": "halt_traffic_and_request_operator_review",
        "database_rollback": "manual_restore_from_verified_isolated_backup_only",
    }:
        return False
    return True


def ci_evidence(source_commit: str, api_id: str, web_id: str) -> dict:
    if not isinstance(source_commit, str) or not SHA40.fullmatch(source_commit):
        raise ValueError("Invalid checkout revision")
    if not all(isinstance(x, str) and LOCAL_IMAGE_ID.fullmatch(x)
               for x in (api_id, web_id)):
        raise ValueError("Invalid local Docker image ID")
    if api_id == web_id:
        raise ValueError("API and browser must be distinct images")
    return {
        "schema": CI_SCHEMA, "source_commit": source_commit,
        "images": {"api": {"local_image_id": api_id},
                   "web": {"local_image_id": web_id}},
        "registry_digest_independently_verified": False,
        "remote_registry_publication": "NOT_PERFORMED",
        "real_site_deployment_independently_verified": False,
        "pilot_activation": BLOCKED,
        "autonomous_enforcement_authorized": False,
    }


def write_exclusive(path: Path, value: dict) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def check_receipt(valid: bool) -> dict:
    return {
        "schema": LOCK_SCHEMA,
        "immutable_reference_format": "PASS" if valid else "BLOCKED",
        "registry_content_or_signature_verified": False,
        "running_deployment_digest_verified": False,
        "rollback_image_schema_compatibility_verified": False,
        "external_operator_approval_recorded": False,
        "pilot_activation": BLOCKED,
        "autonomous_enforcement_authorized": False,
        "secrets_or_source_identifiers_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-deploying immutable release evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    ci = sub.add_parser("ci", help="Record local CI image IDs (never registry digests)")
    ci.add_argument("--source-commit", required=True)
    ci.add_argument("--api-image-id", required=True)
    ci.add_argument("--web-image-id", required=True)
    ci.add_argument("--output", required=True, type=Path)
    check = sub.add_parser("check", help="Validate operator release-lock syntax only")
    check.add_argument("--manifest", required=True, type=Path)
    check.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        if args.command == "ci":
            data = ci_evidence(args.source_commit, args.api_image_id, args.web_image_id)
            write_exclusive(args.output, data)
            print(json.dumps({"schema": CI_SCHEMA, "local_build_recorded": True,
                "registry_digest_independently_verified": False,
                "pilot_activation": BLOCKED}))
            return 0
        valid = valid_lock(load_lock(args.manifest), args.expected_commit)
    except (OSError, ValueError, TypeError, UnicodeError):
        valid = False
    print(json.dumps(check_receipt(valid), sort_keys=True))
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
