# Camera Trust — Phases 8 and 9 release operations

**Software package:** implemented, tested in CI. **Site deployment:** not verified. **Physical tamper detection:** not field-qualified. **Autonomous enforcement:** disabled.

This document finishes the operations *software and evidence gates*. It does not invent the physical camera evidence, hosting credentials, independent adjudication or authorization needed to certify a real site.

## Shipped architecture

- Protected Next.js officer UI and existing OIDC/CSRF same-origin proxy.
- Centre-scoped FastAPI Camera Trust routes, PostgreSQL v3 storage, immutable audit and independent reference approval.
- Private, rootless Docker worker with resumable authenticated Google Drive transfers, SHA-256 pins, centre-specific grants, retries, cancellable leases and private media cache.
- Sparse diagnostic cues, explicit UNKNOWN health states, human-only review.
- Privacy-filtered PostgreSQL numeric export and frozen external holdout evaluator.
- Read-only deployment preflight plus Ed25519 three-party signed field-review verifier.
- CI synthetic tests for worker/container, browser, auth, PostgreSQL and cryptographic failure paths.

## Hosting boundary

No confirmed KaushalWatch deployment target is linked in the connected Vercel account. Do not deploy over a different project or create a billable project without an authorized target. A live deployment must have an approved persistent database, private evidence storage, OIDC identity provider, shared secure sessions and private source-volume credentials. No video bytes or identity secrets may be committed to this public repository.

Target flow: protected Next.js -> server-side session/CSRF BFF -> private FastAPI -> PostgreSQL, with existing protected S3+KMS evidence store. An independent rootless CPU worker -> authenticated Google Drive/private persistent cache -> numeric PostgreSQL observations. There must be no exposed worker port or unauthenticated CCTV/media endpoint.

## Phase 8 — controlled shadow-pilot checklist

1. Provision an authorized isolated staging/pilot namespace with private DNS, HTTPS ingress, secrets manager, persistent encrypted PostgreSQL, and existing protected S3 bucket/region/KMS config.
2. Explicitly run database migration and verification:
    
        python scripts/migrate_postgres.py --apply
        python scripts/migrate_postgres.py --check

3. Configure API: KAUSHALWATCH_ENV=pilot, KAUSHALWATCH_STORAGE_BACKEND=postgres, KAUSHALWATCH_EVIDENCE_BACKEND=s3, KAUSHALWATCH_DATABASE_URL, KAUSHALWATCH_REVIEW_AUTH_MODE=oidc, KAUSHALWATCH_OIDC_GRANTS_JSON, and the configured OIDC issuer/audience. Set KAUSHALWATCH_EVIDENCE_S3_BUCKET, KAUSHALWATCH_EVIDENCE_S3_REGION and KAUSHALWATCH_EVIDENCE_KMS_KEY_ID; no custom plaintext evidence endpoint.
4. Configure web in protected mode: KAUSHALWATCH_WEB_AUTH_MODE=protected, NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true, KAUSHALWATCH_API_INTERNAL_URL pointed at the private API, a strong session encryption key and shared protected session store. Require a verified officer identity and CSRF for writes.
5. Provision a private Drive manifest with frozen SHA pins and KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON mapping source aliases to single centres. Provision the approved reference PNGs and authorized Drive token/ADC in secure filesystem mounts, not source code. Run the independent rootless worker from compose.camera-trust-worker.yaml. The Linux media-cache mount must be writable by worker uid 10001; original video and OAuth may never be baked into the image.
6. Run read-only checks in the actual respective service environments:

        python scripts/check_camera_trust_deployment.py --component api --probe-database
        python scripts/check_camera_trust_deployment.py --component web
        python scripts/check_camera_trust_deployment.py --component worker --probe-database
        python scripts/run_camera_trust_worker.py --preflight
        python scripts/evaluate_camera_trust_holdout.py --status
        python scripts/review_camera_trust_field.py --status

   Checks only disclose check names and statuses, no secret values. The status commands deliberately report field release BLOCKED until external evidence is available.

7. Run a permitted source-pinned job. Confirm job completion, strictly scoped officer read access, independent reference approval, immutable audit, explicit failed-source behavior, request idempotency, cancellation/lease revocation, and zero mutations to compliance cases. This is a shadow pilot, not automatic camera integrity enforcement.

## Phase 9 — independent field-review process

1. Independently verify physical cameras, custody, footage, the reference image, and meaningful normal operating hours, day/night/IR and occlusion/movement conditions.
2. Freeze thresholds, minimum normal camera-hours, minimum real physical tamper events per class, and false-alert episode/latency criteria **before** collecting evaluation data. The sample values in synthetic tests are format examples only, not validated thresholds.
3. Blinded adjudicators evaluate physical events. Store the source annotation digest and external evidence separately, with no detector-threshold retuning on the untouched holdout.
4. Use the private database exporter and offline evaluator on the locked real labels:

        python scripts/export_camera_trust_holdout.py --labels /private/labels.json --output /private/numeric.json
        python scripts/evaluate_camera_trust_holdout.py --labels /private/labels.json --predictions /private/numeric.json --output /private/holdout.json

   The numeric output contains sparse clip-level review candidates, not true field alert episodes per camera-hour.
5. Separately collect field **operator alert episodes** and event latency with independent human review. Obtain three *distinct* trusted Ed25519 attestations of one canonical dossier: source_custodian, independent_adjudicator and release_authority. Trusted public key anchors must come from an independent secure channel, not from the untrusted dossier.

        python scripts/review_camera_trust_field.py --bundle /private/signed-field-dossier.json --trusted-public-keys /private/trusted-public-keys.json --output /private/field-receipt.json

   Dossier schema: KW_CAMERA_FIELD_REVIEW_V1; fields schema, policy, measurements and signatures. Policy includes a SHA-256, a declared pre-pilot freeze timestamp and independently chosen thresholds. Measurements include start/end timestamps, sites/cameras, normal camera-hours, independently adjudicated false alert episode count, positive events/detections by covered/defocused/moved class, measured latency samples, pinned external annotation digest and consent/custody/blinding declarations. Signatures are base64 Ed25519 over bytes: domain prefix KW_CAMERA_FIELD_REVIEW_V1 followed by a zero byte and compact sorted canonical JSON of schema+policy+measurements.

   The verifier enforces three distinct configured trusted public keys, valid signatures, count consistency, time-order declarations, explicit minimum exposure, class-level sensitivity, operator nuisance episodes per 100 camera-hours and p95 latency. **A valid signature verifies who signed data, not whether a camera was genuinely tampered with or timestamps are independently anchored.** The strongest automated result is EVIDENCE_READY_FOR_INDEPENDENT_MANUAL_REVIEW, never field certification.

6. The independent owner makes a manual go/no-go decision with privacy/security review, site permission, camera coverage, verified custody, alert burden, incident escalation runbook and a rollback plan. Keep autonomous enforcement disabled in this branch regardless of the result.

## Emergency stop and rollback

- Stop the camera worker without deleting its durable jobs; cancel queued/running jobs through the protected officer UI.
- Remove centre-source grants and revoke the Drive OAuth grant if access is compromised. Rotate keys outside GitHub. Preserve the immutable audit and frozen source hashes.
- Block public ingress to the API if OIDC, BFF, database or S3+KMS checks fail; do not fall back to a demo login.
- Roll back to the previous approved web/API image using the hosting provider's established deployment rollback, after backing up data. Database schema rollback requires a reviewed migration; never delete forensic audit rows.
- Any insufficient field evidence, invalid signatures, missing source, low geometry confidence or incomplete decoding yields UNKNOWN/BLOCKED, not healthy or tampered.

## What is and is not finished

**Finished software:** the protected shadow workflows, private worker, data provenance, independent-label evaluator, read-only pilot preflight, signed field-review checker, tests and written operational runbook.

**Not established:** an actual approved deployment, original full-day media replay in the authorized worker, source-custody confirmation, physical field sensitivity/nuisance, and external acceptance. These can only be verified by running the released system in a real approved environment. No recurring manual chat-upload loop is required by the architecture.

## Real centre registry for protected pilot and production

Protected environments `pilot`/`production` require `KAUSHALWATCH_CENTRES_JSON` with a versioned object: `{"version":"KW_CENTRE_REGISTRY_V1","centres":[...]}`. Each centre requires exactly `centre_id`, `name`, `location`, `district`, `state`, `batch_id`, `job_role`, `trainees`, `camera_id`, `connectivity_mode`. Protected deployments reject duplicate IDs, IDs starting with `DEMO-`, malformed centre metadata and missing registries; local/demo mode retains existing test fixtures. All camera-source grants, officer access, centre listings, worker preflights and per-centre camera routes use this same provisioned registry. The registry is a privileged deployment configuration, never user input, identity claims, or a Drive manifest. Do not open live pilot ingress until actual centre owners have approved both OIDC officer grants and SHA-pinned source assignments.
