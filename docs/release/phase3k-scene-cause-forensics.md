# Phase 3K — Explain Scene Differences Without Suppressing Evidence

**Status: experimental offline forensic diagnostics.** This branch is stacked
on the Phase 3J draft (#65), which depends on Phase 3I (#64), Phase 3H (#63)
and Phase 3G (#62). No component is imported by released Camera Trust,
attendance or compliance services.

## Why this is needed

The old UHCTD development replay showed that fixed-camera scene
comparisons could remain triggered through substantial annotated-normal
periods. Manual forensic review suggested a mixture of nuisance
foreground activity, lighting/IR transitions, incident carryover and
genuinely degraded visibility. Annotation-normal is NOT an independent
guarantee of healthy or usable footage.

Historic, unchanged development numbers:

| Measure | Day 3 | Day 4 |
| --- | ---: | ---: |
| Annotated-normal review fraction | 0.410366 | 0.070102 |
| New review episodes per annotated-normal hour | 27.196730 | 14.382874 |
| Fresh movement alerts | 15/24 | 22/24 |

## Implemented, diagnostic-only

The new module camera_scene_cause_shadow.py observes a private fixed
approved reference from the offline Phase 3I session and a decoded
video frame. It returns *unconfirmed cause-compatible measurements*:

1. Brightness changes, contrast ratio, tile correlation and sparse
   textured-tile change/quadrant coverage. High overall brightness
   shift with preserved local correlation can be PHOTOMETRIC_SHIFT_COMPATIBLE.
2. Changed tiles concentrated in <=2 quadrants can be
   LOCAL_FOREGROUND_OR_OCCLUSION_COMPATIBLE. This is NOT proof that
   the camera is stationary or that foreground activity is harmless.
3. Image translation measured by spatial phase correlation on a full
   192x144 reduced frame plus four separate quadrants. Two frozen
   exploratory/conservative consensus presets compare coherence,
   phase confidence and global pixel displacement. A coherent shift
   means COHERENT_IMAGE_TRANSLATION_COMPATIBLE, not confirmed tampering.
4. Low-texture evidence remains STRUCTURAL_EVIDENCE_INSUFFICIENT,
   irrespective of other possible causes.
5. Multiple compatible hypotheses can coexist. No hypothesis chooses
   a reset, dismisses a review cue, or verifies usability.

The full-recording evaluator records these forensic measurements every
fifth *sampled* observation, uniformly across ALL annotated classes
rather than preferentially inspecting only known events or positive
detector warnings. This intentionally limits overhead and avoids
using ground-truth class to condition forensic inference.

The report is aggregated only: numbers of scene hypotheses by class,
counts observed during raw detector review, and the conservative/
exploratory phase-consensus support. It retains the ORIGINAL raw
scene review fraction, onset event scoring, UNKNOWN evidence counts and
notification policy comparison. No frame crops, images or per-person
data are emitted. The fixed reference remains immutable throughout.

No forensic classifier is trained, calibrated, declared accurate, or
selected for operation. Presence of a phase-correlation shift is
NOT sufficient proof that the physical camera moved.

## Reproducible evaluation

The existing Phase 3I CLI produces Phase 3K numerical diagnostics in
its JSON report automatically when the approved-reference offline
session is used:

    python scripts/run_phase3i_offline_reference.py \
      --manifest path/to/private_camera_manifest.json \
      --out path/to/private_phase3k_replay.json \
      --sample-seconds 1

Requires a separately reviewed reference from the SAME physical
camera, provisioned private staging identity, access-controlled S3
artifact and PostgreSQL metadata, and the pinned video/annotation
hashes. It will not proceed by faking a review of the demo centre or
learning a video-first-frame reference. No real Day 3/Day 4 new
numbers can be asserted until the local operator runs authorised
full recordings and reports numeric outputs.

Synthetic tests:

    python -m pytest \
      backend/tests/test_camera_scene_cause_shadow.py \
      backend/tests/test_camera_offline_reference_benchmark.py -q

## Acceptance gates still outstanding

- Inspect candidate/normal false-review footage under independent,
  appropriately consented review to distinguish physical movement,
  weather, IR, people, scene obstruction and maintenance.
- Evaluate a genuine, provenance-correct approved reference across the
  same camera's full recorded day; track false positive burden AND
  preserved post-event sensitivity.
- Pre-register any calibrated decision policy BEFORE new independent,
  blinded site/camera holdout. Day 3 and Day 4 are development footage.
- Keep evidence quality, camera scene review and reference governance
  separate; do not equate a hypothesis with recovered integrity.
- Any eventual operational use needs appropriate source permissions,
  device identity and chain-of-custody controls, authenticated
  officers and explicit human incident/recovery review.

Status remains NOT PRODUCTION QUALIFIED.
