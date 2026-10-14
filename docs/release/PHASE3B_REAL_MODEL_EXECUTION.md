# Phase 3B — Real Model Execution and Cross-Pipeline Diagnostics

**Date:** 14 October 2026
**Repository:** `dev-ahmed01/KaushalWatch`
**Branch:** `main`, latest actual-model implementation commit `3eb0102d5ab3f2f7467582857d46c65967b3e860`
**Scope:** real, public-source executable model checks; *not* controlled training-centre held-out qualification.

## 1. Reproducible OpenVINO person benchmark: real annotated footage

[Actual OpenVINO benchmark run #38606324935](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38606324935)
downloaded and verified the Open Model Zoo FP16 `person-detection-retail-0013`
model and the EPFL Laboratory Camera 0 public research video and annotations.
The benchmark processed **113 actual annotated frames** at IoU 0.50,
confidence 0.45, and 25-frame sampling.

| Detector | Person precision | Person recall | Person F1 | Occupancy MAE |
| --- | ---: | ---: | ---: | ---: |
| OpenVINO person-detection-retail-0013 | 91.45% | 89.95% | 90.69% | 0.327 |
| OpenCV HOG baseline (non-authoritative fallback) | 43.82% | 9.11% | 15.09% | 3.000 |

OpenVINO confusion counts: **385 TP, 36 FP, 43 FN**. The public-dataset
result matches the historical stored result and establishes a real-model
regression baseline, not independent generalization to government centres.
Original EPFL terms/research dataset credit remain applicable. The
workflow uploads the metrics and comparison as a short-lived GitHub artifact
but does not commit videos or labels.

## 2. GroundingDINO: real offline model adapter, not mocked inference

[Actual model run #38606324722](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38606324722)
and [pinned reproducibility rerun #38607088769](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38607088769)
both completed successfully.

`scripts/smoke_live_grounding_adapter.py` downloads a permitted public
workroom image and the exact GroundingDINO Tiny repository revision
`a2bb814dd30d776dcf7e30523b00659f4f141c71`, copies only acceptable
processor/tokenizer/config/checkpoint files into a private temporary model
folder, and SHA-256 pins **all nine model files**. It then sets offline
mode, loads them through the released
`app.services.live_equipment.GroundingDinoAdapter`, and runs actual CPU
inference with no model mocking.

The run returned **two workbench proposals and zero chair proposals**
on the public image, at the smoke threshold of 0.35. This is **not**
ground-truth accuracy: no independent item labels or detection-box review
were provided. A separate historical GroundingDINO smoke script produced
six generic proposals using its own multi-label prompt strategy and is
not directly comparable to the two-class live-adapter counts.

The real adapter is **opt-in**, not automatically promoted to an
officer-verified equipment-compliance decision. Missing weights, mutable
snapshots, bad boxes, inference failures and changed videos must fail
closed rather than inventing a zero count. The model license, public test
image attribution and downstream usage rights must be independently
checked before redistribution or production deployment.

## 3. OpenVINO inside the actual attendance and practical pipeline

[Cross-pipeline real inference run #38607088793](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38607088793)
runs `scripts/run_real_public_video_pipeline.py` after the full annotated
benchmark. It extracts a disposable six-second clip from the public
EPFL lab camera and uses the frozen vision profile with tiled CPU OpenVINO
(person threshold 0.45, tile overlap 0.18, NMS 0.45).
It executes both production
`VideoCompliancePipeline` and `PracticalActivityPipeline` through the
actual `assess_camera` quality gate. No mocked detector is used.
The source, model XML/BIN and profile are SHA-256 recorded in the uploaded
JSON diagnostic. Raw clip and anonymized temporary case frames are deleted
when the command exits; they are not uploaded to the repository or CI artifacts.

| Diagnostic field | Observed |
| --- | --- |
| Detector backend | OpenVINO, authoritative in both pipelines |
| Sampled frames | 30 attendance; 30 practical |
| Detector runtime errors | Zero in both |
| Camera trust usable ratio | 1.0 in both |
| Short-excerpt occupancy estimate | 0 |
| Synthetic reported attendance | 3 — **not an official register** |
| Attendance output | `attendance_exception` — **diagnostic only** |
| Practical authorization | `unknown` |
| Practical output | `no_persistent_practical_activity` |
| Active work cells | 0 |

Interpret carefully: the public six-second laboratory excerpt is not
labelled for trainee authorization, worker skills or practical activity.
An attendance mismatch with an intentionally arbitrary synthetic register
is **not** proof of fraudulent attendance. The zero occupancy estimate
on a short clip could reflect camera entry dynamics, track warmup or other
model/temporal behavior; it is not promoted as ground truth or an accuracy
pass. A subsequent labelled temporal/scene diagnostic should inspect these
cases without tuning the frozen profile against final held-out footage.

## Reproduce

Both workflows are normally manual but run automatically when their own
workflow, adapter or benchmark implementation changes on main:

- `.github/workflows/vision-benchmark.yml`: download public data and
  OpenVINO model, compare detector baselines and run the full-pipeline
  diagnostic, then upload a redacted JSON/CSV benchmark artifact.
- `.github/workflows/grounding-smoke.yml`: install optional CPU model
  dependencies, run existing image smoke and the SHA-pinned local live
  adapter, then upload a small JSON artifact.

Do not commit model weights, private CCTV, raw identity data, auth tokens,
independent annotations or actual evidence frames.

## Remaining release qualification — all unverified

1. New, authorized, independently labelled multi-centre videos for frozen
   held-out attendance counting and case decisions, including negatives,
   low light, occlusions, arrivals, departures and camera failures.
2. Frozen practical-activity ground truth, independent work-zone geometry
   and externally verified authorization states, not laboratory walking.
3. New independent, never-inspected camera-obstruction/defocus/movement
   recordings; UHCTD Day 3 and Day 4 are development data, not untouched
   candidate holdouts.
4. Equipment-specific count **and localization** annotations for a frozen
   production-approved model/snapshot, not a single public image.
5. Actual multi-camera apparent-motion and abstention evaluation, without
   claiming mechanically/electrically certified equipment health.
6. Government/operator staging: real IdP/MFA, private S3/KMS/IAM,
   officer-grant lifecycle, high availability, backup/restore and
   human-approved release review.

**Phase 3B achieved:** actual models were executed reproducibly on
public test media and the real inference paths were exercised.

**Not achieved:** independently qualified KaushalWatch performance or
authorization to operate on real training-centre data.
