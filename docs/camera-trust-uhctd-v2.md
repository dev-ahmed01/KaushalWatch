# UHCTD Camera Trust v2 — candidate results

This branch improves evidence quality checks, NOT proof of camera sabotage.
Only synthetic regression examples are committed; UHCTD footage remains local.

## Changes
- Stream-scoped temporal state in attendance and practical-work pipelines.
- Relative blur measurement avoids misclassifying naturally soft CCTV footage.
- Persistent scene-composition loss may identify obstruction or movement.
- Exact repeated frames for three seconds flag possible frozen/replayed video.
- Sustained blur, darkness, obstruction and movement gate visual conclusions.

## Development-set probe (NOT held-out evaluation)
Source: four short clips from UHCTD Day 3, 3 FPS, 680x510 pixels.
Three tampering clips each include 12 seconds of normal baseline.
The tampering clip counts below refer to their 106 post-onset frames.

| Clip | Old untrusted frames | Candidate untrusted frames |
|---|---:|---:|
| Normal 106-frame clip | 44 (false positives) | 0 (false positives) |
| Covered | 91/106 | 90/106 |
| Defocused | 40/106 | 90/106 |
| Moved | 0/106 | 93/106 |

Candidate first-event delays: 5.33 seconds covered, 5.33 seconds
defocused, 4.33 seconds moved, measured after annotated onset.
These are small development-set results only.

## Before promotion
1. Test Day 4 or another camera as a held-out source, without retuning.
2. Measure false alarms per hour, event-level detection, detection delay.
3. Check crowded scenes, lighting/shadow changes, low-light and indoor labs.
4. Verify evidence suspension in attendance AND practical-work flows.
5. Version new candidate thresholds in a separate vision profile. Do NOT
   alter the existing frozen fixed-camera-v1 profile until validated.
6. Respect dataset research-only licensing: do not publish its videos.

Limitations: frozen scene vs replay cannot be reliably proven by pixels alone;
a camera that starts obstructed lacks a reliable initial reference; foreground
changes can resemble a scene shift. Treat warnings as evidence-quality
flags requiring officer review, never punitive determinations.


## Phase 3 — development-only conservative candidate
The complete Day 4 Camera B recording showed **52.2%** false untrusted
samples and 5.30 false-alarm episodes per normal hour under the v2
evidence-quality metric. The scorecard also counted alarms already active
at event onset as detected; 37 of 70 marked detections had zero delay.
That event-recall definition is no longer appropriate for new incidents.

Candidate changes on this branch:
- Separate low-visibility **evidence usability** from suspected camera
  **tampering**. Dark footage can still suspend attendance without
  automatically becoming a tamper alert.
- Do not infer obstruction from changing brightness alone.
- Require a coherent translated scene (phase correlation on edge maps)
  before treating raw reference dissimilarity as camera displacement.
- Add counters for normal scene failure reasons and separate evidence
  quality metrics in the UHCTD evaluator.
- Require a **fresh rising tamper alert** to count as event detection. An
  already-active alert is reported, but no longer credited to a new event.

Development inspection only: on the FOUR uploaded Day 3 clips the
candidate flagged 0/106 normal, 90/106 covered, 90/106 defocused and
93/106 moved post-onset frames. This is a small, selected development set,
not a statistically valid result for 24-hour surveillance.

**Do not reuse Day 4 as an untouched test of this candidate.** Its failure
details have already influenced the design, even if its frames were not
available for local tuning. Before promotion, find a new, truly untouched
recording from another day/camera with full labels, evaluate under the
frozen candidate, and inspect false alarms/hour plus new-alert
event recall. Neither old full-recording Day 4 results nor short
Day 3 clip scores establish deployment suitability.

Camera trust based on visual evidence cannot reliably authenticate true
stream freshness or prove malicious tampering. Human review remains
the final decision.
