# Phase 3M — Single-run local Day 3 + Day 4 development replay

**This is not a camera-trust release.** Draft branch stacked on Phase 3L
and previous experimental PRs. No changes to protected production main.

## Why this exists

The Day 3 and Day 4 sources are on the researcher's local Windows
computer, not GitHub. No genuine independently authenticated,
officer-approved reference frame for the two separate cameras has
been supplied here. Previous Phase 3L tools therefore could not
generate new complete-day measurements.

Phase 3M adds an **explicit unapproved development-only workaround**:
for each recording, choose the midpoint of the FIRST 90 consecutive
seconds of annotated-normal video, within the first ten minutes,
and keep that single decoded frame only IN MEMORY. The reference rule
is fixed before examining model performance; no candidate selector,
multiple baseline search, or image quality tuning is performed.

**Critically, an annotation of normal does not prove the camera image
is healthy.** This cannot establish physical camera provenance,
independent review, untouched held-out evaluation, or an operational
reference. Both frames were selected from their own evaluation video.
Do not present resulting numbers as measured on a previously approved
real camera reference or use them for production policy selection.

The local script:
- Checks both recordings and headerless one-based annotation files exist.
- Checks video metadata and computes SHA-256 of both original videos
  and annotation files before analysis.
- Fails without a minimum early annotation-normal interval on either
  source, without an explicitly opted-in experimental flag.
- Captures *one* reference per source via sequential decoder access
  and an SHA-256 of shape + raw BGR bytes, never exports its pixels.
- Rejects duplicate source videos, unsafe dimensions and any mismatch
  between reference bytes before preview/full processing.
- Runs Day 3 and Day 4 sixty-second previews first. Optionally
  runs BOTH full 24-hour recordings, maintaining continuous detector
  state and scoring all Phase 3L candidates at the original one-second
  cadence. All core Stage 3K/3L input checks remain in force.
- Writes a path-free reference metadata manifest, numeric per-day
  preview reports, numeric full-day reports, and the existing strict
  two-day candidate comparison when full mode finishes successfully.
- Uses an exclusive new output directory; previous evidence cannot
  be overwritten. Crashes never create a false successful complete
  report, and each successful JSON report is written atomically.
- Does not contact S3, a live camera, officer services, production API,
  or PostgreSQL; nothing approves a scene or changes evidence usability.

## Windows PowerShell one-batch command

Use a separate experimental checkout. From the existing clean GitHub
checkout at C:\Users\Admin\Desktop\KaushalWatch-main:

    $repo = "C:\Users\Admin\Desktop\KaushalWatch-main"
    $trial = "C:\Users\Admin\Desktop\KaushalWatch-phase3m"
    $source = "C:\Users\Admin\Desktop\MEVA"
    $outRoot = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3m"
    $out = Join-Path $outRoot ("run-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

    git -C $repo fetch origin
    if ($LASTEXITCODE -ne 0) { throw "Git fetch failed" }
    if (-not (Test-Path $trial)) {
        git -C $repo worktree add --detach $trial origin/experiment/phase3m-dual-day-research-replay
        if ($LASTEXITCODE -ne 0) { throw "Could not add separate Phase 3M worktree" }
    } else {
        if (git -C $trial status --porcelain) { throw "Phase 3M worktree has local modifications" }
        git -C $trial switch --detach origin/experiment/phase3m-dual-day-research-replay
        if ($LASTEXITCODE -ne 0) { throw "Could not update experimental worktree" }
    }
    python -c "import cv2, numpy; print('OpenCV + NumPy ready')"
    if ($LASTEXITCODE -ne 0) { throw "Please use the configured KaushalWatch Python virtual environment" }

    python "$trial\scripts\run_phase3m_dual_day_research.py" --day3-video "$source\video.avi" --day3-annotations "$source\annotations-1.csv" --day4-video "$source\UHCTD_Day4\video.avi" --day4-annotations "$source\UHCTD_Day4\annotations.csv" --run-dir $out --sample-seconds 1 --preview-seconds 60 --run-full --allow-unapproved-self-reference-development
    if ($LASTEXITCODE -ne 0) { throw "Phase 3M replay incomplete; do not interpret partial reports" }
    Get-Content "$out\phase3m_status.json" -Raw
    Get-Content "$out\phase3m_dual_day_comparison.json" -Raw

The command above does TWO complete videos after both previews. Depending
on CPU speed and storage this may take a long time; do not promise runtime.
Use a NEW timestamped run directory for each fresh attempt.

To test just the selected references and the first 60 seconds without
waiting for a full run, omit --run-full. Its status is
PHASE3M_PREVIEWS_ONLY_NO_FULL_RECORDING_EVALUATION and it will NOT
write any purported complete comparisons.

**Only share numeric JSON reports**, ideally phase3m_status.json,
research_reference_manifest.json, and phase3m_dual_day_comparison.json.
Do not upload private clips, images, officer secrets or identifiers.

## What this run can and cannot tell us

- It can reveal which Phase 3L candidate rules lose annotated covered,
  defocused or moved events when compared to the SAME original frozen
  detector on TWO full recordings, under a deterministic in-video
  reference experiment.
- It can quantify annotated-normal warning fractions and event review
  counts, and compare notification/cause hypotheses without hiding raw
  evidence.
- It cannot establish a true false-positive rate (normal annotation
  is not verified usable), independently confirm physical movement,
  or verify camera source provenance. In-video self reference can
  dramatically change the shadow baseline and is not approved.
- Day 3 and Day 4 have been repeatedly debugged. Neither counts as a
  blinded, untouched holdout, and no model/policy is authorized for
  production even if every development result improves.
- The real approved-reference process (Phase 3G through 3I) remains
  separate, gated and unmerged; nothing here modifies it.

## Tests and next gate

The synthetic suite uses two generated AVI clips with different content,
headerless CSV annotations and a known post-onset move. It checks
immutable in-memory references, previews/full status, cross-day policy
comparison, no media export, failed preflights, duplicate inputs,
missing normal windows and no overwrite of prior reports.

After the user executes the batch: examine losses by event start frame,
quality unknowns, normal-period review burdens and source-reference
sensitivity. Require a separately verified camera reference plus
independently blinded multi-camera held-out evidence before any
operational promotion. No automated baseline reset, punitive or
attendance action is authorized.
