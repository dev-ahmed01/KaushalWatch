# Phase 3I — Approved-Reference Offline Camera Shadow Replay

**Status: experimental only; stacked on PR #63 (Phase 3H), which is stacked
on PR #62 (Phase 3G). Nothing is merged into production main.**

## What this does

Phase 3I makes the earlier Phase 3D frozen shadow-scene detectors usable
with a privately stored reviewed frame instead of learning an arbitrary
reference from the beginning of a surveillance video.

- The frozen spatial and persistent-scene probe source from Phase 3D is
  copied selectively into this stack. It remains excluded from live
  CameraTrust, attendance and case handling. Frozen 55% spatial cues,
  low-texture UNKNOWN status, confirmation windows and global fallback
  have not been modified to improve a benchmark result.
- The offline session can open only from a separately authenticated,
  server-resolved network-admin principal. It verifies PostgreSQL
  reference metadata and audit consistency; demands state
  REVIEWED_NOT_BOUND, an independent review ID, a matching stored image
  record, and reads/checks private S3 bytes and canonical decoded BGR
  SHA-256 before constructing the probes. It never learns a baseline
  from the video itself.
- Every observed frame reconfirms that the current reference remains
  reviewed, has the same digest/revision/review ID and matches a committed
  private artifact record. If a reference is suspended or replaced, the
  offline session closes immediately. There is no automatic recovery.
- The numeric-only full-recording evaluator checks supplied SHA-256
  hashes of BOTH the source video and headerless frame annotation CSV
  before decoding. Continuous state is preserved through the full run.
  It records annotated-normal review fraction, new review episodes per
  annotated-normal hour, true post-onset/fresh event counts, events with
  pre-existing alerts, review-delay metrics and low-texture unknowns.
  Short previews cannot masquerade as complete-recording results.
- The script emits only an aggregate JSON report after a successful
  replay; no frames, face crops, frame-by-frame labels, timestamps or
  image thumbnails are exported.
- Synthetic PostgreSQL + fake S3 and small generated-video tests
  confirm binding and revocation. The CLI is additionally restricted
  to a private staging deployment with an existing strong configured
  reviewer access token held in an environment variable (not a CLI flag).
  The command-line prototype DOES NOT accept OIDC subjects or manufacture
  a principal from a supplied user name. OIDC worker integration is a
  separate release prerequisite.

A reviewed image and a hash match are not cryptographic proof that
the capture originated from the real physical camera. Source provenance
is an explicit limitation in the report.

## Private local full-day replay workflow

This command is only meaningful on an operator-controlled staging
machine with the authorised PostgreSQL and KMS-encrypted S3 configuration
from Phase 3H and a separately reviewed reference for that EXACT
centre/camera/revision. It WILL NOT work with the old unapproved 10-second
video warmup as a stand-in for officer-approved reference images.

First pin the source hashes using a source-custody procedure. Example
on Windows PowerShell (using locally licensed recordings):

    Get-FileHash C:\Users\Admin\Desktop\MEVA\video.avi -Algorithm SHA256
    Get-FileHash C:\Users\Admin\Desktop\MEVA\annotations-1.csv -Algorithm SHA256

Prepare the manifest on the *private operator workstation*, with real
hashes and a real reviewed reference revision; do not commit it to Git:

    {
      "centre_id": "DEMO-KA-104",
      "camera_id": "LAB-CAM-01",
      "revision": 1,
      "video": "C:\\Users\\Admin\\Desktop\\MEVA\\video.avi",
      "annotations": "C:\\Users\\Admin\\Desktop\\MEVA\\annotations-1.csv",
      "video_sha256": "PLACEHOLDER_TO_REPLACE_WITH_64_LOWERCASE_HEX",
      "annotations_sha256": "PLACEHOLDER_TO_REPLACE_WITH_64_LOWERCASE_HEX"
    }

Do not use the example manifest literally. Do not pretend the UHCTD
video belongs to LAB-CAM-01: create a verified reference linked to that
actual dataset camera or run only a labeled unqualified experiment.
The centre/camera in the manifest must correspond to the physical
reference, not merely pass metadata checks.

Set protected environment variables privately (never paste the token
into this chat or put it in PowerShell history):

    KAUSHALWATCH_ENV=staging
    KAUSHALWATCH_STORAGE_BACKEND=postgres
    KAUSHALWATCH_REVIEW_AUTH_MODE=token
    KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW=shadow_artifact
    KAUSHALWATCH_PHASE3I_OFFLINE_TOKEN=<PRIVATE_STAGING_REVIEWER_TOKEN>
    KAUSHALWATCH_DATABASE_URL=<PRIVATE_STAGING_DATABASE>
    KAUSHALWATCH_CAMERA_REFERENCE_S3_BUCKET=<PRIVATE_BUCKET>
    KAUSHALWATCH_CAMERA_REFERENCE_S3_REGION=ap-south-1
    KAUSHALWATCH_CAMERA_REFERENCE_KMS_KEY_ID=<PRIVATE_KMS_ID>

In the Phase 3I repo:

    python scripts/run_phase3i_offline_reference.py \
        --manifest path/to/private_day3_manifest.json \
        --out path/to/private_day3_replay.json \
        --sample-seconds 1

Preview first, using a DIFFERENT output path, with
--preview-seconds 60. The script never overwrites previous results.

Compare against the old Phase 3D continuous-development benchmarks
only on matching labels, source videos, cadence and camera conditions.
Original Phase 3D figures:
- Day 3 annotated-normal review fraction: 0.410366;
  new normal review episodes per normal hour: 27.196730;
  fresh moved events: 15/24.
- Day 4 annotated-normal review fraction: 0.070102;
  new normal review episodes per normal hour: 14.382874;
  fresh moved events: 22/24.

Those values are baselines, NOT qualification targets. The new code
has not been run on those local videos and no improvement is claimed.
Unlike the old full-day script, this new run requires a separately
reviewed reference pixel frame. Differences can stem from that changed
reference selection, not a genuine detector improvement.

## Evidence and safety boundaries

- Day 3 and Day 4 have already been repeatedly inspected, hence are
  DEVELOPMENT, not untouched independent held-out data.
- A review cue is neither proof of camera movement nor intentional
  tampering; camera non-alert is not proof that activities are visible.
- A private S3 reference and an officer attestation do NOT establish
  trusted camera-device provenance or a digital signature.
- The offline analysis uses no operational endpoints. It cannot start
  live processing, auto-reset cameras, sanction providers, alter
  attendance, or make compliance determinations.
- New reference approval, reference retirement/recovery, and reviewer
  role changes must be handled and audited outside the running replay.
- PostgreSQL/role grants and per-frame full audit verification add
  overhead: runtime performance is not qualified.
- Never process CCTV recordings without institutional authority,
  local permissions, privacy procedures and retention controls.

Remaining gates: physical source provenance and authenticated camera
identity, independently accepted reference enrollment, secure worker
credentials and OIDC authorization, full-day preview/replay on both
recordings, acceptable false-warning burden, and independently blinded
multi-camera held-out qualification.
