"""Synthetic AWS-only read-only cloud evidence preflight contract tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.check_private_storage_cloud import _tls_policy, evaluate, CLOUD_CHECKS

BUCKET = "kw-private-ci"
KEY_ARN = "arn:aws:kms:ap-south-1:111111111111:key/abcd-1234"
ENV = {
    "KAUSHALWATCH_ENV": "pilot",
    "KAUSHALWATCH_STORAGE_BACKEND": "postgres",
    "KAUSHALWATCH_EVIDENCE_BACKEND": "s3",
    "KAUSHALWATCH_EVIDENCE_S3_BUCKET": BUCKET,
    "KAUSHALWATCH_EVIDENCE_S3_REGION": "ap-south-1",
    "KAUSHALWATCH_EVIDENCE_KMS_KEY_ID": "alias/kw-evidence",
}


def policy(bucket=BUCKET):
    return json.dumps({"Statement": [{
        "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [
            f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*",
        ],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }]})


class S3:
    def __init__(self, failures=(), **overrides):
        self.calls = []
        self.failures = set(failures)
        self.overrides = overrides

    def _answer(self, name, response, **kwargs):
        self.calls.append((name, kwargs))
        if name in self.failures:
            raise RuntimeError("S3_SECRET-DO-NOT-ECHO")
        return self.overrides.get(name, response)

    def get_bucket_location(self, **kwargs):
        return self._answer("location", {"LocationConstraint": "ap-south-1"}, **kwargs)

    def get_public_access_block(self, **kwargs):
        return self._answer("public", {"PublicAccessBlockConfiguration": {
            key: True for key in [
                "BlockPublicAcls", "IgnorePublicAcls",
                "BlockPublicPolicy", "RestrictPublicBuckets"
            ]}}, **kwargs)

    def get_bucket_policy_status(self, **kwargs):
        return self._answer("policy_status", {"PolicyStatus": {"IsPublic": False}}, **kwargs)

    def get_bucket_ownership_controls(self, **kwargs):
        return self._answer("ownership", {"OwnershipControls": {
            "Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]
        }}, **kwargs)

    def get_bucket_policy(self, **kwargs):
        return self._answer("policy", {"Policy": policy()}, **kwargs)

    def get_bucket_encryption(self, **kwargs):
        return self._answer("encryption", {"ServerSideEncryptionConfiguration": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "aws:kms", "KMSMasterKeyID": KEY_ARN,
            }}]
        }}, **kwargs)


class Kms:
    def __init__(self, state="Enabled", manager="CUSTOMER", arn=KEY_ARN):
        self.calls = []
        self.state = state
        self.manager = manager
        self.arn = arn

    def describe_key(self, *, KeyId):
        self.calls.append(KeyId)
        return {"KeyMetadata": {
            "Arn": self.arn, "KeyState": self.state,
            "KeyManager": self.manager, "Enabled": self.state == "Enabled",
        }}


def test_healthy_readonly_controls_never_access_media_or_mutate():
    s3, kms = S3(), Kms()
    report = evaluate(ENV, probe=True, s3=s3, kms=kms)
    assert report["cloud_read_only_preflight"] == "CHECKS_PASS"
    assert all(value == "PASS" for value in report["checks"].values())
    assert report["pilot_activation"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert report["real_site_deployment_independently_verified"] is False
    assert report["aws_iam_least_privilege_independently_verified"] is False
    assert set(name for name, _ in s3.calls) == {
        "location", "public", "policy_status", "ownership", "policy", "encryption",
    }
    assert all(kwargs == {"Bucket": BUCKET} for _, kwargs in s3.calls)
    assert kms.calls == ["alias/kw-evidence", KEY_ARN]
    assert not any(token in json.dumps(report) for token in
                   (BUCKET, KEY_ARN, "alias/kw-evidence", "S3_SECRET"))


@pytest.mark.parametrize(("name", "response"), [
    ("location", {"LocationConstraint": "us-east-1"}),
    ("public", {"PublicAccessBlockConfiguration": {"BlockPublicAcls": False}}),
    ("policy_status", {"PolicyStatus": {"IsPublic": True}}),
    ("ownership", {"OwnershipControls": {"Rules": [{"ObjectOwnership": "ObjectWriter"}]}}),
    ("policy", {"Policy": "{}"}),
    ("encryption", {"ServerSideEncryptionConfiguration": {"Rules": [{
        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
    }]}}),
])
def test_each_missing_or_insecure_cloud_control_blocks(name, response):
    report = evaluate(ENV, probe=True, s3=S3(**{name: response}), kms=Kms())
    assert report["cloud_read_only_preflight"] == "BLOCKED"
    assert report["checks"][{
        "location": "bucket_region_matches",
        "public": "bucket_public_access_block_all",
        "policy_status": "bucket_policy_not_public",
        "ownership": "bucket_owner_enforced",
        "policy": "bucket_https_only_policy",
        "encryption": "bucket_default_customer_kms_key",
    }[name]] == "BLOCKED"
    assert report["pilot_activation"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"


def test_aws_access_denied_never_leaks_error():
    report = evaluate(ENV, probe=True, s3=S3(failures={"public"}), kms=Kms())
    assert report["checks"]["bucket_public_access_block_all"] == "BLOCKED"
    assert "S3_SECRET-DO-NOT-ECHO" not in json.dumps(report)


@pytest.mark.parametrize(("state", "manager"), [
    ("Disabled", "CUSTOMER"), ("Enabled", "AWS"),
])
def test_disabled_or_aws_managed_kms_rejected(state, manager):
    report = evaluate(ENV, probe=True, s3=S3(), kms=Kms(state=state, manager=manager))
    assert report["checks"]["configured_kms_key_enabled"] == "BLOCKED"
    assert report["cloud_read_only_preflight"] == "BLOCKED"


def test_incorrect_kms_default_key_blocks():
    class WrongKms(Kms):
        def describe_key(self, *, KeyId):
            result = super().describe_key(KeyId=KeyId)
            if KeyId == KEY_ARN:
                result["KeyMetadata"]["Arn"] = KEY_ARN + "-other"
            return result
    result = evaluate(ENV, probe=True, s3=S3(), kms=WrongKms())
    assert result["checks"]["bucket_default_customer_kms_key"] == "BLOCKED"


def test_no_network_if_not_probed_or_config_invalid():
    s3, kms = S3(), Kms()
    report = evaluate(ENV, probe=False, s3=s3, kms=kms)
    assert report["cloud_read_only_preflight"] == "BLOCKED"
    assert all(report["checks"][name] == "NOT_PROBED" for name in CLOUD_CHECKS)
    assert not s3.calls and not kms.calls
    for invalid in [
        {**ENV, "KAUSHALWATCH_ENV": "development"},
        {**ENV, "KAUSHALWATCH_EVIDENCE_S3_ENDPOINT_URL": "http://localhost"},
        {**ENV, "KAUSHALWATCH_EVIDENCE_KMS_KEY_ID": ""},
        {**ENV, "KAUSHALWATCH_EVIDENCE_S3_BUCKET": "INVALID"},
    ]:
        blocked = evaluate(invalid, probe=True, s3=s3, kms=kms)
        assert blocked["cloud_read_only_preflight"] == "BLOCKED"
    assert not s3.calls and not kms.calls


@pytest.mark.parametrize("value", [
    {"Statement": [{"Effect": "Allow"}]},
    {"Statement": [{"Effect": "Deny", "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{BUCKET}/*",
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]},
    {"Statement": [{"Effect": "Deny", "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"],
                    "Condition": {"Bool": {"aws:SecureTransport": "true"}}}]},
])
def test_incomplete_https_deny_policy_is_not_certified(value):
    assert not _tls_policy(json.dumps(value), BUCKET)


def test_status_cli_is_offline_and_nonqualifying():
    process = subprocess.run([sys.executable,
                              str(ROOT / "scripts/check_private_storage_cloud.py"),
                              "--status"], capture_output=True, text=True,
                             cwd=ROOT, timeout=20)
    assert process.returncode == 0, process.stderr
    data = json.loads(process.stdout)
    assert data["cloud_read_only_preflight"] == "BLOCKED"
    assert data["probe_attempted"] is False
    assert data["autonomous_enforcement_authorized"] is False

def test_pilot_gate_requires_cloud_and_distinguishes_failed_probe(monkeypatch):
    import scripts.check_pilot_rollout as rollout
    monkeypatch.setattr(rollout, "check_environment", lambda *a, **kw: {
        "checks": {"other_local_controls": "PASS",
                   "external_custody_and_field_accuracy": "NOT_VERIFIED"}
    })
    missing = rollout.evaluate(ENV)
    assert missing["checks"]["private_storage_cloud_controls"] == "NOT_PROBED"
    assert not missing["eligible_to_request_external_pilot_signoff"]
    monkeypatch.setattr(rollout, "inspect_private_storage", lambda *a, **kw: {
        "cloud_read_only_preflight": "BLOCKED", "probe_attempted": True
    })
    blocked = rollout.evaluate(ENV, probe_private_storage_cloud=True)
    assert blocked["checks"]["private_storage_cloud_controls"] == "BLOCKED"
    assert not blocked["eligible_to_request_external_pilot_signoff"]


def test_status_mode_cannot_invoke_cloud_probe():
    from scripts.check_pilot_rollout import evaluate as pilot
    receipt = pilot({})
    assert receipt["checks"]["private_storage_cloud_controls"] == "NOT_PROBED"
