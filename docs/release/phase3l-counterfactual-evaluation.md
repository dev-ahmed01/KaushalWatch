# Phase 3L — Full-Recording Counterfactual Camera Gate Evaluation

**Experimental, development-only, draft.** Stacked on Phase 3K (#66),
3J (#65), 3I (#64), 3H (#63), and 3G (#62). Production main is unchanged.

## Findings inherited from actual prior development runs

Day 3 and Day 4 were extensively investigated, so neither is an independent
held-out evaluation. Historic unretrained fusion metrics:

| Metric | Day 3 | Day 4 |
| --- | ---: | ---: |
| Annotated-normal review fraction | 0.410366 | 0.070102 |
| New review episodes per annotated-normal hour | 27.196730 | 14.382874 |
| Fresh moved-event review | 15/24 | 22/24 |

Day 3 normal review carryover and postincident visibility remain a separate
issue from Day 4's shorter, recurrent review episodes. A normal annotation
does NOT independently establish that evidence is unobstructed or usable.

**No new full-day result has been computed** from the user's local videos.
The code here evaluates possible hypotheses without changing released
camera-trust, attendance, compliance or production source references.

## Six frozen shadow candidates

All candidates are Boolean *postprocessing* of the SAME frozen scene-review
cue and its SAME measured diagnostic evidence. They do NOT retrain,
change raw spatial/global detector signals or replace any baseline.

1. frozen_baseline — original raw detector cue, exact comparison anchor.
2. photometric_defer — defer an existing scene cue if the independently
   measured image is compatible with a photometric shift.
3. localized_defer — defer if localized foreground/occlusion is compatible.
4. photometric_or_local_defer — union of hypotheses 2 and 3.
5. coherent_translation_only — retain a sufficient-texture cue only
   when conservative multi-quadrant phase coherence supports translation.
   This may miss covered or defocused events and is expected to be risky.
6. sustained_raw_20s — require 20 seconds of continuously raw-positive
   samples before surfacing a sufficient-texture scene cue. This may
   delay/miss shorter events.

For EVERY candidate, original raw review and UNKNOWN_LOW_TEXTURE evidence
remain recorded; positive raw global fallback during spatial UNKNOWN is
ALWAYS retained. No candidate can introduce new scene-review cues,
reenroll a reference or declare camera evidence usable.

## Evaluation and fail-closed gates

Each full video is decoded once. Every annotated frame is presented to
all candidate scorers (including non-sampled frames for true event
boundaries); the frozen detector observation and structural cause
measurements are computed once per sampled frame, then reused for every
policy. This is not a selected-window experiment or cherry-picked set.

The report includes:
- Raw and candidate annotated-normal review fractions and new review
  episode rates per labelled-normal hour.
- Covered/defocused/moved event counts, fresh alerts after onset,
  preexisting-at-onset alerts, any-review events and maximum delay.
- EXACT start-frame IDs for events detected by the baseline but lost
  by a candidate, **even when overall event counts stay equal**.
- Unknown-quality samples conserved and the candidate count of raw
  review samples that would have been deferred.
- Full vs preview status, reference and input SHA-256, and strict
  baseline accounting checks. A real labelled event with NO sampled
  decoded frame blocks the candidate comparison: it is not counted
  as a legitimately missed event or silently treated as healthy.
- A mandatory false-warning-vs-missed-event gate: losing any baseline
  fresh/any-review event is BLOCKED_KNOWN_EVENT_REGRESSION; no gain is
  NO_OBSERVED_RAW_NORMAL_REVIEW_REDUCTION. A rule with no observed
  event loss and reduced normal warnings is explicitly
  DEVELOPMENT_NO_EVENT_LOSS_OBSERVED_NOT_QUALIFIED, **NOT deployed**.

The two-day comparison script takes TWO full completed JSON reports,
enforces complete recording coverage and distinct source SHA-256,
cross-checks reported raw metrics against the frozen candidate, and
blocks a policy when ANY event detection is lost on either camera/day.
Only consistent two-day gains without observed event loss reach
UNQUALIFIED_DEVELOPMENT_SIGNAL_REQUIRES_INDEPENDENT_VALIDATION.
It NEVER selects a policy to deploy, even for positive results.

### Local research execution — no cloud or identity bypass

The separate Phase 3K local research CLI is extended, without changing
the approved-reference process. For already-authorized local UHCTD
footage, supply a separately selected still from the SAME physical
camera and its verified SHA-256. It does NOT auto-generate one.

Example PowerShell from the Phase 3L checkout:

    $source = "C:\Users\Admin\Desktop\MEVA"
    $video = "$source\video.avi"
    $labels = "$source\annotations-1.csv"
    $reference = "C:\private\day3_same_camera_reference.png"
    $dest = "C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3l"
    $vhash = (Get-FileHash $video -Algorithm SHA256).Hash.ToLowerInvariant()
    $lhash = (Get-FileHash $labels -Algorithm SHA256).Hash.ToLowerInvariant()
    $rhash = (Get-FileHash $reference -Algorithm SHA256).Hash.ToLowerInvariant()

    python scripts/run_phase3k_local_forensics.py --video $video --annotations $labels --reference-image $reference --video-sha256 $vhash --annotations-sha256 $lhash --reference-sha256 $rhash --out "$dest\day3_full.json" --sample-seconds 1 --development-only

Repeat for Day 4 with its OWN physical camera's reference, the Day 4
video.avi/annotations.csv, actual digests and a separate day4_full.json.
Preview first using --preview-seconds 60 and a distinct output file;
a preview will never qualify for the two-day comparison.

    python scripts/compare_phase3l_dual_day.py --day3 "$dest\day3_full.json" --day4 "$dest\day4_full.json" --out "$dest\day3_day4_comparison.json"

No images or personal details are included in reports; output is
aggregated numerical evidence and frame-index event IDs. Never commit
local research videos or private frame files, credentials or manifests.
Users without a verified same-camera frame cannot claim successful
Day 3/Day 4 benchmarking.

The approved-reference Phase 3I replay also includes the counterfactual
comparison if a reviewed private reference is provided and verified.
It remains dependent on staging authorization and private storage.
No shortcut through demo credentials is allowed.

## Interpretation and next gates

These candidate policies are thought experiments and may hide real
incidents. A photometric hypothesis alone cannot prove a harmless
lighting change; a coherent global translation cannot certify that
the camera physically moved. Normal-labelled periods include actual
visibility problems and incident carryover. DO NOT call reduced
annotation-normal review a verified reduction of false alarms.

Before any possible promotion:
- Check all baseline-lost events and all suspicious normal review
  segments with independent blinded human review and physical camera
  provenance; involve a separate annotator.
- Choose **pre-registered** candidate thresholds using development
  footage only, then LOCK the decision before untouched independent
  multi-camera deployment/site tests.
- Independently evaluate evidence usability, false-warning rate, delay,
  recall by event class, recording/runtime stability and operational
  recovery. Avoid auto-reference resets.
- Reconcile stacked draft PRs, secured operator permissions and
  vendor-independent source integrity before shipping any feature.

**Current production qualification: FALSE. None selected for release.**
