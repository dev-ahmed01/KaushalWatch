# Milestone 3 — Operational attendance inference trace

This tool captures **actual observations from the existing attendance pipeline**, not a separate detector-only code path. It is a stronger reproducibility check than the [raw-frame detector trace](attendance-inference-trace.md), but it remains limited to attendance and must not be presented as a whole-platform compliance benchmark.

## What it actually observes

The optional `observation_sink` in `VideoCompliancePipeline.run` receives one privacy-safe dictionary per pipeline-sampled frame, including frame number, decoded-frame SHA-256, camera trust, detector eligibility, raw/candidate/confirmed/registered/smoothed counts and **eligible sample mismatch**. It never exports video pixels, person coordinates, overlay boxes or track IDs. Samples are considered scorable only after registration warmup, with authoritative model availability and a trusted camera.

The recorder runs that *same existing pipeline* on the exact frozen attendance clip. Any privacy-blurred evidence temporarily produced during this isolated evaluation run is destroyed at the end of the run. Only the receipt JSON is saved.

## Local run with real frozen footage and OpenVINO

Create independent occupancy labels with `sample_id`, `frame_index` (zero-based), `true_count`, `pred_count`, `true_issue`, `pred_issue` columns. Label ground truth without looking at predictions. Select frame positions aligned to the configured `sample_every_seconds` interval **after the registration warmup**, and where the camera is reliable. `pred_count` in this mode must correspond to the **smoothed operational count**, while `pred_issue` is the **per-sample eligible mismatch flag**, not the eventual case review verdict. This dataset must not be used to imply independently validated case-level sensitivity.

Freeze the CSV with its SHA-256 and rerun `scripts/verify_release_assets.py`. Set the model as in the final-media guide, then capture:

```powershell
$env:KAUSHALWATCH_PERSON_DETECTOR="openvino"
python evaluation/capture_operational_attendance.py `
  --asset-manifest demo/release-assets.local.json `
  --attendance data/annotations/attendance.csv `
  --reported-attendance 12 `
  --sample-every-seconds 0.2 `
  --count-source registered `
  --smoother-window 5 `
  --out evaluation/output/final-demo/operational-attendance.json
```

**Use the actual independently documented reported attendance**, not necessarily `12` (which is illustrative), and preserve the evidence of how it was obtained. Confirm the chosen count source/window matches the target runtime configuration; they are recorded in the receipt. The sample schedule, source video, model XML/BIN, active profile and all relevant SHA hashes are captured.

To validate against the full scorecard:

```powershell
python evaluation/evaluate_final_demo.py `
  --final `
  --asset-manifest demo/release-assets.local.json `
  --operational-attendance-receipt evaluation/output/final-demo/operational-attendance.json `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

A supplied attendance sample is **rejected** if it was captured during registration warmup, an untrusted camera state or detector-unavailable run. It also fails if it is not a true pipeline sampling position, if a decoded frame or model file has changed, or if `pred_count` or per-sample `pred_issue` does not match the operational output.

The output's `attendance_pipeline_trace` contains the strict receipt match status, sampled count and model/configuration hashes. `prediction_source_verified` stays `false` globally: there are additional prediction columns, other modalities, unverified external attendance data, and unsigned local receipts.

**Do not pass both** `--attendance-receipt` (raw detector) and `--operational-attendance-receipt` in a single scorecard. These refer to different count semantics.

## Qualification boundaries

- This records output from the actual temporal attendance engine; it does not establish **independent manual ground-truth accuracy**, quality of camera-trust decisions or proof that an external scheme recorded the reported count correctly.
- The per-sample mismatch flag is **not** the final temporal case-level decision or human officer disposition. Final case-level TP/FP/FN/TN still needs its own ground-truth opportunities and genuine inference source.
- All receipts are unsigned local JSON. This verifies internal consistency and file identity, not adversarial authenticity; independent review of the command outputs and a reproducible rerun are necessary.
- Synthetic CI detector receipts say `synthetic_test_only`; they are **not** qualifying model measurements. Test suites separately exercise receipt validation using fabricated mock model files and data with explicit test-only scope.
- Real final footage remains outside Git. No accuracy metric should be cited until the exact local video, calibrated model and independent labels are captured and evaluated together.
