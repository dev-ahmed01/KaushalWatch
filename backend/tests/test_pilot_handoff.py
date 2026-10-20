"""Pilot multi-receipt handoff never elevates CI or self-report into field approval."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend/tests")]
from scripts.assemble_pilot_handoff import (
    INPUT_SCHEMA, OUTPUT_SCHEMA, BLOCKED, assemble, load_inputs, write_packet,
)
from scripts.check_pilot_rollout import evaluate
from test_camera_trust_field_review import signed_fixture
from test_pilot_release_lock import example_lock

COMMIT = "a" * 40


def write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    return path


def pin(path: Path) -> dict:
    return {
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def prepare(root: Path, *, all_green: bool = False, signed: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lock = write_json(root / "release-lock.json", example_lock())
    receipt = evaluate({})
    if all_green:
        receipt["checks"] = {
            k: ("NOT_VERIFIED" if k == "external_custody_and_field_accuracy"
                else "PASS") for k in receipt["checks"]
        }
        receipt["software_preflight"] = "CHECKS_PASS"
        receipt["eligible_to_request_external_pilot_signoff"] = True
        receipt["field_evidence"] = "EVIDENCE_READY_FOR_INDEPENDENT_MANUAL_REVIEW"
        receipt["blocking_check_names"] = []
    preflight = write_json(root / "pilot-preflight.json", receipt)
    refs = {
        "release_lock": pin(lock),
        "pilot_preflight": pin(preflight),
    }
    if signed:
        dossier, anchors = signed_fixture()  # generated test-only Ed25519 keys
        refs["field_bundle"] = pin(write_json(root / "field.json", dossier))
        refs["trusted_public_keys"] = pin(write_json(root / "trusted.json", anchors))
    return write_json(root / "handoff-inputs.json", {
        "schema": INPUT_SCHEMA, "status": "frozen",
        "release_commit": COMMIT, "receipts": refs,
    })


def update_role(manifest: Path, role: str, edit) -> None:
    doc = json.loads(manifest.read_text())
    source = manifest.parent / doc["receipts"][role]["path"]
    value = json.loads(source.read_text())
    edit(value)
    write_json(source, value)
    doc["receipts"][role] = pin(source)
    write_json(manifest, doc)


def test_blocked_frozen_packet_is_precise_and_private(tmp_path):
    packet = assemble(prepare(tmp_path), COMMIT)
    assert packet["schema"] == OUTPUT_SCHEMA
    assert packet["status"] == "BLOCKED_MISSING_OR_FAILED_EVIDENCE"
    assert packet["technical_review_candidate"] is False
    assert packet["software_checks_reproducible"] is False
    assert packet["field_signatures_reverified"] is False
    assert packet["pilot_activation"] == BLOCKED
    assert packet["real_site_deployment_independently_verified"] is False
    assert packet["autonomous_enforcement_authorized"] is False
    assert "real_https_readiness" in packet["blocking_or_external_approval_items"]
    assert packet["release_commit"] == COMMIT
    assert set(packet["source_receipt_sha256"]) == {"release_lock", "pilot_preflight"}
    assert "password" not in json.dumps(packet).lower()


def test_signature_reverified_on_good_synthetic_fixtures_but_never_activates(tmp_path):
    file = prepare(tmp_path, all_green=True, signed=True)
    packet = assemble(file, COMMIT)
    assert packet["technical_review_candidate"] is True
    assert packet["field_signatures_reverified"] is True
    assert packet["status"] == "READY_FOR_EXTERNAL_OPERATOR_REVIEW"
    assert packet["pilot_activation"] == BLOCKED
    assert packet["external_operator_approval_recorded"] is False
    assert packet["running_deployment_digests_independently_verified"] is False
    assert packet["real_site_deployment_independently_verified"] is False
    assert "external_operator_go_no_go" in packet["blocking_or_external_approval_items"]
    assert "synthetic-site" not in json.dumps(packet)
    assert "trusted.json" not in json.dumps(packet)


def test_green_summary_without_reverified_field_signatures_fails(tmp_path):
    file = prepare(tmp_path, all_green=True)
    with pytest.raises(ValueError, match="Referenced field PASS"):
        assemble(file, COMMIT)


def test_missing_trust_anchors_or_tampered_signed_data_fails(tmp_path):
    file = prepare(tmp_path, all_green=True, signed=True)
    doc = json.loads(file.read_text())
    del doc["receipts"]["trusted_public_keys"]
    write_json(file, doc)
    with pytest.raises(ValueError, match="Incomplete"):
        assemble(file, COMMIT)
    file = prepare(tmp_path, all_green=True, signed=True)
    update_role(file, "field_bundle", lambda r: r["measurements"].update(false_alert_episodes=99))
    with pytest.raises(ValueError, match="Referenced field PASS"):
        assemble(file, COMMIT)


def test_pinned_source_modified_without_manifest_update_fails(tmp_path):
    file = prepare(tmp_path)
    source = tmp_path / "pilot-preflight.json"
    source.write_text(source.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="hash drift"):
        assemble(file, COMMIT)


def test_wrong_revision_and_release_lock_rejected(tmp_path):
    file = prepare(tmp_path)
    with pytest.raises(ValueError, match="identity mismatch"):
        assemble(file, "b" * 40)
    update_role(file, "release_lock", lambda r: r.update(source_commit="b" * 40))
    with pytest.raises(ValueError, match="Invalid immutable"):
        assemble(file, COMMIT)


def test_forged_eligible_flags_and_blocker_lists_rejected(tmp_path):
    file = prepare(tmp_path)
    update_role(file, "pilot_preflight",
                lambda r: r.update(eligible_to_request_external_pilot_signoff=True))
    with pytest.raises(ValueError, match="Contradictory"):
        assemble(file, COMMIT)
    file = prepare(tmp_path)
    update_role(file, "pilot_preflight", lambda r: r.update(blocking_check_names=[]))
    with pytest.raises(ValueError, match="blocklist"):
        assemble(file, COMMIT)


def test_preflight_claim_of_pilot_approval_rejected_even_if_signed(tmp_path):
    file = prepare(tmp_path, all_green=True, signed=True)
    update_role(file, "pilot_preflight", lambda r: r.update(pilot_activation="ACTIVE"))
    with pytest.raises(ValueError, match="falsely authorizing"):
        assemble(file, COMMIT)


def test_no_root_escape_duplicate_json_member_symlink_or_path_alias(tmp_path):
    file = prepare(tmp_path)
    obj = json.loads(file.read_text())
    obj["receipts"]["release_lock"]["path"] = "../elsewhere.json"
    write_json(file, obj)
    with pytest.raises(ValueError, match="relative"):
        assemble(file, COMMIT)
    file = prepare(tmp_path)
    alias = tmp_path / "alias.json"
    alias.symlink_to(tmp_path / "pilot-preflight.json")
    obj = json.loads(file.read_text())
    obj["receipts"]["pilot_preflight"]["path"] = "alias.json"
    obj["receipts"]["pilot_preflight"]["sha256"] = pin(tmp_path / "pilot-preflight.json")["sha256"]
    write_json(file, obj)
    with pytest.raises(ValueError, match="symlink"):
        assemble(file, COMMIT)
    file = prepare(tmp_path)
    file.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        assemble(file, COMMIT)


def test_no_overwrite_and_private_permissions(tmp_path):
    file = prepare(tmp_path)
    packet = assemble(file, COMMIT)
    out = tmp_path / "operator-packet.json"
    write_packet(out, packet)
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert json.loads(out.read_text())["pilot_activation"] == BLOCKED
    with pytest.raises(FileExistsError):
        write_packet(out, packet)


def test_cli_invalid_source_denial_does_not_echo_secrets(tmp_path):
    file = prepare(tmp_path)
    file.write_text(file.read_text() + "SECRET-SUBJECT-DO-NOT-PRINT")
    output = tmp_path / "blocked-packet.json"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/assemble_pilot_handoff.py"),
        "--manifest", str(file), "--expected-commit", COMMIT,
        "--out", str(output),
    ], capture_output=True, text=True, cwd=ROOT, timeout=20)
    assert result.returncode == 2
    assert "SECRET-SUBJECT" not in result.stdout + result.stderr
    assert not output.exists()
    assert json.loads(result.stdout)["pilot_activation"] == BLOCKED


def test_cli_blocked_inputs_generate_nonauthorizing_packet_exit_2(tmp_path):
    file = prepare(tmp_path)
    output = tmp_path / "blocked-packet.json"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/assemble_pilot_handoff.py"),
        "--manifest", str(file), "--expected-commit", COMMIT,
        "--out", str(output),
    ], capture_output=True, text=True, cwd=ROOT, timeout=20)
    assert result.returncode == 2
    assert json.loads(output.read_text())["technical_review_candidate"] is False
    assert json.loads(result.stdout)["pilot_activation"] == BLOCKED
