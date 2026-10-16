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


## Phase 3D complete-run triage and ranked failure map

The existing numerical triage shows:
- Day 3 spatial normal review fraction 39.6155%, global 56.6212%,
  fusion 41.0366%. New review episodes per normal hour are respectively
  10.254505, 5.796025 and 27.196730.
- Day 4 spatial 7.0102%, global 51.6066%, fusion 7.0102%.
  Global produces *zero new normal rises* even though more than half
  the normal samples have an active global warning. Thus a 0.0 fresh
  normal-episode rate for global **does not mean zero false warnings**.
- Movement-specific fusion: 15/24 Day 3 and 22/24 Day 4 fresh alerts.
  Do not count the listed covered and defocused events as motion
  detector misses; those have separate evidence-quality pathways.

Because fusion can change its source between spatial and global cues,
it may generate more new alert episodes than either input alone.
This is a hypothesis until the per-hour origin and episode data are
measured, not a reason to adjust threshold or add auto reset.

After re-running the **updated continuous evaluator** to obtain the
three numerical outputs per day, compute a ranked human-inspection map:

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $base = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2\extended"
    python "$trial\scripts\report_uhctd_continuous_failure_map.py" --day3 "$base\day3" --day4 "$base\day4" --out "$base\failure_map.json"

This validates hourly and contiguous-episode totals against the full
continuous summary, then prints the highest-volume normal review hours,
highest-churn normal hours, longest flagged spans, and number of review
samples originating from each method. All times are offsets from the
start of the video: do not infer clock time without trusted capture
metadata. The report is numeric-only and does not inspect individual
frames or establish causal links to lighting, time of day, traffic,
pedestrians or actual camera movement.

Until the high normal-period review burden has been explained and
independently tested, do not merge the candidate into the production
decision path or send punitive camera-tampering alerts to operators.


## Normal-period episode carryover analysis — numerical reports only

The ranked full-recording map makes clear that ordinary annotated-normal
intervals can be flagged by either *carried-over* warnings from the preceding
labeled event or newly raised warnings. These have very different operational
implications, and neither is proof of deliberate interference.

Use the existing **extended** outputs (no video reading required):

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $root = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2\extended"
    python "$trial\scripts\triage_uhctd_normal_recovery.py" --day3 "$root\day3" --day4 "$root\day4" --out "$root\normal_recovery_triage.json" --nearby-seconds 60

The tool counts flagged normal samples within spans that start with a
warning already active across a label boundary, then compares episode
start times with the nearest previous annotated tampering event. It
prints the longest spans, counts attributable to each cue, and flags
which start near an annotated event. **Temporal adjacency is not causal
attribution**: a camera genuinely displaced or deteriorated after a
labeled incident may properly remain under review; equally, a spurious
reference mismatch could persist long after the event.

Next stage: rank which normal-period stretches warrant authorized manual
inspection and discriminate legitimate unusable evidence from nuisance
scene-change warnings. Do not auto-reset a camera baseline or change
camera-integrity / attendance production decisions from these diagnostics.


## Local targeted review queue — from the extended numerical outputs

Post-event normal-period carryover is substantial on Day 3, while most
Day 4 normal review intervals are newly raised and far from recent
annotations. From the latest offline adjacency report:
- Day 3: 9,080 / 26,508 normal review samples (34.2538%) belong to
  episodes already active at the normal-label boundary. Another summary
  shows 21,269 / 26,508 (80.2362%) belong to episodes which STARTED
  within 60 seconds of the preceding annotated event.
- Day 4: 186 / 4,527 (4.1087%) carried across the boundary;
  387 / 4,527 (8.5487%) belong to episodes that started within 60
  seconds of an annotated event.
- Important: the 60-second number is **not** the fraction of flagged
  samples physically occurring within 60 seconds. Entire episode
  durations are included once their START qualifies.
- Neither temporal proximity nor a normal annotation proves the
  visual cause or that footage was usable.

Generate a small numerical CSV list for authorized **local** video
review from the already-produced extended reports, without scanning or
saving any new frames:

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $root = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2\extended"
    python "$trial\scripts\prepare_uhctd_failure_review_queue.py" --day3 "$root\day3" --day4 "$root\day4" --out "$root\manual-review" --nearby-seconds 60 --per-category 3 --churn-hours 2

Outputs:
- targeted_camera_review_queue.csv with recording-relative seconds and
  numerical context. It includes examples of carried, newly near-event,
  and newly far-event normal warnings, plus high-churn intervals.
- targeted_camera_review_summary.json with the **entire** population's
  unreviewed category/sample counts and a warning that the selected cases
  are deliberately enriched for long/churning alerts, not representative
  of benchmark accuracy.

The queue is not a replacement for human inspection. Use local licensed
footage only; classify each selected interval as camera-view displacement,
foreground occupancy/change, lighting or IR mode shift, genuine
visibility degradation, unclear, or other. Independently note whether
the image appears usable and whether the preexisting camera reference
is still valid. Leave conclusions uncertain when evidence is insufficient.
Avoid identifying individuals in reviewer notes. Do not upload raw frames,
faces, footage or identified persons to the repository or a public chat.

Keep the current vision profile and main Camera Trust untouched. First
classify the reviewed intervals; then decide whether a new reviewed-reference
lifecycle, persistence model, or foreground/lighting robustness experiment
is defensible. An automated baseline reset remains prohibited.


## Local interactive review (Windows; no exported frames)

After preparing targeted_camera_review_queue.csv, use the new
review_uhctd_queue_local.py helper to **inspect the original recordings
on the same Windows computer**. It decodes video frames in memory using
OpenCV, displays them using the standard Python tkinter GUI, and records
only reviewer-authored categorical labels in a **separate** CSV.

Preflight (headless, validates paths and existing labels):

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $meva = "C:\Users\Admin\Desktop\MEVA"
    $review = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2\extended\manual-review"
    python "$trial\scripts\review_uhctd_queue_local.py" --queue "$review\targeted_camera_review_queue.csv" --day3-video "$meva\video.avi" --day4-video "$meva\UHCTD_Day4\video.avi" --reviews-out "$review\local_review_decisions.csv" --validate-only

Open the desktop viewer (same command without --validate-only):

    python "$trial\scripts\review_uhctd_queue_local.py" --queue "$review\targeted_camera_review_queue.csv" --day3-video "$meva\video.avi" --day4-video "$meva\UHCTD_Day4\video.avi" --reviews-out "$review\local_review_decisions.csv"

The viewer provides a time slider, 5s/30s frame steps, start/middle/end,
and optional **5-second frame scan** (not full frame-rate video playback).
For each of the 22 intervals choose scene classification, whether
evidence is usable, whether the earlier camera reference remains valid,
and review status. You may mark uncertain or needs second review when
the still-frame scan does not resolve the cause. Save and switch cases;
existing decisions resume from the separate output CSV.

The scanner never creates JPEGs, screenshots or playable clips, never
sends data to GitHub, and never mutates the generated queue or original
video files. The reviewer CSV is **not** independent validation: these
22 cases were selected for likely failure, and neither pre-event
reference quality nor annotation-normal scene usability is proven.
Do not enter people's names or identifiable details in reviewer notes.
Do not merge this experimental branch into main based solely on the queue.


## Summarize local reviewer decisions (private aggregate only)

After inspecting selected cases locally and saving
local_review_decisions.csv, analyze exact case coverage and scene outcomes
without needing footage or uploading reviewer notes:

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $review = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2\extended\manual-review"
    python "$trial\scripts\summarize_uhctd_manual_reviews.py" --queue "$review\targeted_camera_review_queue.csv" --reviews "$review\local_review_decisions.csv" --out "$review\manual_review_aggregate.json"

The tool validates exact case IDs/metadata against the generated queue,
identifies cases marked REVIEWED / UNREVIEWED / NEEDS_SECOND_REVIEW,
and emits counts by Day 3/Day 4, review-window origin, scene class,
evidence usability and camera-reference validity. The reported diagnostic
combinations (e.g. displaced and invalid reference; normal-looking usable
and valid reference; visual degradation but evidence marked usable) are
questions for follow-up, **not automatically confirmed causal labels**.
If a formally complete 22/22 review is required, append
--require-complete to fail on any pending or second-review case; unresolved
cases can also be reported without that flag.

The JSON intentionally omits individual case IDs, the video's content,
and all free-text notes. SHA-256 hashes of the original queue and decisions
identify the numeric aggregate's inputs. Sharing the aggregate JSON is safer
than uploading private footage or potentially identifiable reviewer notes.

This small, intentionally failure-enriched review is not an independent
precision or recall benchmark. It cannot justify automatic baseline resets,
camera-tampering enforcement, withholding attendance or production integration.


## Phase 3D reviewed-case quality audit and visibility/ref separation

After 22 of 22 targeted cases were saved, the initial reviewer aggregate had
the following *reviewer-supplied* values:
- Day 3: all 11 scene descriptions were visibility_degraded, but 7 cases
  marked the visual evidence usable and 4 marked it unusable.
- Day 4: 10 of 11 marked unchanged_scene, and those 10 marked the evidence
  unusable; one degraded scene was marked usable.
- All 22 selected valid reference=yes, and all 22 lacked explanation notes.

These are not necessarily contradictory: a stationary camera can be dark or
blurred, and degraded footage can still support narrower visual tasks.
However, the evidence is **not sufficient to certify a camera reference**,
and no external reviewer or approved reference comparison is documented.
Do not reinterpret yes reference labels as independent validation.

Optional quality audit using the saved categorical CSV *without re-reviewing
or opening video*:

    $trial = "C:\Users\Admin\Desktop\KaushalWatch-camera-trial"
    $review = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3d\guarded-v2\extended\manual-review"
    python "$trial\scripts\audit_uhctd_manual_review_quality.py" --reviews "$review\local_review_decisions.csv" --out "$review\quality-audit"

The resulting review_quality_audit.json contains only aggregate counts,
classification-coherence hypotheses, the input hash, and hard limitations.
An **optional**, capped local CSV contains clarification examples of unchanged
but unusable, degraded but usable, and degraded/unusable scenes; blanks ask
whether an approved independent reference was actually compared and what
observation was (or was not) possible. It never modifies the original 22
decisions, promotes any evidence to ground truth, or exports reviewer notes.

Further camera-trust implementation should separate at least these concepts:
1. Image/scene evidence usability: can the intended activity be verified?
2. Camera viewpoint change: has an independently trusted scene reference
   changed, with sufficient texture and lighting controls?
3. Reference provenance/approval: is the comparator still approved?
4. Human review status: unknown and ambiguous cases require abstention,
   not punitive automated conclusions.

No current reviewer aggregate changes the full-day false-review measurements.
Independent blinded camera/site evaluation remains required for production.


## Phase 3E foundation — three independent camera-evidence axes

The 22 manual review decisions were saved and aggregated, with 12 marked
visibility_degraded, 10 unchanged_scene, 14 marked evidence unusable, and
all 22 marked reference_still_valid=yes. Those judgments are informative
but cannot establish independent provenance. In particular, 10 Day 4
unchanged scenes were marked unusable, and eight visibility-degraded
scenes were marked usable. This shows why stability, activity-verifiability
and reference approval must NOT be conflated.

The next engineering foundation is implemented as two **shadow-only**
pure service modules:

- backend/app/services/camera_reference_lifecycle_shadow.py:
  An explicit workflow with UNENROLLED, PENDING_REVIEW, APPROVED,
  SUSPENDED and REVOKED states. New references require a named proposer,
  lowercase SHA-256 fingerprint, capture ID, reviewed source ID and
  timezone-aware event timestamp; approval requires a different actor,
  a new independent review ID, and three affirmative verified-health/
  unchanged-view/independent-comparison checks. An existing approved
  reference cannot be silently replaced, and suspending it NEVER
  automatically selects a new frame. Each transition records a simple
  in-memory chronological event. This is a policy prototype, not an
  authenticated service, durable datastore or approved audit ledger.
- backend/app/services/camera_evidence_axes_shadow.py:
  Generates three separate advisory outputs (evidence-quality signal,
  structural scene-change review, and reference lifecycle). It does not
  treat CameraTrust.trusted or any no-alert result as independently
  verified scene stability or operational footage usability. The output
  always states camera integrity NOT_DETERMINED and attendance/compliance
  NOT_AUTHORIZED. Low-texture UNKNOWN stays explicitly unknown. Even
  APPROVED in the prototype means the caller claimed human verification;
  external proof and authorization are not established here.

Neither module is wired into released FastAPI endpoints, authentication,
attendance or compliance actions. The underlying 55% spatial detector
and its full-day results are **unchanged**. They remain a failed
operational reliability candidate with 41.04% of Day 3 and 7.01% of Day 4
annotation-normal samples flagged, despite the selected-window result.

Synthetic tests, without any licensed CCTV:

    python -m pytest backend/tests/test_camera_reference_lifecycle_shadow.py backend/tests/test_camera_evidence_axes_shadow.py -q

Production adoption gates, still open:

1. Authenticated and authorized role checks with separate proposer and
   independent approver (the in-memory shadow object does not provide these).
2. Durable database-backed, immutable reference provenance and audit
   trail; custody, reference image/feature capture, camera ID, retention,
   privacy control, concurrency protection and change approval.
3. Explicit semantics for visibility/evidence usability tied to specific
   training tasks, including unknown and partial degradation.
4. A state machine that does not reset baselines on detection alone and
   requires a human adjudication of true vs nuisance scene change.
5. Continuous development benchmark acceptance and then untouched,
   multi-site, blind independent held-out validation.
6. No camera tampering allegations, sanctions, attendance modifications,
   or automatic compliance outcomes while shadow-only.

Status: engineering foundation, NOT released Camera Trust 2.0.
