# Camera Trust: reviewed references and visibility separation

**Status:** candidate branch only; not a validated anti-tampering device.
Source: Phase 5 of UHCTD Camera Trust reliability evaluation.
Do **not** commit actual CCTV reference images or populated manifests.

## States (frame-level, observed evidence)

- USABLE: no sustained issue currently detected. This is **not**
  proof the video is authenticated, real-time, or unaltered.
- DEGRADED_VISIBILITY: image is too dark, intrinsically low-detail, or
  excessively defocused for reliable downstream attendance/activity
  inference. The detector suspends visual conclusions but does not
  accuse anyone of obstructing or moving the camera.
- SUSPECTED_TAMPERING: candidate obstruction, coherent scene
  displacement, or possible frozen/replayed feed. Only an officer
  can determine the actual cause. No automatic punitive action.

API-compatible CameraTrust fields are retained, with added
camera_status, quality_status, integrity_status, reference_status and
reference_id. The scores and labels are **heuristic**, uncalibrated and
camera-dependent.

For downstream run-level review, if the trusted-frame ratio is below
the existing minimum, predominantly degraded frames create a
camera_visibility case rather than camera_integrity; visual attendance
and activity conclusions remain suspended. Cases retain anonymized
evidence. Other API consumers should inspect case_type.

## Manually reviewed reference manifest (v1)

The current full-video processing code accepts two **optional** keyword
arguments on either VideoCompliancePipeline.run or
PracticalActivityPipeline.run:

    reviewed_reference_manifest="C:/secure/CAM1/references.json",
    reviewed_reference_mode="night",

The mode is selected explicitly by the caller/operator using independent
camera metadata or an approved schedule. **Never choose the mode from
pixels that might already be obstructed.** If the camera mode changes
during a long recording, start a new analysis segment with a known,
approved reference. No automatic baseline promotion, enrollment,
switching or reference adaptation occurs.

Example manifest stored outside Git (replace paths and SHA values with
ones recorded after human review):

    {
      "version": 1,
      "camera_id": "CAM1",
      "references": [
        {
          "id": "CAM1-DAY-20261009",
          "mode": "day",
          "image_path": "day_reference.png",
          "approved": true,
          "reviewed_by": "authorized-camera-operator",
          "reviewed_at": "2026-10-09",
          "sha256": "<sha256 hex of image bytes>"
        },
        {
          "id": "CAM1-NIGHT-20261009",
          "mode": "night",
          "image_path": "night_reference.png",
          "approved": true,
          "reviewed_by": "authorized-camera-operator",
          "reviewed_at": "2026-10-09",
          "sha256": "<sha256 hex of image bytes>"
        }
      ]
    }

SHA verification detects an unexpected image-file change but does NOT
authenticate an officer identity or prove the reference is truly normal.
Images must be independently reviewed for correct scene geometry,
privacy and equipment state before approval. Keep them local, permissioned,
and out of the repository. Reference resolution must exactly match the
video feed. Invalid references fail closed with ValueError.

PowerShell hash generation:

    (Get-FileHash "C:\secure\CAM1\night_reference.png" -Algorithm SHA256).Hash.ToLower()

## Demonstrated vs unproven

UHCTD Day 4 Camera B showed benign normal-night scene reference drift.
A development-only low-light guard was previously added to the candidate.
This phase separates poor visibility from inferred integrity incidents
and supports selecting operator-reviewed modes. It does NOT establish
that the camera is usable at night or that dim obstructions are caught.

Evaluation must now report two *separate* outcomes:
1. Whether tampering was suspected (not evidence of malicious intent).
2. Whether any visual inference was unusable (including degraded quality).

For defocus, declaring the footage unusable may be correct even with no
tampering allegation. This distinction must be used in any reported
per-class recall numbers. Earlier full-day results were for previous
candidate revisions and are not v5 accuracy claims.

### Required before promotion

- Synthetic dark obstruction/translucent screen negative-case tests.
- Full-day diagnostic comparison on previously used Day 4 (not held-out),
  with per-hour visibility and tamper reasons.
- New *untouched* independent recording, with licensing respected,
  for promotion-level metrics.
- Integration/UI review for the visibility case_type and reference state.
- No changing the frozen fixed-camera-v1 profile without explicit review.
