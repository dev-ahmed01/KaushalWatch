# Phase 3R — Systematic Normal-Footage Burden Audit

**Research-only / offline / not held out / not production-qualified.**
Based on the verified Phase 3M Day3/Day4 recording source and the
Phase 3P causal numeric observer, stacked on Phase 3Q draft PR #72.

## Why this work is needed

Phase 3P/3Q yielded only FOUR fully normal-labeled control windows across
two days (four other planned controls were excluded). Even the promising
exploratory defocus signal and 3-sample confirmation comparison do not
estimate realistic officer false-warning burden. Also, annotations marked
normal do NOT establish authenticated healthy camera footage.

## What was built

- scripts/run_phase3r_systematic_normal.py: independently verify entire
  video/annotation digests, Phase 3M report completion and frozen
  development-reference pixel hash using Phase3P verification.
- Split each complete recording by frame count into 12 fixed progress
  strata. Within each stratum choose a deterministic nearest-midpoint
  180-second control interval ONLY where every label is normal.
  Ineligible strata are preserved explicitly with their label coverage
  and skip reason. No sampling based on the model's predicted warnings.
- Add up to four intervals immediately BEFORE and four AFTER
  annotation event boundaries per day, sampled across available
  eligible events, no overlap with selected time strata.
- Each chosen interval uses a FRESH causal observer (no history
  inherited across distant windows). Decode frames every two seconds;
  the first 30 seconds are warmup, not treated as clean evidence.
- Reuse frozen Phase3Q numerical exploration: unmodified Phase3P
  boolean, sharpness-only, 2-of-3 and 3-consecutive. No policy selection
  or tuning. Report candidate starts, sample-level active time, maximum
  episode length, UNKNOWN and illumination status.
- Distinguish sampled *normal-annotation* candidate episodes from true
  adjudicated false alarms. Record windows and observed time with zero
  warning without fabricating source trust or operational closures.
- Do not export frames, crops, face images or source video. Outputs are
  numeric JSON and frame indices only.

## What it cannot establish

The 12 bins refer to positions in the recorded timeline; real day/night
or wall-clock phase is NOT known. The selection is deterministic and
annotation-conditioned, NOT a random/unbiased sample of camera hours.
Short normal sections are unobserved, and no blind expert has certified
image health. Ratios and confirmation cutoffs were already inspected
on this development data, so these conditional counts are NOT field
false-positive rates, sensitivity, specificity, or release criteria.
Raw scene review and spatial measurements are NOT available and must
remain unmeasured, never healthy by default.

## Command for Windows PowerShell

Create a new isolated checkout. Do NOT run scripts in KaushalWatch-main
if that directory is not a Git checkout, nor change KaushalWatch-live.

    $branch = 'experiment/phase3r-systematic-normal-burden'
    $trial = 'C:\Users\Admin\Desktop\KaushalWatch-phase3r'
    $data = 'C:\Users\Admin\Desktop\MEVA'
    $prior = 'C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808\full'
    $outRoot = 'C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3r'
    New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
    if (-not (Test-Path $trial)) {
      git clone --single-branch --branch $branch https://github.com/dev-ahmed01/KaushalWatch.git $trial
      if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
    } else {
      git -C $trial rev-parse --is-inside-work-tree
      if ($LASTEXITCODE -ne 0) { throw 'Not a Git checkout' }
      if (git -C $trial status --porcelain) { throw 'Refusing to discard local edits' }
      git -C $trial fetch origin
      if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
      git -C $trial switch --detach "origin/$branch"
      if ($LASTEXITCODE -ne 0) { throw 'Checkout failed' }
    }
    python -c 'import cv2,numpy'
    if ($LASTEXITCODE -ne 0) { throw 'Python/OpenCV/NumPy not ready' }
    $out = Join-Path $outRoot ('normal-burden-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
    python "$trial\scripts\run_phase3r_systematic_normal.py" `
      --day3-video "$data\video.avi" `
      --day3-annotations "$data\annotations-1.csv" `
      --day3-report "$prior\day3.json" `
      --day4-video "$data\UHCTD_Day4\video.avi" `
      --day4-annotations "$data\UHCTD_Day4\annotations.csv" `
      --day4-report "$prior\day4.json" `
      --time-bins 12 --adjacent-each 4 --window-seconds 180 --sample-seconds 2 `
      --out $out --allow-unapproved-development-reference
    if ($LASTEXITCODE -ne 0) { throw 'Phase 3R local evaluation failed' }
    Write-Host "Phase3R numeric-only output: $out"

Upload only the generated normal-burden-*.json file for numerical
interpretation. No video, screenshots, or camera face imagery needed.

## Acceptance prerequisites after this development experiment

1. Review every omitted time stratum and pre/post boundary eligibility;
   do not extrapolate missing control footage.
2. Independently adjudicate any flagged normal-labeled intervals before
   calling them false alarms, with privacy and source custody enforced.
3. Preserve covered and moved incident detection: no new suppressions.
4. Freeze a prospective quality policy and enroll independently sourced
   held-out camera footage, authenticated physical reference custody,
   representative daylight/night/IR and real normal-hour officer burden.
5. Continue to keep all Camera Trust PRs in DRAFT, unmerged into main.

**Never use these development observations for enforcement or attendance.**
