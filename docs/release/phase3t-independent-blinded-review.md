# Phase 3T — Independent blind adjudication protocol

**Status:** Development only. Not a release gate or production-ready claim.
Stacks on draft Phase 3S PR #74; no changes to camera runtime, officer
workflow, physical reference, alerts, incident recovery, or main branch.

## Why this is the correct next gate

Uploaded Phase3S new pre-event control report confirms 4/4 additional
normal-labeled 180-second windows selected on each development day,
without rerunning the previous 16 Phase3R windows per day.

| Existing + new 3-consecutive candidates | Day3 | Day4 | Both |
| --- | ---: | ---: | ---: |
| Phase3R selected normal windows | 16 | 16 | 32 |
| Phase3S selected NEW pre-event windows | 4 | 4 | 8 |
| Total selected normal-labeled exposure (hours) | 1.0 | 1.0 | 2.0 |
| Phase3R three-consecutive episode starts | 13 | 2 | 15 |
| Phase3S NEW pre-event episode starts | 0 | 1 | 1 |
| Total three-consecutive episode starts | 13 | 3 | 16 |

Model signals are not evidence of actual unusable camera footage. The
same development cameras and thresholds have already been inspected.
The next useful progress requires independent visual adjudication
instead of repeatedly fitting confirmation policies to known footage.

## New tool: scripts/prepare_phase3t_blinded_reviews.py

- Accepts pinned Phase3R and Phase3S JSON. Verifies their source hashes
  match within day, upstream control denominators, all candidate counts,
  no overlap between 3R/3S windows and all nonproduction/unknown flags.
- Chooses 10 candidate/control windows per day (20 cases by default).
  Model-candidate-bearing intervals are intentionally overrepresented
  for diagnostic review. Remaining windows are sampled across timeline
  using deterministic quantiles. This DOES NOT constitute an unbiased
  estimate of false-alert incidence, precision, or sensitivity.
- Generates two identical reviewer CSV worksheets (reviewer_01.csv,
  reviewer_02.csv). Each has a distinct case_id and local source alias
  DAY3 or DAY4, start/end frame, and unfilled observation questions.
  Model candidate activity, hypothesis, stratum, source phase and
  previous annotation are hidden from reviewer worksheets.
- Also creates SEALED_DO_NOT_SHARE_with_reviewers.json with exact
  case-to-model mapping for post-adjudication comparison. It must remain
  private and not be sent to reviewers until both independent CSV
  assignments have been completed and locked.
- Reviewers need legitimate LOCAL authorized access to original footage.
  The tool does not open, transcode, crop, display, or export media.
  Do not upload raw identifiable camera footage or screenshots.

## Reviewer instructions

Two independent people should inspect each indicated 180-second
interval using the local original Day3/Day4 source video.
Do not disclose the sealed key or model candidate label.

Each reviewer should fill ALL columns, using exactly:

- footage_available_yes_no_unknown: yes / no / unknown
- visible_focus_loss_yes_no_uncertain: yes / no / uncertain
- lighting_transition_yes_no_uncertain: yes / no / uncertain
- physical_camera_displacement_yes_no_uncertain: yes / no / uncertain
- foreground_occlusion_yes_no_uncertain: yes / no / uncertain
- image_usable_for_human_observation_yes_no_uncertain: yes / no / uncertain
- reviewer_confidence_low_medium_high: low / medium / high
- reviewer_id: non-sensitive label, e.g. reviewer01 or reviewer02
- short_observation_notes_without_person_identifiers: optional
  observational rationale only, no person names or identifiable details

Reviewers must not force uncertain into yes or no. A 180s interval
can contain mixed behavior. An apparent focus change is a physical
observation, NOT proof of intentional tampering. When images cannot
be viewed, use unknown/uncertain, never assert camera usability.

## Local usage (no video processing)

Open PowerShell in a checked-out Phase3T branch:

    $root = 'C:\Users\Admin\Desktop\KaushalWatch-live\artifacts'
    $out = Join-Path $root ('phase3t\review-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force $out | Out-Null
    python .\scripts\prepare_phase3t_blinded_reviews.py `
        --phase3r-report "$root\phase3r\normal-burden-20261018-123541.json" `
        --phase3s-report "$root\phase3s\pre-event-20261018-125003.json" `
        --out-dir $out --per-day 10

Keep reviewer files separate and independently completed. After
they finish, preserve the two original reviewer CSVs and sealed key
and return only the completed de-identified CSVs plus sealed numeric
key to the research lead for a FIRST comparison of agreement,
disagreement, uncertainty and candidate-positive/negative strata.
Do not compute sensitivity/specificity until independent source
custody and representative held-out test annotations exist.

## Further gates

1. Next software phase after reviewers return: independent reviewer
   CSV validation, blinded agreement/unknown analysis, explicit
   adjudication disagreements, and numerical model-vs-reviewed
   development contingency tables with missingness denominators.
2. A second separate physical camera/site holdout, approved fixed
   reference, source provenance, night/day/IR controls, and stable
   policy frozen prior to independent validation are still required.
3. Ordinary scene integrity, camera-covered/moved review, and
   operator incident continuity remain separate and untouched.

**Never treat review case counts as independently verified field false-alarm rates.**
