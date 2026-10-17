# Phase 3N — Separate Visibility Quality and Incident Continuity

**Experimental, unqualified development only.** This branch is stacked on
Phase 3M draft #68 and earlier research branches #67 through #62. All
production/main CameraTrust, attendance, compliance and centre officer
routes stay unchanged.

## Motivation grounded in completed Day3/Day4 Phase3M reports

2026-10-17 development replay used one automatically self-selected 45s
reference frame per camera, not independently approved references.

| Full-day metric | Day 3 | Day 4 |
| --- | ---: | ---: |
| Annotated-normal scene-review fraction | 0.450941 | 0.003546 |
| Fresh defocused events with review | 1/24 | 4/24 |
| Sampled defocus frames with scene-review cue | 120/7260 | 543/7260 |
| Sampled defocus UNKNOWN_LOW_TEXTURE | 4158/7260 | 2345/7260 |
| Covered events with any scene review | 23/24 | 18/24 |
| Moved events with any scene review | 24/24 | 22/24 |
| Existing scene review at onset, per event class | 12 each | 0 each |

Key point: an UNKNOWN_LOW_TEXTURE flag is neither confirmed defocus
nor evidence recovery. The scene-change cue is intrinsically unsuitable
as a stand-alone sharpness/visibility monitor. And the Day 3 fresh
onset metric is heavily confounded by preexisting alerts.

## Built

**Separate sharpness/visibility feature axes**
(backend/app/services/camera_visibility_quality_shadow.py):
- Fixed immutable 192x144 luminance reference, no automatic rebaseline.
- Relative Laplacian variance, gradient edge fractions, contrast and
  luma shift, with categorical hypotheses: SHARPNESS_LOSS_COMPATIBLE,
  REFERENCE_TEXTURE_INSUFFICIENT, ILLUMINATION_CONFOUNDED,
  NO_SHARPNESS_LOSS_SIGNAL.
- Feature cutoffs are UNCALIBRATED technical candidates. A hypothesis
  cannot certify defocus, visibility usability, or clear a scene warning.
- Tests cover generated synthetic blur, unchanged view, global lighting
  shifts, low reference texture, and input validation.

**Incident/warning continuity diagnostics**
(backend/app/services/camera_incident_continuity_shadow.py):
- Distinguishes newly annotated events while a scene review is already
  active from events without a preexisting review.
- Tracks consecutive raw warnings, carryover into normal-labeled
  periods, UNKNOWN intervals, and *cue-clear candidates* only after
  sustained sufficient-texture non-review.
- Cue-clear candidates do NOT approve physical camera recovery. No
  reference reset, officer acknowledgement, case or compliance action.
- Future authorized FULL offline replays include a sampled-only
  continuity summary. Existing Phase 3M numbers are unchanged.

**No-full-replay targeted local analysis**
(scripts/run_phase3n_targeted_visibility.py):
- Reuses the previous Phase3M FULL reports and verifies their SHA-256
  and reference source frame against the actual video and annotations.
- Streams original headerless annotations to enumerate ALL 24
  annotated defocus episodes on each day; also samples alternating
  moved-camera events, without sampling based on model correctness.
- Six predeclared sampling positions per selected event: 30s before,
  onset, 30s after onset, event end, 30s after end, 120s after end.
  Actual source class is verified for each sample; samples after event
  end need not always be normal.
- Reads only the targeted decoded frames; does NOT run the full-day
  scene detector, recalibrate a model or export video/image crops.
- Each numeric record includes the original full-report baseline event
  review status alongside NEW *hypothesis-only* quality measurements.
- Outputs hypothesis counts stratified by event class, sample phase
  and actual annotation class. No production quality claims.
- Output is one new JSON. Separate complete reports remain unchanged.

## One Windows PowerShell evaluation (no 24-hour detector replay)

Use a separate checkout and preserve the old run folder. The latest
Phase 3M sources from the previous successful run are pinned by hash.
From PowerShell:

    $branch = "experiment/phase3n-quality-incident-diagnostics"
    $trial = "C:\Users\Admin\Desktop\KaushalWatch-phase3n"
    $source = "C:\Users\Admin\Desktop\MEVA"
    $old = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m\run-20261017-204808"
    $out = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3n\quality-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"

    if (-not (Test-Path $trial)) {
      git clone --single-branch --branch $branch "https://github.com/dev-ahmed01/KaushalWatch.git" $trial
      if ($LASTEXITCODE -ne 0) { throw "Phase 3N clone failed" }
    } else {
      if (git -C $trial status --porcelain) { throw "Phase 3N checkout has changes" }
      git -C $trial fetch origin
      if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
      git -C $trial switch --detach "origin/$branch"
      if ($LASTEXITCODE -ne 0) { throw "Branch switch failed" }
    }
    python -c "import cv2, numpy"
    if ($LASTEXITCODE -ne 0) { throw "OpenCV/NumPy required" }

    python "$trial\scripts\run_phase3n_targeted_visibility.py" --day3-video "$source\video.avi" --day3-annotations "$source\annotations-1.csv" --day3-report "$old\full\day3.json" --day4-video "$source\UHCTD_Day4\video.avi" --day4-annotations "$source\UHCTD_Day4\annotations.csv" --day4-report "$old\full\day4.json" --out $out --allow-unapproved-development-reference
    if ($LASTEXITCODE -ne 0) { throw "Targeted Phase3N evidence incomplete" }
    Write-Host "Phase 3N result: $out"

Only the NEW numeric JSON is needed for comparing quality hypotheses.
Do not upload video or raw still frames. No image from the source is
saved. The command verifies full video hashes, but does not decode
every source frame again. AVI seeking has codec limitations; these
samples are forensic hypotheses, NOT validated frame identity without
an independently reviewed extraction.

## Open release gates

1. Verify quality axes across independently inspected defocus and
   obstruction samples, including noise, IR shifts, low light and
   legitimate foreground activity.
2. Human-review true scene state and camera reference provenance.
3. Test and freeze any candidate rule on NEW independent camera/site
   videos, including false-normal warnings and missed incident counts.
4. Preserve unknown quality and previously active incident distinctions
   in all metrics; no automatic reference resets or incident closure.
5. Institutional privacy, durable access authorization and real
   production environment acceptance are absent.

**Release status: NOT QUALIFIED.**
