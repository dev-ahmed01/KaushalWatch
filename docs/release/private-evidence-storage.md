# Central private evidence storage — release engineering

**Scope:** Server-side storage of transformed JPEG evidence frames. This does
not mean that every stored object has been independently privacy-audited.
Existing analysis pipelines still apply privacy transforms before storage.
No raw CCTV uploads or camera videos are copied to the object bucket by this feature.

## Configuration and migration

Development and isolated SIH demo use `KAUSHALWATCH_EVIDENCE_BACKEND=local`
by default; the existing on-disk `/evidence/{id}.jpg` behavior remains.

For a multi-instance pilot, set both:
```
KAUSHALWATCH_ENV=pilot
KAUSHALWATCH_STORAGE_BACKEND=postgres
KAUSHALWATCH_EVIDENCE_BACKEND=s3
KAUSHALWATCH_DATABASE_URL=postgresql://...?...sslmode=verify-full
KAUSHALWATCH_EVIDENCE_S3_BUCKET=your-private-bucket
KAUSHALWATCH_EVIDENCE_S3_REGION=ap-south-1
KAUSHALWATCH_EVIDENCE_KMS_KEY_ID=alias/your-evidence-key
```

Supply S3 credentials **only to FastAPI** through the workload's IAM identity;
never put bucket secrets or presigned links into public Next.js variables.
Do not use an untrusted `KAUSHALWATCH_EVIDENCE_S3_ENDPOINT_URL` override.
The application rejects custom S3 endpoint URLs for protected evidence.

Migrate PostgreSQL with a separate migration credential and backup:
```bash
python scripts/migrate_postgres.py --apply
python scripts/migrate_postgres.py --check
```
Version 2 introduces the unique `kw_evidence_objects` integrity index, tied to
an opaque evidence ID, centre ID, exact S3 object key, JPEG SHA-256 and
perceptual hash. The migration remains repeatable. It does **not** import or
rewrite existing local evidence files, nor scan the historical case ledger.

## Write lifecycle

The existing `persist_evidence` function dispatches to S3 only when
`KAUSHALWATCH_EVIDENCE_BACKEND=s3`. It is called from attendance,
practical-activity and infrastructure pipelines **after the existing
privacy-transform steps**.

1. Encode the transformed frame as JPEG (max 10 MiB).
2. Upload under `evidence/v1/{centre_id}/{evidence_id}.jpg` using conditional
   creation (`IfNoneMatch: *`), SSE-KMS and SHA-256 checksum metadata.
   No public ACL, browser URL or presigned URL is generated.
3. Insert one `kw_evidence_objects` row, rejecting colliding evidence IDs.
   Duplicate-image checks search **only within the current centre** and
   serialize writes for that centre with a PostgreSQL advisory lock.
4. The normal pipeline stores the resulting `EvidenceRecord` in its case.
   APIs redact its internal `frame_path` from JSON payloads.

S3 and PostgreSQL are separate systems; no distributed transaction exists.
If metadata/case persistence fails after upload, the object is **orphaned,
not accessible** from the authenticated read route. A controlled lifecycle
reconciliation process to inventory/delete stale orphan objects is still
required. Do not blindly delete objects that are under legal retention.

## Read authorization and integrity

The original `/evidence/{id}.jpg` browser path is preserved.
In S3 mode, FastAPI never mounts the local static evidence folder.
The protected request boundary validates officer identity and centre scope
against a **persisted case**, not a caller-provided centre. The route rechecks
that exactly one case evidence record matches the ID, verifies the object's
centre/key/hash against the PostgreSQL index, privately fetches the bytes, and
computes their SHA-256 before returning a JPEG response.

Cross-centre, unknown, orphaned, duplicate case reference, corrupted or missing
image requests fail closed. No evidence object is streamed unless all checks
pass. Responses use `Cache-Control: private, no-store`,
`X-Content-Type-Options: nosniff` and a restrictive CSP. Object store
failures produce a generic unavailable response rather than leaking credentials.

**Note:** In development/demo local mode, the static-file route is unchanged
and not appropriate for public deployment. Pilot/production sensitive routes
refuse JSON and local evidence storage.

## Mandatory AWS controls outside the repository

- An isolated **private bucket**, block-all-public-access, disabled ACLs,
  HTTPS-only bucket policy, and least-privilege scoped workload IAM identity.
- Policy requiring SSE-KMS and the correct key, with explicitly scoped KMS
  encrypt/decrypt permissions and audited administrative access.
- Bucket versioning / Object Lock **only after** retention, deletion and legal
  requirements are approved. Define a retention schedule for images and
  metadata, including correction requests, evidence holds and incident review.
- Configured backups, cross-region disaster recovery choices, deletion
  reconciliation, logging, anomaly alerts, key rotation and restore tests.
- Workload isolation, production IdP provisioning and rate limiting before
  government-centre onboarding.
- If using S3-compatible providers rather than AWS S3, their encryption,
  conditional-upload and checksum semantics need their own qualification.
  The current adapter deliberately targets AWS S3 only.

The application validates configuration, access and content SHA-256. It cannot
attest that an external bucket policy, KMS key policy or operational backup
exists. CI uses an in-memory S3 stand-in and an isolated real PostgreSQL
database: it is **not an AWS/KMS integration test**.

## Verify in CI and local environments

`postgres-persistence` runs the PostgreSQL v2 migration twice, verifies it,
and executes:
```bash
pytest -q backend/tests/test_postgres_storage.py backend/tests/test_s3_evidence.py
```

The second module covers private image retrieval via real FastAPI routes,
centre isolation, orphaned objects, SHA mismatch, missing image, tampered DB
index, duplicate-case and duplicate-evidence safeguards, missing KMS config
and pilot-mode fail-closed behavior. Normal backend unit tests skip the
DB-dependent S3 checks unless the isolated test database is available.

## Remaining before real pilot

1. Perform real AWS IAM/S3/KMS acceptance tests and bucket-policy inspection.
2. Implement media retention, orphan cleanup, legal holds, backup and restore.
3. Add operational telemetry, upload idempotency, edge-to-cloud image transfer,
   and durability/load/failover tests under two active FastAPI replicas.
4. Provision a real identity provider; static officer token configuration is
   still a prototype.
5. Complete independent **real-footage** accuracy qualification. This storage
   phase does not change model metrics or evaluate raw CCTV footage.

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
