# Vision profile and dataset promotion workflow

KaushalWatch now separates **product logic** from **camera/dataset calibration**.

The active vision contract is:

`configs/vision_profiles/kaushalwatch-fixed-camera-v1.json`

It records the detector, attendance temporal settings, practical-work geometry policy, camera-trust thresholds, infrastructure adapter, operability claim boundary, and currently verified benchmark provenance.

## Why this exists

A better CCTV dataset should improve the vision layer without forcing a frontend/API rewrite. The product consumes stable concepts:

- anonymous occupancy
- trusted practical activity
- camera-verifiable infrastructure
- apparent visual activity
- camera trust
- retained evidence + human review

Dataset-specific thresholds and geometry live in a **vision profile**.

## Adding a better dataset later

Do not replace the frozen profile immediately.

1. Copy `configs/datasets/training-centre-candidate.template.json`.
2. Give the dataset a unique `dataset_id`.
3. Record licensing/consent/redistribution constraints.
4. Use only fixed-camera scenes for this profile.
5. Create separate **calibration** and **held-out** splits.
6. Add ground truth only for claims the dataset can actually support.
7. Validate the manifest:

```powershell
python scripts/validate_vision_profile.py --dataset configs/datasets/<candidate>.json --strict-candidate
```

## Attendance tuning

Calibration can use:

```powershell
python scripts/calibrate_attendance_detector.py --video <calibration-video> --true-count <count>
```

For changing occupancy over time, use timestamped manual counts:

```powershell
python scripts/evaluate_dynamic_attendance.py --video <held-out-video> --manual-csv <counts.csv>
```

Never tune using the held-out split.

## Practical activity

Each fixed camera needs a work-zone definition. Existing zone coordinates are transferable only when the same camera geometry is resized; they must not be reused for a different viewpoint.

Ground truth should distinguish:

- worker present in work cell
- sustained visible interaction/activity
- authorized/unauthorized state supplied externally

Do not label individual productivity or skill quality from video.

## Infrastructure

Open-vocabulary detections remain proposals until reviewed. For a promoted dataset/profile, record:

- equipment class
- reviewed count/presence at sampled timestamps
- false-positive/false-negative annotations
- the exact source video digest
- the job-role manifest version

Required numeric quantities must remain marked simulated unless an authoritative source supplies them.

## Apparent operability

The current method is an ROI motion proxy. Evaluation may establish whether visible interaction is present, but it cannot establish mechanical/electrical health.

Allowed language:

- APPARENTLY ACTIVE
- APPARENTLY INACTIVE
- UNCERTAIN
- OFFICER VERIFICATION REQUIRED

## Camera trust

Candidate footage should include or annotate representative trust failures where possible:

- blur
- darkness
- frozen/replayed stream
- camera viewpoint shift/obstruction

When camera trust fails, dependent visual conclusions remain suspended.

## Promotion rule

A candidate profile is promoted only after:

1. calibration is complete,
2. settings are frozen,
3. held-out evaluation is run,
4. claimed metrics are compared with the current frozen profile,
5. any regression/trade-off is documented,
6. privacy and claim boundaries remain intact.

Then launch with:

```powershell
$env:KAUSHALWATCH_VISION_PROFILE="configs/vision_profiles/<new-profile>.json"
```

Runtime Readiness and `/api/vision/governance` expose whether the running detector/settings match the selected profile.

A profile being **aligned** means configuration matches the frozen contract. It does not mean the model is universally accurate.
