# KaushalWatch — real-centre pilot acceptance gate

This milestone follows the four completed officer OS/CRM sprints. The new gate combines current configuration, HTTPS staging, database and field-dossier checks. It generates a bounded, non-sensitive JSON readiness receipt. It never starts or certifies a real deployment.

## One private, repeatable operator workflow

1. Provision one or more approved real centres in the private versioned KW_CENTRE_REGISTRY_V1 setting. Provision centre-scoped OIDC grants, PostgreSQL with schema v3, private S3/KMS evidence custody, protected Next.js sessions, and the separate private Camera Trust worker with its SHA-pinned Drive manifest and centre-source grants. None of the files, recordings, credentials or subjects belong in Git.
2. Use the approved secret manager to supply environment variables to a secured operator runtime; do not paste full production .env values into chat or public CI.
3. Run the offline status command: python scripts/check_pilot_rollout.py --status. This does not access any service or inspect private files.
4. Once an actual deployment and independently signed field evidence exist, run the following command using real HTTPS origins, not localhost or placeholder endpoints:

    python scripts/migrate_postgres.py --check

    python scripts/check_pilot_rollout.py --api https://api.example.org --web https://officers.example.org --probe-database --probe-private-storage-cloud --release-lock /secure/releases/release-lock.json --expected-release-commit FULL_40_CHARACTER_HEX_SHA --field-bundle /secure/field/review.json --trusted-public-keys /secure/field/trusted-keys.json --output /secure/receipts/pilot.json

5. A signed field dossier must use KW_CAMERA_FIELD_REVIEW_V1 and three distinct, separately trusted Ed25519 public keys. The frozen measurement and policy validator is the existing evaluation/camera_trust_field_review.py. Raw videos are never read by this gate.
6. The output is created with exclusive-create mode and private user permissions (0600); it refuses a path anywhere inside the repository. It contains checks and blockers only. No camera source names, Drive IDs, URLs, access tokens, DB credentials, field images or individual trainee data are included.

## What a PASS means

The acceptance receipt uses the exact schema KW_PILOT_ACCEPTANCE_V1. A full technical PASS requires configured approved source grants and worker credentials, a live PostgreSQL schema probe, a real HTTPS API and browser check, and independently signed field evidence meeting a pre-registered policy. Even if these pass, pilot_activation remains BLOCKED_PENDING_EXTERNAL_AUTHORIZATION, autonomous_enforcement_authorized remains false, and physical_camera_health remains UNKNOWN.

External authorization must be recorded and verified outside this script, including real SSO MFA and subject revocation, S3/KMS IAM inspection, disaster recovery, source custody, false-alert burden, operator latency and independent field truth. The software cannot certify these from a runtime environment variable or CI simulation.

## CI and rollout boundaries

The CI suite exercises unsafe transport, missing signed evidence, fake signatures, withheld grants, non-secret receipts, and versioned source-registry isolation. Passing synthetic CI cannot claim real pilot readiness. The prior private worker and dashboard still run in shadow/officer-review mode, with no automatic sanction or compliance incident mutation.

No additional UI modules were added. Officer navigation remains KaushalAI, Centres, Insights, Actions. Real centre pilot setup is a controlled deployment operation, not a demo-video re-upload workflow. Research drafts remain unmerged.

## Immutable image provenance prerequisite

The private pilot gate now requires --release-lock and
--expected-release-commit together, in addition to live HTTPS, database and
independent field-dossier checks. Missing or mutable image references, source
revision mismatch, incomplete schema v3 migrations, or unsafe automatic database
rollback instructions block eligibility to request operator sign-off.

Run the read-only format check before any real operator-led migration or rollout:

~~~bash
python scripts/pilot_release_lock.py check \
  --manifest /secure/releases/release-lock.json \
  --expected-commit FULL_40_CHARACTER_HEX_SHA
~~~

The exact JSON contract is in PILOT_PHASE2_CONTAINERS.md. This syntax check does
NOT verify that registry digests exist, that either image is running, that
image signatures are trusted, that the rollback image works with migrated
data, or that field-camera results are valid. The external operator remains
responsible for independently checking those facts and authorizing the pilot.

## Verified PostgreSQL TLS transport

Protected pilot API and migration processes reject candidate PostgreSQL
connection strings without explicit `sslmode=verify-full` and
`gssencmode=disable` (plus a concrete host). The deployment preflight reports
only `postgres_tls_hostname_validation: PASS/BLOCKED`; it never prints a DSN.
Independent cloud CA, host identity, network policy and backup/restore remain
operator responsibilities. Real certificate failures stop readiness and pilot
acceptance; synthetic local CI connections are not production qualifications.

## Real read-only AWS bucket/KMS controls

A live operator probe is now required for *technical eligibility* to request
pilot approval: run `scripts/check_private_storage_cloud.py --probe-cloud`
from a privately authorized workload (or use
`scripts/check_pilot_rollout.py --probe-private-storage-cloud` with the other
normal checks). **Status-only mode uses no AWS credentials or network calls.**

The probe performs only read-only AWS control-plane calls:
bucket location, public-access block, public policy status, bucket ownership,
HTTPS-only deny policy, default SSE-KMS and KMS DescribeKey. The latter checks
that the bucket's default key resolves to the configured enabled customer-managed
key. It does **not** list or fetch evidence, write an object, decrypt a key,
change configuration, inspect raw video, or output the bucket/account/key
identifiers. Incomplete IAM permissions return BLOCKED, never a claimed PASS.

This is a *bounded technical configuration observation*, **not** independent
proof of IAM least privilege, real encrypt/decrypt permissions, data retention,
object-lock/legal hold, operational recovery, organization identity policy, or
physical-camera accuracy. The pilot stays blocked until separate operator
sign-off and independent field assessment.


## PostgreSQL Camera Trust audit-chain acceptance (read-only)

Before requesting technical pilot sign-off, run the strictly read-only
\`python scripts/check_camera_audit_integrity.py --probe-database\` from
the authorized private operator process with an approved protected
\`KAUSHALWATCH_DATABASE_URL\`. The unified gate now also requires
\`--probe-camera-audit\` alongside the existing HTTPS, v3 schema, immutable
image, private bucket/KMS and signed independent field checks.

The audit verifier reads the **entire available v3 history**, not merely
the first 2,000 UI-visible events. It walks the append-only records under
one repeatable-read MVCC snapshot, checks that every registered camera has
an audit, all sequences start at one without gaps, each previous/event
SHA-256 matches the canonical application hash, and the audit update/delete
trigger remains enabled. A bounded maximum of 250,000 events fails CLOSED
rather than truncating history and reporting a false PASS; a larger site
requires a separately reviewed scaling plan.

The receipt contains only generic check names/statuses, never camera IDs,
source names, observed images, hashes, subjects or PostgreSQL credentials.
No footage is downloaded; no database mutation, restore or source upload
occurs. **This is not proof against a privileged database administrator
rewriting and re-signing the entire chain**, nor independent physical-camera
custody/accuracy evidence. Pilot activation remains blocked.
