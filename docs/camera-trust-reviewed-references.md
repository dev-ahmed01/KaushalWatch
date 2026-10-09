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


## Phase 7 survey review and movement forensics

Day 3 Camera A, stratified development survey at commit 3611609:
- 4/4 sampled covered events produced new suspected-tamper alerts.
  1,423/1,440 positive samples were flagged (98.82%).
- Defocus: 2/4 produced brief tamper alerts, but 1,305/1,440
  frames were correctly classified as **unusable evidence by the heuristic**.
  A blurry camera should not automatically imply deliberate tampering.
- Movement: 0/4 selected events produced new integrity alerts.
  1,065/1,440 event samples were unusable, commonly because of
  poor night visibility. One selected moved event had extent
  parameter 0.0: verify before treating it as physical displacement.
- 181 suspected-tamper samples occurred within a single 90-second
  normal control (control #8, starting around 15:00 into recording).
  That window accounted for all 181 normal-control alerts. Across
  all 12 controls and all event contexts it is 181/3,960 healthy
  samples (4.57%), **not** an estimated full-day false alarm rate.
- All selections reset temporal state, so neither event frequency
  nor production latency is established.

New nonmutating diagnosis:
  python scripts/diagnose_uhctd_movement.py \
    --video C:/Users/Admin/Desktop/MEVA/video.avi \
    --annotations C:/Users/Admin/Desktop/MEVA/annotations-1.csv \
    --out C:/Users/Admin/Desktop/MEVA/phase7_movement_diagnostics

It replays the four selected moved events and normal control #8,
recording phase-correlation translation response, estimated shift,
reference correlation, blur/luminance ratios, each movement eligibility
gate, and actual integrity/visibility decisions. It compares the
recording's first-frame reference against a window-local reference
**only diagnostically**. It exports CSV/JSON, not licensed media.

A previously uploaded strong-moved onset clip shows coherent phase
translation (roughly 36 normalized pixels in its displaced state)
with registration response around 0.35, while a healthy static control
showed almost zero displacement. That alone is not justification to
remove all eligibility checks: the selected milder moved events may
behave differently, and control #8 remains unexplained.

Before changing the production movement rule, inspect this diagnostic.
Do not merge the draft or change the frozen v1 vision profile.

## Phase 8 — movement-gate diagnostics from Day 3 (not full-day validation)

Five spans sampled at 3 FPS:
- Four moved spans, 360 annotated post-onset frames each, produced **no**
  phase-correlation registration pass and no integrity alert.
- Original-reference phase-correlation displacement medians were
  53.2, 62.7, 74.6, and 68.9 normalized pixels. These apparent
  offsets are **unreliable** because all geometric responses were
  below the existing 0.25 confidence floor.
- Healthy normal control #8 also showed median apparent displacement
  54.9 pixels against the original historical reference, but only
  0.115 pixels against a fresh local reference. It generated 181
  suspected-obstruction flags. This is a distinct stale-reference
  false alarm, not evidence of camera movement.
- Moved events 2 through 4 were frequently low detail before and
  after onset, so apparent motion from phase correlation alone is not
  credible. The event with extent 0.0 needs visual confirmation.

A diagnostic-only **ORB + RANSAC partial-affine landmark estimator**
has now been added in camera_feature_geometry.py. It uses CLAHE and
distributed matched background landmarks and returns a three-way
interpretation: confident shifted, confident not shifted, or unknown
when evidence is insufficient. It does not substitute large
low-response phase offsets for physical motion.

In a separate development replay of the supplied strong moved clip
(680x510, 3 FPS), a clean frame versus frame 45 produced approx
61 normalized pixels displacement with 45 inlier ORB matches across
6 of 9 spatial regions; pre-onset frame 9 had only 0.13 pixels
displacement. The partial-cover clip did not produce a false
confident shift. These probes and synthetic unit tests are only
candidate evidence, not representative validation.

scripts/diagnose_uhctd_movement.py now emits sparse
original_landmark_* and local_landmark_* measurements every ~2 seconds
for the same four selected moved events and normal control #8.
It writes movement_gate_summary.json and movement_gate_samples.csv;
no protected CCTV images are exported or committed.

**Do not promote ORB results into the production integrity decision
until the new movement-gate diagnostics show adequate genuine
displacement evidence and control #8 false-alarm rejection.**
Do not automatically adapt the reference using a suspicious camera.
The frozen fixed-camera-v1 profile remains unchanged.

## Phase 9 updated landmark-survey review and transform safety

Original Day 3 move-event landmark diagnostic at commit 458b5e9:
- After annotated onset, the four tested moved-event intervals yielded
  original-reference confident matches **0/60 each**.
- Local (pre-event window) reference gave 1/60 for moved event 1 and
  0/60 for moved events 2 through 4.
- The sole event 1 'confident' match was a degenerate affine estimate:
  scale 0.0003, corresponding to geometrically collapsed landmarks.
  This is NOT valid evidence of a physical camera move.
- Healthy normal control #8 matched its local reference confidently
  **45/45 checks, with 0 shifts**; it still generated 181/270 false
  *regional obstruction* alerts against the original stale baseline.
- Later moved intervals have low texture, poor landmark distribution,
  and frequently poor visual quality; mere phase offset or low-match
  affine transformations must NEVER be interpreted as a shifted camera.

Safety fix (still diagnostic only):
camera_feature_geometry.landmark_displacement now rejects implausible
transform scale (outside 0.70–1.40), excessive rotation (>30 degrees),
and insufficient *destination-side* spatial landmark coverage. It
reports 'IMPLAUSIBLE_AFFINE_TRANSFORM' or insufficient landmarks instead
of a confident shift. Synthetic tests explicitly reject an affine
scale of 0.0003 and collapsed destination geometry. This code does NOT
change the production Camera Trust movement decision.

Next evidence needed: human review the four different moved-event
appearance sequences (including the event with extent parameter 0.0)
and the flagged normal control #8. The source data license remains in
force. A local-only selection tool is available at:

    python scripts/export_uhctd_movement_review.py \
      --video C:/Users/Admin/Desktop/MEVA/video.avi \
      --annotations C:/Users/Admin/Desktop/MEVA/annotations-1.csv \
      --out C:/Users/Admin/Desktop/MEVA/phase9_manual_review

The tool exports five contact sheets, each containing six source-video
frames with time and onset offsets, plus a JSON manifest. It never
automatically enrolls these images as references or commits video.
The observations are diagnostic, NOT held-out or production validation.

Until independent full-day testing supports it, keep PR #54 draft,
the frozen fixed-camera-v1 profile untouched, and the officer-review
requirement in place.
