"""Non-deploying image evidence and release lock fail-closed tests."""
from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.pilot_release_lock import (
    BLOCKED, CI_SCHEMA, LOCK_SCHEMA, ci_evidence, load_lock, valid_lock, write_exclusive,
)

SOURCE = "a" * 40
API = "registry.example/kaushalwatch-api@sha256:" + "1" * 64
WEB = "registry.example/kaushalwatch-web@sha256:" + "2" * 64


def example_lock() -> dict:
    return {
        "schema": LOCK_SCHEMA,
        "source_commit": SOURCE,
        "images": {"api": API, "web": WEB},
        "database": {
            "required_migrations": [1, 2, 3],
            "apply": "separate_approved_migration_only_role",
            "verify": "scripts/migrate_postgres.py --check",
        },
        "rollback": {
            "on_failed_readiness": "halt_traffic_and_request_operator_review",
            "database_rollback": "manual_restore_from_verified_isolated_backup_only",
        },
    }


def test_full_pinned_manifest_is_valid_syntax_only():
    assert valid_lock(example_lock(), SOURCE)
    assert not valid_lock(example_lock(), "b" * 40)


@pytest.mark.parametrize("bad", [
    "registry.example/kw-api:latest",
    "registry.example/kw-api@sha256:" + "g" * 64,
    "https://registry.example/kw-api@sha256:" + "1" * 64,
    "registry.example/../kw-api@sha256:" + "1" * 64,
    "registry.example/kw-api@sha256:" + "1" * 64 + "?token=SECRET",
    "registry.example/kw-api@sha256:" + "1" * 64 + "\nINJECTED",
])
def test_unpinned_invalid_and_unsafe_references_block(bad):
    data = example_lock()
    data["images"]["api"] = bad
    assert not valid_lock(data, SOURCE)


def test_other_bypasses_are_rejected():
    data = example_lock()
    data["database"]["required_migrations"] = [1, 2]
    assert not valid_lock(data, SOURCE)
    data = example_lock()
    data["database"]["apply"] = "automigrate_on_server_start"
    assert not valid_lock(data, SOURCE)
    data = example_lock()
    data["rollback"]["database_rollback"] = "drop_and_reverse_schema"
    assert not valid_lock(data, SOURCE)
    data = example_lock()
    data["images"]["web"] = data["images"]["api"]
    assert not valid_lock(data, SOURCE)
    data = example_lock()
    data["unauthorized_extra_field"] = "hidden"
    assert not valid_lock(data, SOURCE)


def test_local_ci_image_ids_never_qualify_as_registry_digests(tmp_path):
    evidence = ci_evidence(SOURCE, "sha256:" + "3" * 64, "sha256:" + "4" * 64)
    assert evidence["schema"] == CI_SCHEMA
    assert evidence["registry_digest_independently_verified"] is False
    assert evidence["real_site_deployment_independently_verified"] is False
    assert evidence["pilot_activation"] == BLOCKED
    assert not valid_lock(evidence, SOURCE)
    output = tmp_path / "local-image-evidence.json"
    write_exclusive(output, evidence)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_exclusive(output, evidence)
    with pytest.raises(ValueError):
        ci_evidence(SOURCE, "sha256:" + "3" * 64, "sha256:" + "3" * 64)


def test_release_lock_loader_bounds_and_duplicate_key_rejection(tmp_path):
    location = tmp_path / "release-lock.json"
    location.write_text('{"schema":1,"schema":2}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_lock(location)
    location.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_lock(location)
    location.write_text(" " * (16 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ValueError):
        load_lock(location)


def test_cli_never_echoes_bad_content_or_implies_deployment(tmp_path):
    location = tmp_path / "release-lock.json"
    location.write_text(json.dumps(example_lock()), encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/pilot_release_lock.py"),
        "check", "--manifest", str(location), "--expected-commit", SOURCE,
    ], capture_output=True, text=True, cwd=ROOT, timeout=15)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["immutable_reference_format"] == "PASS"
    assert receipt["registry_content_or_signature_verified"] is False
    assert receipt["running_deployment_digest_verified"] is False
    assert receipt["pilot_activation"] == BLOCKED
    location.write_text('{"PRIVATE-TOKEN-DO-NOT-ECHO": "unsafe"}', encoding="utf-8")
    blocked = subprocess.run([
        sys.executable, str(ROOT / "scripts/pilot_release_lock.py"),
        "check", "--manifest", str(location), "--expected-commit", SOURCE,
    ], capture_output=True, text=True, cwd=ROOT, timeout=15)
    assert blocked.returncode == 2
    assert "PRIVATE-TOKEN-DO-NOT-ECHO" not in blocked.stdout + blocked.stderr


def test_pilot_acceptance_blocks_without_release_lock():
    from scripts.check_pilot_rollout import evaluate
    receipt = evaluate({})
    assert receipt["checks"]["immutable_release_lock_format"] == "NOT_SUBMITTED"
    assert receipt["eligible_to_request_external_pilot_signoff"] is False
    receipt = evaluate({}, release_lock=example_lock(),
                       expected_release_commit="b" * 40)
    assert receipt["checks"]["immutable_release_lock_format"] == "BLOCKED"
