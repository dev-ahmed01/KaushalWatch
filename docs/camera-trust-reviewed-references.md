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


## Phase 6: Partial edge obstruction candidate (development only)

Inspecting UHCTD Day 3 gentle-onset and gentle-recovery clips showed a
**fixed-pattern rectangular overlay at the upper-left of the camera view**
while the grass, path and pedestrians remained visible. The earlier
whole-frame engine missed the first covered-camera event entirely.

Added a conservative 8x6 regional cue:
- Downsample to 192x144 grayscale and compensate global additive exposure
  differences using the median pixel shift.
- Require at least six connected tiles with a large change versus the
  initial scene, low temporal movement, and 1.5 seconds persistence.
- At least 26/48 tiles must still resemble the original background, so
  widespread lighting regime changes are not called partial obstruction.
- For now the cluster must occupy multiple rows and columns and touch a
  frame edge. Interior-only partial covers are not handled by this cue.

Local prototype replay of supplied clips using the original clean
reference: first regional alert at cropped onset frame 43 (cover appears
at frame 36), approximately 2.3 seconds later. No alerts in the clean
pre-onset period. Recovery was no longer flagged once the overlay cleared.
This is NOT independent or full application-level validation. The original
footage is not committed. Synthetic tests cover partial patterned covers,
foreground motion, uniform lighting shifts, night scenes and removal.

Risks: stationary edge objects may trigger, full or similar-texture
obstructions need different evidence, and an initially obstructed reference
could mistake restoration for new tampering. This is only a **suspected**
integrity signal requiring human review. Do not merge or promote before
a different untouched camera/day dataset confirms low false-alarm rates
and coverage of strong and mild obstructions.

## Phase 7 — stratified event survey (development only)

Use the new evaluator at scripts/survey_uhctd_events.py before another
full 24-hour evaluation. It selects the first distinct annotation
extent settings for each tamper class (4 covered, 4 defocused, 4 moved
by default), plus 12 healthy windows spread over the day. Each event
includes 20 seconds of verified normal context; the default positive
interval is the first 120 seconds after onset. Windows reset temporal
state while preserving the original first-frame reference.

Example Windows PowerShell:

    python scripts/survey_uhctd_events.py --video "C:/Users/Admin/Desktop/MEVA/video.avi" --annotations "C:/Users/Admin/Desktop/MEVA/annotations-1.csv" --out "C:/Users/Admin/Desktop/MEVA/phase7_survey"

Outputs:
- sampled_event_summary.json: per-class suspicion and visual unusability
  rates, normal-window false alert rates, model revision, annotation SHA.
- sampled_event_results.csv: one row per selected event or normal interval
  with event onset, annotation parameters, independent alert rising edge,
  delay, and evidence-quality failures.

Caveats: This is not continuous 24-hour state reconstruction. Selecting
particular extents or segments means results do not represent event
frequency, camera-wide prevalence, precision or false alarms per full
normal hour. Entire 5-minute events may continue beyond the 120-second
sample. The annotation extent is a dataset control parameter, not
necessarily a literal percent of the field of view. Day 3 and Day 4
are both development/diagnostic inputs, NOT untouched promotion tests.
