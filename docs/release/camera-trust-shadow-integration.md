# Camera Trust — integrated shadow operations (October 18, 2026)

Status: **software implementation pending full CI/staging acceptance; NOT PRODUCTION-QUALIFIED**.

## Ownership boundary

The main FastAPI application now includes centre-scoped officer routes at
`/api/centres/{centre_id}/camera-trust`; the existing protected officer
middleware and Next.js same-origin BFF control access. A new tab in the
centre UI hosts camera enrollment, job orchestration, reference proposals,
independent approvals and observation review. All writes require officer
authorization. The observer never modifies `kw_cases`, attendance,
centre sanctions, or existing evidence decisions.

The v5.1 workstation in `camera_trust_workstation/` remains the pinned
historical research baseline and independent read-only comparison surface.
Its private evidence is **not** in public GitHub.

## Provisioning (separate one-time authorization, not per-video uploads)

1. Run the existing PostgreSQL migration tool:
   `KAUSHALWATCH_DATABASE_URL=... python scripts/migrate_postgres.py --apply`
   then `--check`. This adds version 3 tables and immutable audit storage.
2. Put `drive-sources.json` **outside the repository** with existing
   `KWTRUST_DRIVE_ASSETS_V1` schema, approved filenames, Drive IDs and pinned
   SHA-256. Every source exposed for enrollment MUST have a SHA-256 pin.
   Set `KAUSHALWATCH_CAMERA_DRIVE_MANIFEST=/private/.../drive-sources.json`
   on the API and worker. Do not commit/echo its contents.
3. Set `KAUSHALWATCH_STORAGE_BACKEND=postgres` and use the existing protected
   OIDC deployment settings. Configure the private evidence store as required
   by KaushalWatch's existing security policy.
4. Run the worker separately from the web process:
   `python scripts/run_camera_trust_worker.py --poll-seconds 15`.
   Set `KAUSHALWATCH_CAMERA_MEDIA_DIR` outside public paths (read/write only
   by the worker). `KAUSHALWATCH_CAMERA_REFERENCE_DIR` holds approved
   reference PNG files named `<sha256>.png`, with matching hash; never
   auto-generate a reference from a suspicious stream. Configure Google
   Application Default Credentials or `KAUSHALWATCH_CAMERA_DRIVE_TOKEN` for
   previously authorized OAuth tokens, and install
   `camera_trust_workstation/requirements-drive.txt`. First OAuth consent is
   interactive and must be completed in an authorized environment once.
5. Keep `/private` and `.private/` excluded from Git, web serving and CI
   artifacts. The private worker uses authenticated chunked and resumable
   Drive byte ranges; this is distinct from the chat connector's 256 MiB limit.

## Decision policy and release gate

- Camera physical status: **UNKNOWN** until independent physical camera
  custody and field adjudication prove otherwise.
- A missing SHA pin, missing reference, poor geometry, failed frame seek,
  bad metadata, or source mismatch results in failure/UNKNOWN, not a healthy
  score.
- Each source job takes a bounded *sparse* series of frames (12–180). The
  summary records sample positions, failures, reference and motion uncertainty.
  This is **not** complete AVI decoding or a field false-alarm study.
- Analysis outputs are append-only at job level. Human review decisions are
  single-shot and audited. Camera references require a proposer and different
  approver; existing approved references cannot be silently overwritten.
- An observation remains separate from enforcement-grade compliance evidence.
  The API deliberately provides **no** field-qualification or automatic
  incident control endpoint.

## Smoke/acceptance coverage

CI must check Python compilation, legacy tests, v3 migration idempotence,
synthetic frame analysis, route authorization, and frontend build. A real
worker replay requires approved OAuth/ADC, the private pinned manifest and
the original videos on a worker reachable by Google Drive. Browser CI
uses synthetic records; it cannot certify Windows PowerShell execution.

## Known release boundaries

The Day3/Day4 development clips are not an independent blinded physical
validation cohort. Movement and gentle/partial obstruction weaknesses remain.
For field qualification, collect locked independent camera/site custodial
references, true normal exposure, night/IR/lighting conditions, actual
tampering cases, blinded decisions, pre-frozen thresholds, verified operator
alert burden and latency. Never promote this shadow pipeline merely because
the build passes.

## Centre-private source grants (required for safe enrollment)

A pinned Drive manifest verifies a file, but alone does not prove it belongs to
a particular training centre. Configure a private environment value
`KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON`, for example:

```json
{"DEMO-KA-104":["approved-camera-a.avi"],
 "DEMO-KA-112":["approved-camera-b.avi"]}
```

The aliases must already exist in the private manifest with a SHA-256 pin and
supported video suffix. Every alias belongs to **at most one centre**. Missing,
malformed, duplicated, or unpinned assignments fail closed. The centre UI
shows only its approved aliases; it never renders Drive IDs or source hashes.
Workers independently enforce grants before downloading, preventing a
database job from bypassing API-level source ownership checks. Adjust this
mapping through privileged deployment secrets, not a public GitHub commit.

## Automated private worker deployment and CI runtime

`Dockerfile.camera-trust-worker` and `compose.camera-trust-worker.yaml`
supply an optional rootless, read-only worker runtime with private read-only
source manifest, reference directory and credentials, and a writable
restricted media cache. The worker is a **separate background service only
when deployed**, never a ChatGPT background task. A startup preflight checks
schema version, centre grants, and Google credentials before claiming jobs.
Run `python scripts/run_camera_trust_worker.py --preflight` for a
non-networking schema/grant check without consuming analysis attempts.

CI synthetic-video tests decode real MJPG frames, check accurate sparse
positions and abstention, and exercise the durable enqueue→claim→fake
download→hash validation→analysis→persist lifecycle. This does not replace
independent original-source or physical-camera qualification.

## Running-job cancellation

An authorized officer can cancel either a queued or running analysis job.
A running worker discovers cancellation through lease heartbeat, and cannot
persist a stale observation after cancellation. Reanalysis requires a fresh
idempotency key and an explicit officer action.


## Phase 7: independent validation and bounded software roadmap

The project has nine defined phases, and Phase 7 adds a strict offline
evaluation path without any recurring ChatGPT video/report uploads.
Read [Phase 7 validation and 9-phase roadmap](CAMERA_TRUST_PHASE_7_VALIDATION.md)
before using the holdout exporter/evaluator. The exporter reads authorized
PostgreSQL observations by frozen job IDs, strips unexpected fields, and
creates a label-SHA-bound numeric snapshot. The evaluator reports sparse
clip-level numerical candidate statistics, **not** physical camera accuracy,
and always blocks autonomous field enforcement. Real external adjudication,
deployment credentials and physically verified pilot evidence remain outside
CI's synthetic tests.

## Phase 2 reliability: generation-fenced worker leases

The Camera Trust shadow worker's 45-minute PostgreSQL lease is now fenced by
the **incremented claim attempt number**, not merely a reused process worker
ID. Claim returns the persisted attempt generation. Heartbeat, completion and
failure paths all require the same camera/job/worker/generation and a still
active lease. Any expired lease, cancellation, or reclaimed generation returns
a non-authorizing result without extending the old lease, inserting a
Camera Trust observation, or replacing a newer worker's status.

A delayed worker may finish decoding after its lease expires; the database
refuses to persist that result, and another claim may retry the bounded job
(at most three attempts). This prevents a restarted process that reuses a
worker ID from causing stale observations. The isolated PostgreSQL CI tests
explicitly simulate expiration and reclaim with the **same** worker ID,
including duplicate completion and stale failure attempts.

These are software-only concurrency/expiry checks with synthetic jobs. They
do not claim a live Drive worker, source-custody validation, physical camera
accuracy, an approved pilot or autonomous enforcement.
