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
