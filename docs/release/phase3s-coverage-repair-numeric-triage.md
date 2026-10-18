# Phase 3S — Repair pre-event coverage and audit nuisance candidates

**OFFLINE/RESEARCH ONLY; no operational warning policy change.**
Stacked on draft Phase 3R PR #73.

## Phase 3R supplied evidence (18 October 2026)

The uploaded normal-burden-20261018-123541.json contains exactly
16 NORMAL-ANNOTATED 180-second control windows for each development day
(32 total; 0.8h per day, 1.6h combined), sampled every 2 seconds.
These annotations are NOT independently authenticated usable footage.

| Prior policy | Day3 candidate episode starts | Day4 candidate episode starts | Combined |
| --- | ---: | ---: | ---: |
| Original Phase3P unmodified | 16 | 2 | 18 |
| Sharpness only | 16 | 2 | 18 |
| 2 of preceding 3 | 13 | 2 | 15 |
| 3 consecutive | 13 | 2 | 15 |

Strict consecutive confirmation leaves 13 research-only candidates
on Day3 sampled normal-labeled footage and two on Day4. The
phase3r candidate-episode starts are NOT confirmed false positives;
do not extrapolate to full-day deployments or select a cutoff.

Day3 3-consecutive warning-bearing windows: progress strata
01, 02, 08, 09, 10, 11, 12, plus one AFTER event boundary.
Day4 warning-bearing window: progress stratum 04.
All 12/12 progress strata sampled each day. Four event-adjacent
POST controls sampled per day, and ZERO BEFORE controls: the four
predeclared before candidates per day collided with progress windows.
This biased coverage must not be interpreted as a reliable comparison
of false alert burden before vs after incidents.

## Changes

1. scripts/analyze_phase3s_normal_burden.py validates the Phase3R JSON
   source gates, two-day counts, no overlap, sampled exposure and
   per-policy/window agreement; outputs descriptive counts and a
   candidate-bearing frame-range review manifest without raw media.
2. scripts/run_phase3s_missing_pre_controls.py rechecks Phase3M source
   video/annotation hashes and frozen UNAPPROVED in-video reference.
   It verifies the 32 Phase3R original control ranges and selects
   ADDITIONAL pre-event normal-labeled controls by a deterministic
   nearest-eligible-quantile fallback; selection uses only annotations
   and frame indices, NEVER candidate output or known sharpness.
3. Only NEW pre-event frames are decoded at 2-second cadence.
   Previously decoded Phase3R controls are reused as numbers, not
   replayed again. Reused and new counts are reported separately.
4. Dedicated tests cover accurate statistics, release gates, unknown
   evidence, overlaps, quantile repair, impossible coverage and
   safe refusal of source integrity violations.

## Recommended minimal local run

Use a clean Phase 3S checkout. Running analysis requires ONLY the
Phase3R JSON, no videos:

    python scripts/analyze_phase3s_normal_burden.py --input C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3r\normal-burden-20261018-123541.json --out C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3s\triage-new.json

To repair the missing pre-event coverage, run with the unchanged
local Phase3M video/annotation files. Pre-create the output folder:

    python scripts/run_phase3s_missing_pre_controls.py `
        --day3-video C:\Users\Admin\Desktop\MEVA\video.avi `
        --day3-annotations C:\Users\Admin\Desktop\MEVA\annotations-1.csv `
        --day3-report C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808\full\day3.json `
        --day4-video C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\video.avi `
        --day4-annotations C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\annotations.csv `
        --day4-report C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808\full\day4.json `
        --phase3r-report C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3r\normal-burden-20261018-123541.json `
        --pre-each 4 --window-seconds 180 --sample-seconds 2 `
        --out C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3s\pre-event-new.json `
        --allow-unapproved-development-reference

These are examples: source paths must be checked on the local machine.
Outputs must be unused .json paths. Upload only the numeric output.

## Interpretation and next gate

- The existing recordings are development samples; expanded controls
  do not make them independently held-out or physically authenticated.
- Review frequent candidate-bearing control frame ranges locally
  with blinded reviewers and custody safeguards. Never export
  identifiable video or reference to a public repository.
- Preserve ordinary scene integrity, covered, displaced and defocused
  incident protections. Quality-only signals must not clear incidents.
- Unmeasured spatial/scene evidence remains UNKNOWN, NOT healthy.
- Need independent cameras and true normal-hour burden validation,
  plus officer workflow, device authorization and privacy controls
  before any production consideration.

**Do not merge this research stack into production main.**
