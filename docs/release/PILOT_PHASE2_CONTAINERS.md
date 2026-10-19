# KaushalWatch — pilot phase 2: reproducible release containers

**Delivery:** the four-module KaushalWatch CRM and its private Camera Trust worker now have separate, rootless container build specifications. This release adds an automated synthetic image smoke test. It is not a live site deployment or independently certified detector.

## Images and trust boundaries

- `Dockerfile.api` — FastAPI on port 8000, Python 3.12, non-root UID 10001. Defaults to `KAUSHALWATCH_ENV=pilot`, PostgreSQL, S3 evidence and OIDC. **Never** starts schema migration implicitly. An unprovisioned instance cannot be treated as ready; deploy only after PostgreSQL v3 migration and secure grants. One worker process per image unless load testing confirms safe concurrency.
- `Dockerfile.web` — Next.js 16 on port 3000, non-root Node user. The `NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true` switch is compiled at image build time, so browser requests use same-origin, HttpOnly officer sessions and CSRF-protected BFF. Runtime defaults are protected/OIDC; all IdP URLs, encrypted Redis REST sessions and private API address must be provided securely at runtime, never baked in.
- `Dockerfile.camera-trust-worker` (existing) — private Drive worker with SHA-pinned sources and no public port. Never bundle real CCTV into any image.
- `.dockerignore` — default-denies build context and explicitly permits reviewed source/config files and only the three small SHA-pinned synthetic preview recordings. The image CI checks that no original videos, model binaries or `.env` files are baked in.

## Build from an immutable, tracked source revision

Create the build context from Git-tracked files, not a local data/video folder. On a trusted Linux operator host:

```bash
set -euo pipefail
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git archive --format=tar HEAD | tar -xf - -C "$tmp"
docker build --pull -f "$tmp/Dockerfile.api" -t kaushalwatch-api:pilot "$tmp"
docker build --pull -f "$tmp/Dockerfile.web" -t kaushalwatch-web:pilot "$tmp"
```

Tags are **not** deployment approvals. For a deployment, pin the built image digest and commit SHA in the release/change record. Do not run a local development API in the internet-facing environment.

## Host/network prerequisites

1. Deploy FastAPI to a private network with a separately approved **HTTPS** origin accessible to the BFF; the BFF rejects a plain-http remote API origin. Do not publicly expose the API except through explicitly approved network policy. Make the Next.js web service externally reachable over HTTPS through a trusted ingress.
2. Provision PostgreSQL 16+ with TLS validation and `scripts/migrate_postgres.py --check` after independently applying v3 migrations from an authorized migration-only runtime. No destructive automatic seeding of demo records.
3. Provision private S3, block public object access, approved SSE-KMS policy and runtime identity. Set `KAUSHALWATCH_EVIDENCE_BACKEND=s3`, region, bucket and key alias outside Git.
4. Configure organization RS256 OIDC issuer, pinned JWKS, dedicated API audience, subject-to-centre grants, and the web callback. Use protected web mode, distributed encrypted Redis REST sessions and a unique 32-byte base64 session key. The internal API origin must be bare HTTPS; the BFF blocks non-loopback HTTP.
5. Keep the camera worker isolated, with source-authorized centre registry and a private pinned Drive manifest, token/ADC credentials, reference directory and media cache. Original videos stay in the approved private source; never upload them to Git, the frontend or this chat.
6. Configure process *liveness* separately from *readiness*: `/api/health` is a process check, while `/api/ready` is a no-secret status that must report `{"ready":true}` before taking requests. Do not treat the readiness boolean as an IdP MFA, KMS or field accuracy attestation.

## Automated acceptance

The workflow `.github/workflows/pilot-release-containers.yml` builds API and web from reviewed source, verifies non-root users and omitted private assets, starts an isolated synthetic API using JSON/demo mode, and starts the protected browser without a session to confirm anonymous proxy denial. The main repository CI independently tests OIDC, PostgreSQL, officer audit, browser access and Camera Trust research gates.

The synthetic API smoke expressly overrides pilot settings **only within CI**. Never use those overrides to operate a real centre.

## External acceptance

On a secured operator workstation with real infrastructure configured:

```bash
python scripts/migrate_postgres.py --check
python scripts/check_protected_staging.py --api https://api.example.org --web https://console.example.org
python scripts/check_pilot_rollout.py --api https://api.example.org --web https://console.example.org --probe-database --release-lock /secure/releases/release-lock.json --expected-release-commit FULL_40_CHARACTER_HEX_SHA --field-bundle /secure/field/review.json --trusted-public-keys /secure/field/trusted-keys.json --output /secure/receipts/pilot.json
```

This does not create a pilot. The external owner must verify hosted OIDC MFA/revocation, cloud IAM/KMS and disaster recovery, private source custody, blind physical-camera labels, false-alert burden and real operator approval. The signed-field gate can mark a package ready **to request** sign-off; `pilot_activation` and autonomous enforcement remain blocked.

No existing app service/account was modified or charged by this code release.

## Immutable release lock, OCI revision labels and CI evidence

Container CI now records the actual checked-out Git commit in each API/web
image's OCI org.opencontainers.image.revision label, and attaches a short-lived
kw-local-image-evidence.json artifact. For pull requests, GitHub Actions may
check out a synthetic merge commit, rather than the PR branch head. This CI
artifact contains only local Docker image IDs and explicitly states it does
NOT prove registry publication, deployability, or a real site deployment.

The operator must independently publish the audited API and web images in an
approved private registry, inspect their immutable pullable manifest digests
and revision labels, then create a private release lock matching this schema.
Replace the placeholder SHA values with full real lowercase hex strings:

~~~json
{
  "schema": "KW_PILOT_RELEASE_LOCK_V1",
  "source_commit": "FULL_40_CHARACTER_HEX_SHA",
  "images": {
    "api": "registry.example.org/project/api@sha256:FULL_64_CHARACTER_HEX_DIGEST",
    "web": "registry.example.org/project/web@sha256:FULL_64_CHARACTER_HEX_DIGEST"
  },
  "database": {
    "required_migrations": [1, 2, 3],
    "apply": "separate_approved_migration_only_role",
    "verify": "scripts/migrate_postgres.py --check"
  },
  "rollback": {
    "on_failed_readiness": "halt_traffic_and_request_operator_review",
    "database_rollback": "manual_restore_from_verified_isolated_backup_only"
  }
}
~~~

The manifest format gate refuses floating image tags, wrong source revisions,
omitted v3 schema migration requirements, or destructive automatic rollback
instructions. It is a *format-only* check; no registry is contacted and no
credentials are read. Do not mistake a format PASS for a verified registry
signature, live running digest, production backup/restore, OIDC/IAM inspection
or real camera assessment.

The roll-forward order remains: inspect and freeze immutable images; verify
an isolated backup/restore; apply database migrations using a distinct approved
migration-only identity; run the read-only --check; stage candidate app versions
without routing protected officer traffic; verify both API and browser
dependencies plus real HTTPS/OIDC; only then request manual operator acceptance.
On any failure stop routing pilot traffic. Revert API/web only after checking
compatibility with the current database. Never automatically reverse the schema
or restore over active records.

The private pilot gate now also requires the lock and expected source commit.
No automatic provisioning, publication, migration, DNS mutation or activation
is performed by this workflow.
