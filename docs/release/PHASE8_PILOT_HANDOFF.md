# Phase 8 — Private pilot acceptance handoff

The repository already provides separate protected HTTPS, PostgreSQL v3, OIDC, S3/KMS, camera audit, release lock and Ed25519 field-dossier checks. This milestone does NOT create a second deployment engine. It assembles the existing independent, read-only receipts into one revision-bound, privacy-minimal operator handoff WITHOUT fetching original video or transmitting credentials.

## Prepare private receipt files

Use the existing procedure in PILOT_ROLLOUT_GATE.md from an authorized operator environment to produce a real pilot-preflight.json. Only a full protected-HTTPS, database, S3/KMS, camera-audit, immutable-release-lock and signed-dossier preflight can report technical PASS. Store all source files outside Git and outside any public web folder.

Create handoff-inputs.json beside the privately provisioned source files:

~~~json
{
  "schema": "KW_PILOT_HANDOFF_INPUTS_V1",
  "status": "frozen",
  "release_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "receipts": {
    "release_lock": {
      "path": "release-lock.json",
      "sha256": "<replace with actual lowercase SHA-256>"
    },
    "pilot_preflight": {
      "path": "pilot-preflight.json",
      "sha256": "<replace with actual lowercase SHA-256>"
    },
    "field_bundle": {
      "path": "field.json",
      "sha256": "<replace with actual lowercase SHA-256>"
    },
    "trusted_public_keys": {
      "path": "trusted-keys.json",
      "sha256": "<replace with actual lowercase SHA-256>"
    }
  }
}
~~~

The shown revision and hashes are placeholders: replace them with the EXACT candidate code commit and real file digests. Use Windows PowerShell Get-FileHash with -Algorithm SHA256 and lowercase the hexadecimal output. Private field and public-key files must be included together for a technical review candidate. Source signing keys must be provisioned by an independent approved organization; do not create arbitrary keys to gain acceptance.

Run from the repository root:

~~~powershell
python scripts/assemble_pilot_handoff.py --manifest "C:\Private\KW\handoff-inputs.json" --expected-commit "<exact 40-hex source SHA>" --out "C:\Private\KW\handoff-receipt.json"
~~~

It checks SHA-256 identity, path confinement, duplicate JSON keys, source size limits, the pinned API/web registry reference syntax, safe PostgreSQL migration/rollback declarations, every required pilot-preflight check and all blocker/eligibility relationships. It independently reruns the three-role Ed25519 field-dossier signature checks using the supplied trusted public keys. Only a small status/check-count/commit/digest-only receipt is written; no detailed field measurements, identities, media, URLs, private keys or secrets are copied.

The file is created once, with 0600 permissions, and cannot overwrite an existing report. Blocked technical evidence yields a blocked receipt and CLI exit 2. Valid technical prerequisites produce READY_FOR_EXTERNAL_OPERATOR_REVIEW and exit 0, but the output ALWAYS says pilot_activation BLOCKED_PENDING_EXTERNAL_AUTHORIZATION, external_operator_approval_recorded false, autonomous_enforcement_authorized false and real_site_deployment_independently_verified false.

## What still needs real operator signoff

A SHA proves file identity, NOT the authenticity of a signed institution or whether a policy was preregistered honestly. An Ed25519 signature does not itself establish the actual custodian's authorized identity. Registry digest strings are syntax-checked but not compared against the actually running API/web images. Real rollback/restore, HTTPS IdP/MFA/revocation, physical camera licensing, source truth and governed pilot authorization remain separate operator requirements.

Never auto-activate camera enforcement based on the packet, green CI, demo media or exit code 0. Real acceptance remains Issue #91. Research branches remain out of main. There is no new product UI module and no upload loop.

## CI and local checks

~~~powershell
python -m pytest -q backend/tests/test_pilot_handoff.py
python scripts/check_pilot_rollout.py --status
~~~

The tests generate ephemeral synthetic field signatures, pinned files and deliberately altered receipts to verify fail-closed behavior. Their result is never real-centre certification.
