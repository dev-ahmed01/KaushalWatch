"""Read-only AWS S3/KMS controls preflight for private evidence.

This is an opt-in operator probe. No list/get of evidence objects, uploads,
deletes, media, KMS encrypt/decrypt or state-changing API operations.
A PASS is a bounded configuration observation, never cloud certification
or permission to activate the camera pilot.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any

import boto3
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "KW_PRIVATE_EVIDENCE_CLOUD_PREFLIGHT_V1"
BLOCKED = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{2,62}\Z")
REGION = re.compile(r"[a-z0-9-]{3,32}\Z")
KEY = re.compile(r"[A-Za-z0-9:/_-]{3,256}\Z")
CLOUD_CHECKS = (
    "bucket_region_matches",
    "bucket_public_access_block_all",
    "bucket_policy_not_public",
    "bucket_owner_enforced",
    "bucket_https_only_policy",
    "bucket_default_customer_kms_key",
    "configured_kms_key_enabled",
)


def configured(env: dict[str, str]) -> bool:
    mode = env.get("KAUSHALWATCH_ENV", "").strip().lower()
    protected = mode in {"pilot", "production", "prod"} or (
        mode == "staging" and
        env.get("KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT") == "true"
    )
    bucket = env.get("KAUSHALWATCH_EVIDENCE_S3_BUCKET", "")
    region = env.get("KAUSHALWATCH_EVIDENCE_S3_REGION", "")
    key = env.get("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID", "")
    return (
        protected
        and env.get("KAUSHALWATCH_STORAGE_BACKEND") == "postgres"
        and env.get("KAUSHALWATCH_EVIDENCE_BACKEND") == "s3"
        and bool(BUCKET.fullmatch(bucket))
        and bool(REGION.fullmatch(region))
        and bool(KEY.fullmatch(key))
        and not env.get("KAUSHALWATCH_EVIDENCE_S3_ENDPOINT_URL")
    )


def _list(value: Any) -> list:
    return value if isinstance(value, list) else [value]


def _tls_policy(policy: Any, bucket: str) -> bool:
    """Conservatively require unconditional wildcard deny on insecure transport.

    More complicated equivalent policies require independent human inspection
    rather than making a possibly unsafe positive claim.
    """
    if not isinstance(policy, str) or len(policy) > 64 * 1024:
        return False
    try:
        value = json.loads(policy)
        if not isinstance(value, dict):
            return False
        covered = set()
        for statement in _list(value.get("Statement", [])):
            if not isinstance(statement, dict):
                continue
            if (statement.get("Effect") != "Deny"
                    or statement.get("Principal") != "*"
                    or statement.get("Condition") != {
                        "Bool": {"aws:SecureTransport": "false"}
                    }):
                continue
            actions = _list(statement.get("Action", []))
            if "s3:*" not in actions:
                continue
            for resource in _list(statement.get("Resource", [])):
                if resource in {
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*",
                }:
                    covered.add(resource)
        return covered == {
            f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"
        }
    except (ValueError, TypeError):
        return False


def _okay(callback) -> bool:
    try:
        return bool(callback())
    except Exception:
        # AWS exceptions may contain bucket IDs, account details and URLs.
        # No exception type/message or credential is included in receipts.
        return False


def evaluate(env: dict[str, str], *, probe: bool = False,
             s3=None, kms=None) -> dict[str, Any]:
    valid = configured(env)
    checks: dict[str, str] = {
        "protected_storage_configuration": "PASS" if valid else "BLOCKED",
    }
    checks.update({name: ("NOT_PROBED" if not probe else "BLOCKED")
                   for name in CLOUD_CHECKS})
    contacted_cloud = False
    if probe and valid:
        bucket = env["KAUSHALWATCH_EVIDENCE_S3_BUCKET"]
        region = env["KAUSHALWATCH_EVIDENCE_S3_REGION"]
        configured_key = env["KAUSHALWATCH_EVIDENCE_KMS_KEY_ID"]
        try:
            options = Config(signature_version="s3v4",
                             retries={"max_attempts": 2, "mode": "standard"},
                             connect_timeout=5, read_timeout=8)
            # The normal AWS SDK provider chain supplies credentials to a
            # privately authorized operator runtime; values are never logged.
            s3 = s3 if s3 is not None else boto3.client(
                "s3", region_name=region, config=options)
            kms = kms if kms is not None else boto3.client(
                "kms", region_name=region, config=options)
            contacted_cloud = True

            def check(name: str, callback) -> None:
                checks[name] = "PASS" if _okay(callback) else "BLOCKED"

            check("bucket_region_matches", lambda: (
                (s3.get_bucket_location(Bucket=bucket)
                 .get("LocationConstraint") or "us-east-1") == region))
            def public_controls() -> bool:
                flags = s3.get_public_access_block(Bucket=bucket)[
                    "PublicAccessBlockConfiguration"]
                return all(flags.get(flag) is True for flag in (
                    "BlockPublicAcls", "IgnorePublicAcls",
                    "BlockPublicPolicy", "RestrictPublicBuckets"
                ))

            check("bucket_public_access_block_all", public_controls)
            check("bucket_policy_not_public", lambda: (
                s3.get_bucket_policy_status(Bucket=bucket)
                ["PolicyStatus"]["IsPublic"] is False))
            check("bucket_owner_enforced", lambda: any(
                item.get("ObjectOwnership") == "BucketOwnerEnforced"
                for item in s3.get_bucket_ownership_controls(Bucket=bucket)
                ["OwnershipControls"]["Rules"]))
            check("bucket_https_only_policy", lambda: _tls_policy(
                s3.get_bucket_policy(Bucket=bucket)["Policy"], bucket))

            def kms_check() -> bool:
                rules = s3.get_bucket_encryption(Bucket=bucket)[
                    "ServerSideEncryptionConfiguration"]["Rules"]
                if len(rules) != 1:
                    return False
                default = rules[0]["ApplyServerSideEncryptionByDefault"]
                if default.get("SSEAlgorithm") != "aws:kms":
                    return False
                default_key = default.get("KMSMasterKeyID")
                if not isinstance(default_key, str) or not default_key:
                    return False
                requested = kms.describe_key(KeyId=configured_key)["KeyMetadata"]
                selected = kms.describe_key(KeyId=default_key)["KeyMetadata"]
                checks["configured_kms_key_enabled"] = (
                    "PASS" if requested.get("KeyState") == "Enabled"
                    and requested.get("KeyManager") == "CUSTOMER"
                    and requested.get("Enabled") is True
                    else "BLOCKED"
                )
                return (
                    checks["configured_kms_key_enabled"] == "PASS"
                    and isinstance(requested.get("Arn"), str)
                    and requested["Arn"] == selected.get("Arn")
                )

            check("bucket_default_customer_kms_key", kms_check)
        except Exception:
            # A failed SDK setup itself is a blocked cloud preflight.
            pass

    passing = valid and probe and all(
        checks[k] == "PASS" for k in CLOUD_CHECKS
    )
    return {
        "schema": SCHEMA,
        "cloud_read_only_preflight": "CHECKS_PASS" if passing else "BLOCKED",
        "probe_attempted": contacted_cloud,
        "checks": checks,
        "aws_iam_least_privilege_independently_verified": False,
        "kms_encrypt_decrypt_permissions_verified": False,
        "object_level_retention_and_legal_hold_verified": False,
        "physical_camera_accuracy_verified": False,
        "real_site_deployment_independently_verified": False,
        "pilot_activation": BLOCKED,
        "autonomous_enforcement_authorized": False,
        "secrets_or_source_identifiers_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Private S3/KMS read-only operator audit; never accesses evidence objects")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true",
                      help="Offline status; no AWS SDK requests or credentials")
    mode.add_argument("--probe-cloud", action="store_true",
                      help="Read live AWS bucket/KMS controls using operator IAM")
    args = parser.parse_args()
    report = evaluate(dict(os.environ), probe=args.probe_cloud)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if args.status or report["cloud_read_only_preflight"] == "CHECKS_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
