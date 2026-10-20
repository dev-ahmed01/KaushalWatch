"""Phase 8: immutable, privacy-minimal pilot technical-evidence handoff.

Assembles already-produced read-only acceptance receipts, not another pilot
gate or a self-declared authorization. A release SHA and SHA-256 pins bind
inputs without copying personal identifiers, camera source names, URLs,
credentials, raw metrics, policy details or keys into the handoff output.
Independent signatures are reverified when a field dossier is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from scripts.pilot_release_lock import valid_lock
from evaluation.camera_trust_field_review import signed_dossier

INPUT_SCHEMA = "KW_PILOT_HANDOFF_INPUTS_V1"
OUTPUT_SCHEMA = "KW_PILOT_HANDOFF_V1"
BLOCKED = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
FIELD_READY = "EVIDENCE_READY_FOR_INDEPENDENT_MANUAL_REVIEW"
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
PINS = frozenset({"pilot_preflight", "release_lock", "field_bundle", "trusted_public_keys"})
REQUIRED_CHECKS = frozenset({
    "protected_environment", "postgres_selected", "postgres_dsn_configured",
    "postgres_tls_hostname_validation", "private_evidence_selected",
    "oidc_officer_identity_selected", "oidc_scoped_subject_grants_configured",
    "evidence_storage_configured", "protected_web_session", "same_origin_proxy",
    "backend_private_address", "real_centre_registry_provisioned",
    "private_sha_pinned_manifest", "centre_source_grants",
    "oauth_token_or_adc_available", "private_media_cache_is_configured",
    "real_https_readiness", "postgres_camera_schema_v3",
    "immutable_release_lock_format", "private_storage_cloud_controls",
    "camera_audit_chain_integrity", "signed_independent_field_dossier",
})


def unique(pairs: list[tuple[str, Any]]) -> dict:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("Duplicate frozen JSON member")
        output[key] = value
    return output


def _json(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Private source missing or linked")
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise ValueError("Private source size outside strict limit")
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    if not isinstance(payload, dict):
        raise ValueError("Expected frozen JSON object")
    return payload


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inputs(manifest: Path, expected_commit: str) -> tuple[dict, dict, dict]:
    if not isinstance(expected_commit, str) or not SHA40.fullmatch(expected_commit):
        raise ValueError("Expected exact 40-hex git revision")
    path = manifest.expanduser()
    if path.is_symlink():
        raise ValueError("Private manifest symlinks prohibited")
    root = path.parent.resolve()
    path = path.resolve()
    if root == ROOT or ROOT in root.parents:
        raise ValueError("Keep private operator receipts outside repository")
    doc = _json(path, 32_768)
    if (set(doc) != {"schema", "status", "release_commit", "receipts"}
        or doc["schema"] != INPUT_SCHEMA or doc["status"] != "frozen"
        or doc["release_commit"] != expected_commit
        or not isinstance(doc["receipts"], dict)):
        raise ValueError("Frozen release identity mismatch")
    pins = doc["receipts"]
    if (not {"release_lock", "pilot_preflight"} <= pins.keys()
        or set(pins) - PINS
        or ("field_bundle" in pins) != ("trusted_public_keys" in pins)):
        raise ValueError("Incomplete or unsupported private receipt set")
    results = {}
    bound = {}
    used = {path}
    for role in sorted(pins):
        spec = pins[role]
        if (not isinstance(spec, dict) or set(spec) != {"path", "sha256"}
            or not isinstance(spec["path"], str)
            or not isinstance(spec["sha256"], str)
            or not SHA64.fullmatch(spec["sha256"])):
            raise ValueError("Malformed private SHA-pinned receipt")
        rel = Path(spec["path"])
        if (rel.is_absolute() or not rel.parts
            or any(piece in {".", ".."} for piece in rel.parts)):
            raise ValueError("Receipt must be relative to approved private folder")
        current = root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Receipt symlink prohibited")
        source = current.resolve()
        if (not source.is_relative_to(root) or source in used
            or source == path):
            raise ValueError("Untrusted or duplicated receipt location")
        used.add(source)
        limit = 2 * 1024 * 1024 if role == "field_bundle" else 64 * 1024
        results[role] = _json(source, limit)
        if _sha(source) != spec["sha256"]:
            raise ValueError("Source receipt hash drift")
        bound[role] = spec["sha256"]
    return results, bound, {"manifest_sha256": _sha(path), "release_commit": expected_commit}


def assemble(manifest: Path, expected_commit: str) -> dict:
    sources, pins, release = load_inputs(manifest, expected_commit)
    lock = sources["release_lock"]
    if not valid_lock(lock, expected_commit):
        raise ValueError("Invalid immutable release lock")
    receipt = sources["pilot_preflight"]
    if (receipt.get("schema") != "KW_PILOT_ACCEPTANCE_V1"
        or receipt.get("pilot_activation") != BLOCKED
        or receipt.get("real_site_deployment_independently_verified") is not False
        or receipt.get("external_operator_approval_recorded") is not False
        or receipt.get("autonomous_enforcement_authorized") is not False
        or receipt.get("physical_camera_health") != "UNKNOWN"
        or receipt.get("secrets_or_source_identifiers_emitted") is not False
        or receipt.get("software_preflight") not in {"CHECKS_PASS", "BLOCKED"}
        or type(receipt.get("eligible_to_request_external_pilot_signoff")) is not bool
        or not isinstance(receipt.get("checks"), dict)):
        raise ValueError("Unsupported or falsely authorizing pilot preflight receipt")

    if set(receipt) != {
        "schema", "software_preflight", "field_evidence",
        "eligible_to_request_external_pilot_signoff",
        "real_site_deployment_independently_verified",
        "external_operator_approval_recorded", "autonomous_enforcement_authorized",
        "pilot_activation", "physical_camera_health", "checks",
        "blocking_check_names", "external_evidence_not_independently_verified",
        "operator_actions_remaining", "secrets_or_source_identifiers_emitted",
    }:
        raise ValueError("Unexpected pilot preflight schema")
    checks = receipt["checks"]
    if not REQUIRED_CHECKS <= checks.keys():
        raise ValueError("Pilot preflight is incomplete")
    if any(not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,100}", name)
           or value not in {"PASS", "BLOCKED", "NOT_PROBED", "NOT_SUBMITTED", "NOT_VERIFIED",
                             "NOT_REQUIRED_LOCAL_ONLY"} for name, value in checks.items()):
        raise ValueError("Unsafe preflight status")
    # Only this known exception may be left for external field approval.
    technical = {k:v for k,v in checks.items() if k != "external_custody_and_field_accuracy"}
    expected_green = all(value == "PASS" for value in technical.values())
    if (receipt.get("field_evidence") != (
        FIELD_READY if checks["signed_independent_field_dossier"] == "PASS"
        else "BLOCKED_OR_NOT_SUBMITTED"
    ) or receipt.get("blocking_check_names") != sorted(
        name for name, state in technical.items() if state != "PASS"
    )):
        raise ValueError("Pilot receipt blocklist or field status contradicts checks")
    if ((receipt["software_preflight"] == "CHECKS_PASS") != expected_green
        or receipt["eligible_to_request_external_pilot_signoff"] != expected_green):
        raise ValueError("Contradictory technical acceptance receipt")
    independently_signed = False
    if "field_bundle" in sources:
        try:
            dossier = signed_dossier(sources["field_bundle"], sources["trusted_public_keys"])
            independently_signed = dossier.get("manual_review_readiness") == FIELD_READY
        except (ValueError, TypeError, KeyError, RuntimeError):
            independently_signed = False
    if checks["signed_independent_field_dossier"] == "PASS" and not independently_signed:
        # The original gate's word PASS cannot replace the field signatures:
        # reject reassembly rather than reporting a green technical claim.
        raise ValueError("Referenced field PASS not independently reproducible")
    if independently_signed and checks["signed_independent_field_dossier"] != "PASS":
        raise ValueError("Preflight disagrees with independently verified field dossier")
    if expected_green and not independently_signed:
        raise ValueError("Technical green requires independently rechecked field signatures")

    blockers = sorted(k for k, v in technical.items() if v != "PASS")
    if checks.get("external_custody_and_field_accuracy") != "PASS":
        blockers.append("external_custody_and_field_accuracy")
    blockers += [
        "external_operator_go_no_go",
        "actual_running_image_digest_observation",
        "real_infrastructure_restore_approval",
        "physical_centre_authorization",
    ]
    return {
        "schema": OUTPUT_SCHEMA,
        "release_commit": expected_commit,
        "manifest_sha256": release["manifest_sha256"],
        "source_receipt_sha256": pins,
        "software_checks_reproducible": expected_green,
        "field_signatures_reverified": independently_signed,
        "technical_review_candidate": expected_green and independently_signed,
        "status": ("READY_FOR_EXTERNAL_OPERATOR_REVIEW" if expected_green and independently_signed
                   else "BLOCKED_MISSING_OR_FAILED_EVIDENCE"),
        "check_summary": {
            "passed": sum(v == "PASS" for v in technical.values()),
            "blocked": sum(v != "PASS" for v in technical.values()),
        },
        "blocking_or_external_approval_items": sorted(set(blockers)),
        "external_operator_approval_recorded": False,
        "running_deployment_digests_independently_verified": False,
        "real_site_deployment_independently_verified": False,
        "autonomous_enforcement_authorized": False,
        "pilot_activation": BLOCKED,
        "secrets_or_source_identifiers_emitted": False,
        "limitations": (
            "SHA pins prove byte identity, not field authenticity. Valid Ed25519 roles "
            "do not establish that their keys belong to appointed reviewers. Release "
            "references are format-checked; live registry, running images, real recovery "
            "and site authorization require separate external operator verification."
        ),
    }


def write_packet(output: Path, payload: dict) -> None:
    requested = output.expanduser()
    if requested.is_symlink():
        raise ValueError("Cannot overwrite symlink")
    target = requested.resolve()
    if ROOT == target or ROOT in target.parents:
        raise ValueError("Keep handoff receipts outside source repository")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble private, non-authorizing pilot technical handoff")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = assemble(args.manifest, args.expected_commit)
        write_packet(args.out, result)
    except (ValueError, OSError, TypeError, KeyError, UnicodeError, json.JSONDecodeError):
        print(json.dumps({"schema": OUTPUT_SCHEMA,
                          "status": "BLOCKED_INVALID_PRIVATE_EVIDENCE",
                          "pilot_activation": BLOCKED,
                          "external_operator_approval_recorded": False}))
        return 2
    print(json.dumps({
        "schema": OUTPUT_SCHEMA, "status": result["status"],
        "technical_review_candidate": result["technical_review_candidate"],
        "pilot_activation": BLOCKED,
    }))
    return 0 if result["technical_review_candidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
