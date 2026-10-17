# Phase 3P — Causal Temporal Visibility Quality Research

**OFFLINE / NOT PRODUCTION-QUALIFIED.** Stacked on Phase 3O draft PR #70.
No changes to production main, camera scene warnings, officer actions,
reference lifecycle, incident closure or attendance.

## Rationale

Phase 3N and 3O established an exploratory event-local sharpness decline
at +30s in 48/48 previously inspected defocus episodes, compared with
2/24 selected moved-camera contrast controls. These comparisons were
retrospective and used annotated event starts. A real camera monitor
cannot know when an incident will begin or assume a prior sample is healthy.

## Implemented

- New CausalTemporalQualityShadow consumes only Phase3N numeric features
  from an immutable frozen-reference equality pin. No event annotations.
- Strictly past-only 30s lookback, 2s tolerance, bounded in-memory history,
  consecutive timestamps, gap detection and an explicit unknown path.
- Low-texture source/anchor, unusable denominators and missing history
  abstain; illumination and scene cues remain visible confounds.
- Missing raw scene cue is explicitly None, and spatial evidence is
  NOT_MEASURED. Never fabricate a healthy state.
- Numeric sharpness, edge and contrast ratios remain advisory. Exploratory
  0.5 sharpness decline does NOT issue notifications or approve recovery.
- Includes synthetic adversarial tests and a bounded local two-day runner.

## Local bounded evaluation, no full detector replay

Use branch experiment/phase3p-causal-temporal-quality in a new clean checkout.
Script: scripts/run_phase3p_bounded_causal_quality.py

Existing source video and annotation files:
  Day3: C:\Users\Admin\Desktop\MEVA\video.avi
  Day3 labels: C:\Users\Admin\Desktop\MEVA\annotations-1.csv
  Day4: C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\video.avi
  Day4 labels: C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\annotations.csv

Previously completed Phase3M JSON reports live in:
  C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808\full

PowerShell from the cloned Phase3P repository:

    python .\scripts\run_phase3p_bounded_causal_quality.py `
        --day3-video 'C:\Users\Admin\Desktop\MEVA\video.avi' `
        --day3-annotations 'C:\Users\Admin\Desktop\MEVA\annotations-1.csv' `
        --day3-report 'C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808\full\day3.json' `
        --day4-video 'C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\video.avi' `
        --day4-annotations 'C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\annotations.csv' `
        --day4-report 'C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808\full\day4.json' `
        --events-per-kind 6 --normal-controls 4 --sample-seconds 2 `
        --out 'C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3p\causal-new.json' `
        --allow-unapproved-development-reference

Output directory must already exist, and output path must be unused.
Upload only the resulting numeric JSON. Never upload footage or images.

## Selection and limitations

Predeclared annotation quantiles choose six defocus and six moved-camera
episodes per day. Four quartile-time annotation-normal control windows
are included only when all their labels are normal. Each window spans
60 seconds before to 120 seconds after event onset, sampled every two
seconds. Annotation labels are used for offline selection and post-hoc
comparison ONLY, not passed into the causal observer.

Missing frame-level raw scene cues and spatial evidence remain unmeasured
in this runner; it does not execute the frozen scene detector. The video
files are fully hashed, but only selected frames are decoded; AVI seeking
may have codec inaccuracies. The historical self-selected reference is
not authorized as a healthy physical source. Normal-labeled controls
are not independently validated healthy footage.

Neither this bounded sample nor Phase3N event-centered data establishes
full-day normal-hour false-warning burden, independent sensitivity,
camera recovery, field onset-delay distributions, or production quality.

## Next release gates

1. Expand to representative continuous normal time, IR/lighting,
   low-texture, foreground obstruction and normal movement controls.
2. Freeze policies and test on unseen cameras with officer-authorized
   physical reference provenance and independent annotated ground truth.
3. Preserve unknown states, scene integrity warnings and operator
   incident continuity as separate systems; never suppress raw review.
4. Complete private source custody, S3/IAM retention, officer workflow,
   and field acceptance before any merge into production main.

**This phase is for numerical research only, not field deployment.**
