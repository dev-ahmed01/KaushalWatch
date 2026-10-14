# Phase 2A — Independent camera evidence-usability qualification

**Implementation:** `evaluation/camera_evidence_holdout.py` on
`release/kaushalwatch-sih-mvp`. This is one part of the real-footage
qualification program, **not** full system accuracy acceptance.

## Scientific claim boundary

The currently released `assess_camera` returns a `trusted` indicator
based on darkness, blur, image similarity and reference scene shift.
The scorer measures **whether the system appropriately withholds
camera-dependent evidence**. It **cannot** determine whether an actual
operator maliciously moved or covered the camera, detect digitally replayed
video reliably, or confirm that someone is working productively. Human
review is still required.

PR #54 includes a *different, not yet validated* camera candidate. This
phase does not merge PR #54 or claim its measurements. The Day 3 and Day 4
UHCTD recordings already influenced Camera Trust development; **Day 4
Camera B must not be called untouched held-out footage**. Use Day 3/Day 4
only for retrospective exploratory error analysis, not to pass this gate.
Choose new independent recordings which have not affected any threshold,
implementation or model selection.

## Data required (kept off GitHub)

For each recording supply a fixed-camera video and a full-frame UHCTD-style
CSV **without a header**. Each row has the one-based frame index, class code,
and three further columns. The evaluation uses only the first two; class
codes are `0=normal, 1=covered, 2=defocused, 3=moved`. The annotations
must have exactly one contiguous row for every frame in the video, with no
duplicates, missing labels or skipped frames.

Create `data/annotations/camera-holdout.json` with:

- `schema_version: 1`, unique `protocol_id`, `status: "frozen"`,
  `fixture_only: false` and an exact copy of
  `evaluation/camera_evidence_holdout.py::POLICY`.
- `vision_profile`: `{"path":"../../configs/vision_profiles/kaushalwatch-fixed-camera-v1.json","sha256":"<real lowercase SHA-256>"}`.
  The selected runtime profile must resolve to that exact path and digest.
- `calibration`: at least one separate video, with stable `recording_id`,
  `scene_id`, `camera_id`, `site_id`, `source_origin`,
  `license_basis`, `privacy_basis`, and `video` as a SHA-pinned file.
- `heldout`: at least **two different cameras/recordings**, unique video
  digests and IDs not used in calibration. Each requires the same metadata,
  its SHA-pinned `annotations`, a `reviewer_id`,
  `blinded_review: true`, and `previously_inspected: false`.
  At least **15 seconds of normal footage** and **two independently
  preceded events of each abnormal class** must be present in total; each
  scored event needs at least two seconds of normal lead-in.

The manifest and every source are hashed before analysis and rechecked after.
Independent annotation and uninspected status remain operator attestations:
SHA-256 can protect the frozen file, but cannot prove a human never viewed
its data. Keep provenance and reviewer evidence separately under approved
privacy controls; do not commit sensitive clips or identifying labels.

## Running on your Windows workstation

Once a newly untouched video and its annotations are prepared:

```powershell
cd C:\Users\Admin\Desktop\KaushalWatch
.\.venv\Scripts\python.exe evaluation\camera_evidence_holdout.py --manifest data\annotations\camera-holdout.json --check-inputs --out evaluation\output\camera-inputs-check.json
.\.venv\Scripts\python.exe evaluation\camera_evidence_holdout.py --manifest data\annotations\camera-holdout.json --out evaluation\output\camera-heldout-report.json
```

The **input check** can only return `inputs_pinned_no_inference`; it never
claims accuracy. The scorer calls the **current release's actual**
`assess_camera` gate at a frozen 0.2-second cadence, using its initial
reference frame and previous sampled frame, aligned with the attendance
pipeline. It reports false-untrusted normal samples, false-alarm episodes
per normal hour, genuine **new** alert onsets during labelled events,
per-class event recall and detection delay. An alert that was already active
at an event's onset **does not** count as a fresh detection.

The provisional engineering gates (not government/PMKVY thresholds) are:

| Measure | Threshold |
| --- | --- |
| Fresh event detection recall | >= 85% |
| Fresh recall within each class | >= 75% |
| Normal footage falsely marked untrusted | <= 5% |
| New false-alarm episodes per normal hour | <= 2 |
| 95th percentile delay for newly detected events | <= 5 seconds |
| Independent held-out cameras | >= 2 |
| Class support | >= 2 events each: covered, defocused, moved |

Coverage and positive/negative support are checked before scoring. A gate
cannot be passed using generated CI fixtures or with missing annotations.
**A high recall with a large false-alarm rate is NOT acceptable.**

### Failure output

The evaluator writes a non-person-identifying JSON scorecard, returns exit
code **2** for invalid/failed qualification, and never produces a positive
result for a `fixture_only: true` recording.

## What is NOT yet established

- No newly untouched, legally usable Camera Trust recordings are stored
  in this GitHub repository. The existing user's large UHCTD Day 3/Day 4
  recordings are on their local Windows computer, not accessible by CI.
- The **attendance** system has a distinct held-out gate:
  `evaluation/heldout_qualification.py`. It too needs pinned videos, real
  OpenVINO model and independent count annotations.
- Practical activity, equipment inventory and apparent equipment movement
  do not yet have comparable independently verified release-pass evidence.
  The final demo CSV scorer alone cannot establish prediction provenance.
- PR #54 Camera Trust is still an unvalidated **experimental candidate**.
  Reevaluate it only with fresh unseen footage, under a separate protocol.

Do not merge unvalidated Camera Trust behavior or make full product readiness
claims based on this newly added evaluation infrastructure.
