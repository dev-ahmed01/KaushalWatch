# Phase 3D — Camera scene-change fusion (shadow only)

**Status:** experiment derived from draft PR #54, **not merged to main**.
**Scope:** advisory numerical signals only; no unattended Camera Trust decisions,
attendance exceptions, practical-work decisions, or camera reference enrollment.

## Decision contract

The two existing experimental observers run on the same frame and interval:
SpatialSceneShadow (regional tile similarity, 55% candidate) and
PersistentSceneProbe (sustained global scene difference).

| Spatial evidence | Spatial review | Persistent global change | Shadow outcome |
|---|---|---|---|
| WARMUP | false | either | WARMUP |
| SUFFICIENT_TILES | true | either | SPATIAL_SCENE_REVIEW |
| SUFFICIENT_TILES | false | either | NO_SHADOW_REVIEW |
| UNKNOWN_LOW_TEXTURE | false | true **and global quality sufficient** | LOW_TEXTURE_GLOBAL_SCENE_REVIEW |
| UNKNOWN_LOW_TEXTURE | false | false **or global quality limited** | UNKNOWN_LOW_TEXTURE |

All outcomes are **advisory**. NO_SHADOW_REVIEW is not proof of stable,
authenticated, live, usable footage. The low-texture global cue requests
human review: it cannot distinguish viewpoint displacement from obstruction,
scene lighting, foreground people, time-of-day/IR transitions, or equipment
movement. Missing or malformed probe outputs raise ValueError. The global persistent
change probe itself can signal change on completely textureless static
footage; the fusion now rejects its fallback when its independent
quality_limited indicator is true.
The low-texture case does not weaken the spatial evidence threshold.

## Reproduce existing CSV exploratory comparison (PowerShell)

Use the isolated experimental worktree updated to this branch:

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $base = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\spatial"
    python "$trial\scripts\score_uhctd_shadow_fusion.py" --day3 "$base\day3\spatial_shadow_samples.csv" --day4 "$base\day4\spatial_shadow_samples.csv" --out "$base\fusion_comparison.json"

IMPORTANT: Existing spatial-shadow CSVs produced before this change lack
the required global_quality_limited column. They cannot score the revised
rule. Regenerate the short-window diagnostics with the updated experimental
branch first, then run the replay. Do not treat the older 8/8 result as a
verified score for the revised rule.

The script reads numerical CSVs only. It produces JSON with source CSV
SHA-256 hashes, validates essential row structure, and reports new rising
event alerts separately from pre-existing alerts and false normal-window
warnings. It is not an end-to-end live-camera evaluation.

To run the new tests inside that worktree:

    python -m pytest backend/tests/test_camera_shadow_fusion.py -q

Tests use synthetic arrays and CSVs, never restricted CCTV.

## Existing Day 3/4 development reports

| Method | Selected moved events newly flagged | Selected normal windows flagged |
|---|---:|---:|
| Spatial 55% only | 5/8 | 0/24 |
| Persistent global only | 7/8 | 3/24 |
| Spatial or low-texture global | 8/8 | 0/24 |

These numbers apply to the **original unguarded experimental fusion**.
A stationary featureless synthetic recording produced spurious global-change
reviews and exposed the need for an explicit global-quality guard.
The revised rule must be rescored on regenerated CSVs and full recordings.
These are **post-hoc, already-inspected development results**. The rule was
selected using the same recordings, healthy warmups depended on annotations,
and the selected intervals restarted detector state. Twenty-four selected
normal windows do not establish a full-day false-alarm rate or performance
at a deployment site. The fallback never establishes proof of sabotage or
restores trustworthy visual evidence.

## Promotion requirements

1. Do not merge PR #54 into main based on this experiment.
2. Obtain independently verified healthy camera references; never enroll
   a new reference silently after a potential viewpoint change.
3. Evaluate complete continuous recordings: lighting/night IR transitions,
   occlusion, pedestrians, rain, low texture and reference drift.
4. Obtain fresh authorized independent site/camera recordings and blind
   annotations; freeze calibration vs hold-out allocation in advance.
5. Measure incident onset recall, false-review episodes per normal hour,
   delays, evidence-usability errors, unknown rates and subgroup failures.
6. Separate advisory review from evidence withholding, camera-integrity
   suspicion and officer decisions; keep all automatic enforcement disabled.


## Continuous-stream development evaluator

The continuous evaluator uses the same two experimental observers, sampling
numerical states through the entire recording **without resetting at each
event**. It reads all annotation rows, validates the first 10 seconds as
dataset-annotated normal, checks frame order/count, and retains the initial
warmup reference for the whole run. This is still not an approved operational
reference.

PowerShell examples (from the experimental worktree):

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $data = "C:\Users\Admin\Desktop\MEVA"
    $out = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\continuous"

Preview first (short smoke check, not full-day evidence):

    python "$trial\scripts\evaluate_uhctd_continuous_shadow.py" --video "$data\video.avi" --annotations "$data\annotations-1.csv" --out "$out\day3-preview" --sample-seconds 1 --preview-seconds 60

Only after the preview succeeds, run full recordings separately:

    python "$trial\scripts\evaluate_uhctd_continuous_shadow.py" --video "$data\video.avi" --annotations "$data\annotations-1.csv" --out "$out\day3" --sample-seconds 1

    python "$trial\scripts\evaluate_uhctd_continuous_shadow.py" --video "$data\UHCTD_Day4\video.avi" --annotations "$data\UHCTD_Day4\annotations.csv" --out "$out\day4" --sample-seconds 1

Do not delete your original recordings or commit generated outputs.
Only numerical JSON/CSV outputs are emitted; both inputs are SHA-256 hashed.
The full-pass summary reports method-wise normal review samples, new
review episodes per annotated normal hour, low-texture uncertainty counts,
preexisting-at-onset alerts, class-wise fresh event recall and delays.
Normal episodes are counted at sampled rising edges; transitions with an
already-existing positive alert need careful human review. This remains
a **development result** even after two complete 24-hour passes, as both
recordings were previously inspected and used to select the fusion logic.

The first ten seconds are not independently approved camera calibration.
Re-enrollment is deliberately disabled. If later true normal footage differs
substantially from the initial camera appearance, this method can produce
persistent nuisance reviews; that is a limitation to measure, not a reason to
silently reset the reference.

CI regression command:

    python -m pytest backend/tests/test_camera_shadow_fusion.py backend/tests/test_camera_continuous_shadow.py -q

No new released Camera Trust decision path is activated by this evaluator.


## Phase 3D — complete-run failure triage (no new video pass required)

The early full-day diagnostics exposed an unacceptable number of advisory
review signals during annotation-normal time:

| Complete recording | Fresh moved-event alerts | Normal samples with fusion review | New episodes per normal hour |
|---|---:|---:|---:|
| UHCTD Day 3 | 15/24 | 41.0366% | 27.196730 |
| UHCTD Day 4 | 22/24 | 7.0102% | 14.382874 |

This **fails the reliability objective** even though the separate
selected-window exploratory surveys reported 8/8 events and 0/24 controls.
Normal labels are not equivalent to independently certified usable footage.
These values are developmental, not independent holdout data.

The existing complete-run JSON summaries and event CSVs can be triaged
without touching raw recordings. In PowerShell:

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $root = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2"
    python "$trial\scripts\triage_uhctd_continuous_shadow.py" --day3 "$root\continuous\day3\continuous_shadow_summary.json" --day4 "$root\continuous\day4\continuous_shadow_summary.json" --out "$root\continuous_failure_triage.json"

The tool shows **spatial vs global vs fusion** normal review rates and
fresh event misses/preexisting alerts, and creates a numerical report.
It cannot attribute exact failure timestamps or distinguish baseline drift
from nuisance foreground movement using the existing aggregated summaries.
To establish causes, instrument time-binned numerical traces and episodes
in a subsequent controlled run. Do not adjust thresholds merely because
short-clip results look promising.


### Extended numeric diagnostics (re-run continuous evaluator once)

The continuous evaluator now produces a third file:
continuous_shadow_normal_review_episodes.csv. This lists each contiguous
annotation-normal span flagged by the advisory fusion, with start/end frames
and seconds, sampled duration, whether the alert carried across a label
boundary, and how many samples were attributed to spatial versus the guarded
global fallback. The summary JSON also contains normal_review_hours, a
record per hour relative to recording start, with normal-sample fractions,
decision origin, low-texture uncertainty and quality-limited global
evidence counts. Hours with few annotated-normal samples must be
interpreted carefully.

Neither this instrumentation nor the triage command re-enrolls references,
resets temporal state midstream, or modifies model thresholds.
Do not mistake normal-label review spans for proof of a false tampering
accusation: they are a prioritized queue for authorized human assessment of
lighting, scene content, camera obstruction and underlying reference validity.
Do not upload private frames, extracted screenshots or identifiable CCTV
contact sheets to GitHub.
