# Phase 3H — Private Camera Reference Images (Staging Shadow)

**Draft PR #63, stacked onto draft Phase 3G PR #62. Not merged to main.**

This adds private reference-image handling to the authenticated officer
workflow. It does NOT integrate the live camera detector, reset baselines
or affect compliance and attendance conclusions.

## Architecture

- Migration v4 adds centre/camera/revision-scoped artifact metadata:
  private S3 object key, normalized PNG SHA-256, canonical BGR pixel
  SHA-256, byte size, dimensions and uploading officer.
  No image bytes are stored in PostgreSQL.
- In STAGING shadow_artifact mode, a centre reviewer may propose and upload
  a static frame in one request (propose-image) or attach one to an already
  pending proposal (attach).
- Image request bodies are streamed and limited to 2 MiB. Only PNG/JPEG,
  preflight dimensions, canonical BGR pixels and metadata-stripped PNGs.
  Raw-pixel hash includes dtype, shape and pixel bytes; it differs from
  the SHA-256 of an original JPEG file.
- The normalized PNG is written to a separate private S3 bucket using
  KMS encryption, checksum, conditional create and server-generated keys.
- On independent review the backend retrieves the stored image, checks
  encoded SHA-256, dimensions, and pixel SHA-256 against the proposal.
  Missing or corrupted frames fail closed. Human review still results
  in REVIEWED_NOT_BOUND, never an active operational camera baseline.
- The private preview endpoint is centre/role protected, no-store,
  proxied through existing officer HttpOnly browser sessions and CSRF BFF.
  Centre viewers are prohibited from retrieving the private frames.

## Explicit staging-only configuration

Server:
  KAUSHALWATCH_ENV=staging
  KAUSHALWATCH_STORAGE_BACKEND=postgres
  KAUSHALWATCH_REVIEW_AUTH_MODE=oidc
  KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW=shadow_artifact
  KAUSHALWATCH_CAMERA_REFERENCE_S3_BUCKET=your-private-reference-bucket
  KAUSHALWATCH_CAMERA_REFERENCE_S3_REGION=ap-south-1
  KAUSHALWATCH_CAMERA_REFERENCE_KMS_KEY_ID=alias/your-camera-reference-key

Apply schema migration with a separately authorized DB migration account:
  python scripts/migrate_postgres.py --apply
  python scripts/migrate_postgres.py --check

Web build, staging only:
  NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true
  NEXT_PUBLIC_KAUSHALWATCH_CAMERA_REFERENCE_REVIEW=true
  NEXT_PUBLIC_KAUSHALWATCH_CAMERA_REFERENCE_IMAGE_UPLOAD=true

Rebuild web after changing build flags. Never place AWS credentials,
database secrets or access tokens in NEXT_PUBLIC variables.

Use a private KMS-encrypted bucket with bucket-level public access
block, TLS enforcement, least-privilege IAM, access logging and a
retention/deletion policy appropriate to the camera source.

## Limitations and safety gates

A matching hash proves exact stored bytes, NOT that the image is
actually sourced from the physical assigned camera. Capture IDs and
review IDs are officer attestations, not independently verified source
custody or device signatures. A successful review NEVER modifies
attendance or compliance and NEVER declares tampering.

Private S3 writes and PostgreSQL metadata are not one distributed
transaction. An S3 image may be orphaned if indexing fails, in which
case officer retrieval remains impossible without the exact DB row.
A protected orphan-reconciliation and retention process is required
before any production-grade deployment.

If one-step proposal creates a pending record but image storage fails,
the same centre reviewer can retry the attach endpoint with the
original image. The independent reviewer cannot complete the review
in artifact mode until the private bytes can be retrieved and verified.

Application-level hash-chain/trigger checks are not immutable against
a privileged DB owner. Do not treat the audit as externally anchored
without separate privileged role controls and independent logging.

The real detector on production main is NOT bound to these images.
Older experimental camera detection in PR #61 remains separate and
is not merged here; sample-selected successes do not offset the
known excessive full-day development warning burden.

The tests use synthetic images, fake S3 calls and isolated PostgreSQL.
This does not constitute actual cloud IAM/retention acceptance,
physical source verification, independently blinded site testing
or detector release qualification.
