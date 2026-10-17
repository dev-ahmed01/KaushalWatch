# Phase 3O — Paired Event-Local Visibility Diagnostics

**Experimental / OFFLINE / NOT QUALIFIED / No production changes.**

Stacked on Phase 3N draft PR #69. No changes to the scene detector,
raw review cues, officer notifications, reference selection, incident
recovery, attendance or production main.

## Grounding: completed Phase 3N numerical analysis

18 October 2026 Day3/Day4 targeted report: 216 numerical observations per
day, including all 24 defocus events, 12 alternate moved-camera events and
six time positions per event. Earlier Phase 3N validated local source video
hashes and reused the Phase 3M frozen unapproved reference.

| Metric 30 seconds after annotation onset | Day 3 | Day 4 | Total |
| --- | ---: | ---: | ---: |
| Defocus events sampled | 24 | 24 | 48 |
| SHARPNESS_LOSS_COMPATIBLE | 9 | 12 | 21 |
| ILLUMINATION_CONFOUNDED | 13 | 12 | 25 |
| NO_SHARPNESS_LOSS_SIGNAL | 2 | 0 | 2 |
| Paired sharpness <=0.5, defocus | 24/24 | 24/24 | 48/48 |
| Paired sharpness <=0.5, moved controls | 2/12 | 0/12 | 2/24 |

At the pre-event anchor, the defocus cohorts were already
ILLUMINATION_CONFOUNDED in 13/24 Day3 and 12/24 Day4 cases. Therefore an
event-local transition (instead of only one first-day frozen reference)
merits research. A fixed-reference relative metric divided by the same
metric 30 seconds before onset cancels its common reference factor
algebraically; that does NOT prove either frame healthy or physically
trustworthy.

### Three descriptive sensitivity checks (same already inspected data)

| Paired sharpness ratio cutoff | Defocus at +30s | Moved controls at +30s |
| --- | ---: | ---: |
| <=0.35 | 48/48 | 1/24 |
| <=0.50 | 48/48 | 2/24 |
| <=0.65 | 48/48 | 3/24 |

These cutoffs are *retrospective exploratory summaries*, neither trained
nor preregistered. They are NOT production thresholds or estimates of
precision/recall. Moved-camera contrast samples do not represent all
normal hours. Separately, edge-fraction decline to <=0.50 at +30s was
43/48 defocus events and 0/24 moved controls in this set.

## Implemented

- scripts/analyze_phase3o_event_transitions.py: pure-Python numeric
  source-only CLI, no OpenCV or footage required; per-event, per-day and
  pooled sharpness, edge and contrast ratios relative to 30s pre-event.
- Requires an explicitly unqualified completed Phase 3N report, both days,
  all six stages per selected event, finite numeric ratios and consistent
  baseline any/fresh scene-review status.
- Abstains where pre-event annotation is not normal, compared annotation
  mismatches event phase, or pre-event denominator is near zero.
- Reports defocus and moved-camera contrast separately; no automatic alert
  decisions, scene-review suppression, re-enrollment or recovery claims.
- backend/tests/test_camera_phase3o_event_transitions.py includes synthetic
  unit/CLI tests for data validation, abstention and trust boundaries.

### Offline reproduction

Run from Phase 3O branch checkout with the existing JSON, NOT source videos:

    python scripts/analyze_phase3o_event_transitions.py --input "quality-20261018-024132.json" --out "phase3o-paired-transitions.json"

Input is never overwritten; output contains only numeric derived evidence
and annotations/event-frame indices, never still images or video. Keep
local reports with the user's private research files; do not commit them.

## Scientific and release limitations

- Event starts and pre-event anchors were chosen using retrospective
  annotations. An operational camera has NO knowledge of these labels.
- Annotated-normal does not imply an independently verified healthy scene.
- All events came from previously repeatedly inspected DEVELOPMENT sources;
  NO independent held-out source, blinded quality truth or field validation.
- Motion, scene structure, compression, IR and illumination can all alter
  sharpness independently of physical defocus.
- Stage sampling says nothing about continuous false alarms, true field
  recall, onset latency or recovery reliability.
- Existing scene cues are preserved. Phase 3M suppression candidates
  previously lost known covered events; this work does not apply them.
- Next: prototype a causal/rolling temporal observer that never silently
  resets its trusted reference. Validate on representative annotated-normal
  intervals and independent new-camera footage, with frozen acceptance
  gates for event loss, warning burden, latency, UNKNOWN and custody.
- Production Camera Trust and officer case handling remain unchanged.
  Draft PR should remain experimental and unmerged.

**Status: research diagnostics only; not production qualified.**
