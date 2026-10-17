# Phase 3J — Camera Review Notification Reliability (Offline)

**Status: experimental draft only.** Stacked on Phase 3I draft PR #64,
which depends on Phase 3H #63 and Phase 3G #62. No deployed service
imports this code; production main and detector thresholds are unchanged.

## What this phase addresses

The completed full-day UHCTD development runs exposed unacceptable
annotated-normal scene-review burden, despite promising selected-window
movement detections.

| metric | Day 3 | Day 4 |
| --- | ---: | ---: |
| Annotated-normal review fraction | 0.410366 | 0.070102 |
| New review episodes / annotated-normal hour | 27.19673 | 14.382874 |
| Fresh annotated moved-event alerts | 15/24 | 22/24 |

These are detector cues, not independently adjudicated false-positive
rates. Phase 3J does NOT improve raw detector warnings or event recall.
It evaluates the frequency at which those cues would generate distinct
officer notification messages.

## Implemented

- camera_reference_notification_shadow.py implements purely offline,
  independent scene and evidence-quality notification state.
- A sustained scene review opens one notification and periodic reminders.
  Transient gaps do not create repeated notifications.
- After sustained texture-sufficient frames without a review cue, the
  notification is marked SCENE_CUE_CLEARED_REVIEW_PENDING. This means
  only a cue cleared; it does NOT verify restored camera integrity,
  approve attendance, or automatically restore or replace a reference.
- UNKNOWN_LOW_TEXTURE interrupts cue-clear eligibility, is tracked
  independently, and generates independent quality advisory messages
  when persistent. A global fallback can still issue a scene review
  during UNKNOWN without declaring the footage usable.
- One full video decode runs SIX fixed shadow candidate policies:
    clear30_remind300
    clear30_remind900
    clear60_remind300
    clear60_remind900
    clear120_remind900
    clear120_remind1800
  These suffixes are seconds. They do NOT modify or calibrate the
  55% spatial detector review threshold or its frozen confirmation.
- All candidates consume exactly the same detector observations.
  Every candidate returns per-annotation-class scene/quality notices,
  scene/quality notices per annotated-normal hour, unchanged raw
  scene-review and low-texture sample counts, and explicit nondeployment
  status. No candidate is automatically selected for production.
- The full-recording report retains raw annotated-normal review fraction,
  rising review episodes, independent per-class onset detection,
  preexisting cue status, and post-onset delay.
- Low-texture totals now count UNKNOWN_LOW_TEXTURE even where global
  fallback produces a simultaneous scene review (previously skipped).

## Important interpretation

Fewer notification events mean fewer hypothetical officer inbox messages,
NOT fewer wrong detector outputs. Officer acknowledgement, final
incident closure, automatic reference re-enrollment and verified
camera recovery are NOT implemented. Notification state is transient
offline, not a reliable delivered-message ledger or queue.

No live camera, attendance, case, sanction or compliance endpoint
imports this notification policy.

## Execution

The existing Phase 3I offline CLI now includes the notification policy
sweep automatically:

    python scripts/run_phase3i_offline_reference.py \
      --manifest path/to/private_day3_manifest.json \
      --out path/to/private_day3_phase3j.json \
      --sample-seconds 1

It still requires the correct camera's independently reviewed private
reference, authorised staging reviewer credentials, and pinned source
video and annotation SHA-256. Do not invent a matching reference from
the video's first 10 seconds; do not equate either UHCTD recording
with the unrelated demo centre. Do not upload camera footage or
credentials to GitHub.

Synthetic tests:

    python -m pytest backend/tests/test_camera_reference_notification_shadow.py \
      backend/tests/test_camera_offline_reference_benchmark.py -q

## Release gates

1. Authorised, correct-camera, complete replay of Day 3 and Day 4, not
   only synthetic/selected-window tests.
2. Independent inspection of shadow/pedestrian/IR/darkness/obstruction
   and carryover changes; normal annotations do not guarantee usability.
3. Approved operational policy for durable notifications, officer
   acknowledgement, explicit reference recovery, secure delivery
   deduplication and retention; no auto reference resets.
4. Improvements to RAW false alarms and incident recall separately
   measured; grouping notification messages cannot satisfy these gates.
5. A newly untouched blinded multi-camera validation set and
   independent post-deployment safety audit.

This is development instrumentation and not a production release.
