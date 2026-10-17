# Phase 3G — Protected Camera Reference Review (Experimental)

Status: draft PR #62, staging only, disabled by default.

This branch starts from current protected main, not the older camera
experiment. Existing HttpOnly browser sessions, same-origin CSRF BFF,
server-derived centre grants and OIDC/staging officer access remain
the security boundary.

## Included

- PostgreSQL schema version 3 for current reference metadata and
  hash-chained, append-only application events.
- Metadata proposal by an authenticated centre_reviewer assigned to
  the centre, and separate attestation by a network_admin.
- Statuses: UNENROLLED, PENDING_REVIEW, REVIEWED_NOT_BOUND, SUSPENDED.
  Stale revisions, invalid roles, cross-centre access and unsanctioned
  replacement are rejected.
- Protected backend endpoints:
  - GET /api/centres/{centre_id}/camera-reference
  - POST /api/centres/{centre_id}/camera-reference/propose
  - POST /api/centres/{centre_id}/camera-reference/review
  - POST /api/centres/{centre_id}/camera-reference/suspend
- Centre-level officer screen using the existing cookie-authenticated
  Next.js BFF and CSRF, hidden unless its own build-time switch is on.
- Synthetic route tests, real middleware token tests, disposable
  PostgreSQL approval/audit tests, frontend build and E2E checks.

## Important limitations

A recorded review is METADATA ONLY. It does not independently
authenticate camera image pixels, verify that the referenced review
ticket exists or certify source provenance. REVIEWED_NOT_BOUND NEVER
activates the camera's structural comparator, enrolls a reference
or changes attendance or compliance outcomes.

No CCTV upload, frame download, raw faces or videos are introduced.
Do not paste sensitive footage into reference metadata fields.

Phase 3D shadow detection remains isolated on its prior PR (#61).
The known full-day normal warning burdens are NOT fixed here:
Day 3 41.04%, Day 4 7.01%. Those remain a release blocker.

Postgres triggers and a SHA-256 event chain provide tamper evidence
against normal application edits, but privileged database owners can
rewrite or remove them. Independent audit anchoring is still required.

## Explicit staging-only enablement

1. Set the backend to staging and use protected officer token/OIDC
   authentication with provisioned, server-side centre roles.
2. Use PostgreSQL persistence, not demo JSON. Run migration explicitly
   with a migration-scoped credential:
   python scripts/migrate_postgres.py --apply
   python scripts/migrate_postgres.py --check
3. Backend opt-in: KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW=shadow
4. Next.js build-time opt-ins:
   NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true
   NEXT_PUBLIC_KAUSHALWATCH_CAMERA_REFERENCE_REVIEW=true
   Rebuild web after changing public build-time flags.
5. Open a centre and the Camera reference tab. A centre reviewer may
   submit an opaque fingerprint and source IDs; a DIFFERENT
   network administrator identity may record the metadata review.
6. The reviewed status remains REVIEWED_NOT_BOUND. Do not claim an
   independently qualified operational camera baseline.

The API rejects staging without the protected identity and PostgreSQL
requirements, and rejects all production, pilot and demo environments.

## Still required before any operational release

- Protected reference pixel/feature store and exact verified binding.
- Durable identity grants and independently documented human review.
- Externally anchored audit, DB role separation and retention policy.
- Recovery after genuine camera incidents, without auto baseline resets.
- Continuous false-review reduction and untouched blind multicamera
  qualification, including evidence-usability outcomes.

No changes from Phase 3G have been merged into production main.
