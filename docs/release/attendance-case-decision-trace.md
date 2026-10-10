# Milestone 3 — One case-level attendance decision, tied to the whole video

This release gate verifies **one explicitly mapped** `attendance_discrepancy` opportunity against the existing attendance engine's **full-video temporal decision**, not just an isolated frame.

## Why this gate exists

A single detected-person count is not a compliance case. The backend only raises an attendance case after camera trust, confirmation/registration, count smoothing, an estimated median occupancy, mismatch threshold and sustained-persistence threshold. A camera with insufficient trusted observations is **not a negative attendance decision**.

The operational receipt now includes a privacy-safe `decision_timeline` of *all pipeline-sampled frames*, recording warmup/trust status, eligible count stages and persistence mismatch flags. It includes no image pixels, bounding boxes, faces or track IDs. The verifier checks that every sampled step has a valid sequence, computes the trusted frame ratio and mismatch persistence, and independently recomputes the count median and final attendance decision. The receipt remains **unsigned** and cannot prove the camera trust labels or model output were not altered by a malicious operator.

## Freeze an explicit attendance case opportunity

Your frozen `cases.csv` must keep `sample_id,case_type,true_issue,pred_issue` and **add** these four fields:

```csv
sample_id,case_type,true_issue,pred_issue,source_asset_id,centre_id,batch_id,reported_attendance
```

For the specific attendance video under review, include exactly one row with:

- `sample_id`: a stable review opportunity ID, e.g. `ATT-CASE-FINAL-01`.
- `case_type`: `attendance_discrepancy`.
- `true_issue`: a separately reviewed **true or false** attendance discrepancy label (not copied from the model).
- `pred_issue`: the final backend's `attendance_exception` decision represented as **true**, or `compliant` as **false**.
- `source_asset_id`: the exact ID of the frozen **attendance** clip.
- `centre_id`, `batch_id`, `reported_attendance`: exactly the values for that frozen clip and the documented external count record.

Keep both actual positive and negative *opportunities* across the full cases CSV. A single video's case decision may only support **one** row; do not invent numerous independent examples from frames of the same recording. Update the cases CSV SHA-256 in the frozen manifest before recording a new operational receipt. All other case types and rows remain unverified unless separately traced and annotated.

## Operator commands

Capture the full operational timeline using the exact final clip and explicit OpenVINO:

```powershell
$env:KAUSHALWATCH_PERSON_DETECTOR="openvino"
python evaluation/capture_operational_attendance.py `
  --asset-manifest demo/release-assets.local.json `
  --attendance data/annotations/attendance.csv `
  --reported-attendance 12 `
  --out evaluation/output/final-demo/operational-attendance.json
```

**12 is illustrative only.** Use the actual externally evidenced attendance count for your chosen demo scene. The `reported_attendance` field in `cases.csv` must equal this runtime value.

Score the single mapped case with the frozen annotations and all other source files present:

```powershell
python evaluation/evaluate_final_demo.py `
  --final --asset-manifest demo/release-assets.local.json `
  --operational-attendance-receipt evaluation/output/final-demo/operational-attendance.json `
  --attendance-case-sample-id ATT-CASE-FINAL-01 `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

The scorer refuses ambiguous/missing case IDs, changed scenario/media/annotations, mismatched centre/batch/source or reported count, an inconsistent full-video timeline, a changed model file, unsupported fallback, and disagreeing final case predictions. It refuses a camera-insufficient clip **as an attendance negative**, instead of silently counting it as compliant.

The JSON `attendance_case_trace` confirms the *one* matched row, source SHA-256, timeline length, final decision and independently supplied truth label. The receipt does not make `prediction_source_verified` true for the **entire** scorecard: other case rows, equipment counts, apparent operability and practical authorization have not been tied to actual inference logs.

## Remaining limits

The CI tests use only synthetic video/detectors, including deliberately fabricated *test-only* model paths. Passing those tests is integration evidence, **not** real-world model accuracy or operator authentication.

A source-aligned final attendance case is still **only one evaluation opportunity**. It does not justify generalizing the TP/FP/FN/TN rate across training centres. Camera insufficiency needs its own independently annotated case opportunities, including both genuine tampering and benign environmental changes, before promotion.

See [operational attendance trace](operational-attendance-trace.md), [frozen scorecards](frozen-scorecards.md) and [SIH MVP tracker](SIH_MVP_TRACKER.md).
