# Milestone 3 — Practical-work decision trace (frozen video)

This phase connects **the actual practical-activity engine** to the frozen evaluation dataset. It is an engineering reproducibility gate, not a benchmark measured on the final stage footage.

The operational path uses fixed-camera trust, an authoritative person detector, anonymous short-lived centroid tracks, persistence-based worker registration, configured work zones, worker-local motion, temporal activity gates, and an **external** work authorization input. Video alone cannot establish who is present or whether they are authorized.

## What the new receipt records

`PracticalActivityPipeline.run(observation_sink=...)` optionally publishes a privacy-safe observation per actually sampled frame: frame index, timestamp, decoded-frame SHA-256, camera trust and reasons, detector availability, anonymous registered worker count, configured active-zone IDs and sustained-motion activity flag. The receipt additionally captures the complete pipeline's final decision, case type, peak stable worker count, trusted-frame ratio, persistent-activity fraction, first activity time and active work-cell count.

**No pixels, bounding boxes, track IDs, faces, names or person identifiers** are written into the receipt. A temporary directory holds any privacy-processed evidence created by the isolated evaluation run and is deleted when that run completes.

## Freeze external authorization as an independently reviewable input

The existing `demo/release-assets.local.json` must freeze the practical clip and the following practical configuration, with actual SHA-256 digests:

```json
{
  "asset_id": "practical",
  "authorization": "absent",
  "authorization_evidence": {
    "path": "../data/reviewed/external-work-authorization.json",
    "sha256": "<actual SHA-256>"
  },
  "zone_profile": "unauthorized",
  "zone_config": {
    "path": "../data/reviewed/work-zones.json",
    "sha256": "<actual SHA-256>"
  },
  "pipeline_parameters": {
    "sample_every_seconds": 0.2,
    "confirmation_seconds": 1.0,
    "registration_seconds": 2.0,
    "activity_window_seconds": 1.0,
    "activity_required_ratio": 0.60,
    "motion_threshold": 0.02,
    "minimum_trusted_ratio": 0.5
  }
}
```

The values above are **format illustrations**, not verified for the local stage video. Work zones must have the same camera geometry as the frozen clip; a recorded `_reference` size permits resizing within the same view, not transfer to a different angle. Work zone JSON supports an array under the named profile (or a top-level `zones` list). Both source file bytes and selected profile are checked.

The separate `external-work-authorization.json` document must contain at least:

```json
{
  "record_id": "STAGE-REVIEW-01",
  "source": "operator-reviewed training schedule / work-order register",
  "status": "absent",
  "centre_id": "DEMO-KA-104",
  "batch_id": "ACTUAL-BATCH",
  "reviewed_at": "2026-10-10T10:00:00+05:30"
}
```

This **pins what was asserted and reviewed**, not whether an official government system attests to it. Do not imply live AEBAS/SIDH integration or proof of unauthorized conduct. If the status cannot be established, use `unknown`, which leads to a human review case, not a scored yes/no authorization violation.

## Operator CLI

Use the Python environment with OpenVINO installed and exact model XML/BIN files:

```powershell
$env:KAUSHALWATCH_PERSON_DETECTOR="openvino"

python scripts/verify_release_assets.py `
  --manifest demo/release-assets.local.json

python evaluation/practical_activity_trace.py `
  --asset-manifest demo/release-assets.local.json `
  --out evaluation/output/final-demo/practical-trace.json
```

To link **one** practical `practical_activity_authorization` opportunity to the final scorecard, the frozen `cases.csv` row needs `sample_id,case_type,true_issue,pred_issue,source_asset_id,centre_id,batch_id,authorization`, with exact source and external authorization values. Use one opportunity per whole video—not one per frame—and include separate real negative cases elsewhere.

```powershell
python evaluation/evaluate_final_demo.py `
  --final `
  --asset-manifest demo/release-assets.local.json `
  --practical-receipt evaluation/output/final-demo/practical-trace.json `
  --practical-case-sample-id PRACTICAL-01 `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

The evaluator re-decodes every sampled frame and compares its SHA; checks an exact, complete sampling cadence; matches the frozen model XML/BIN, vision profile, zone geometry, thresholds and external authorization-record SHA; recomputes trusted ratio, persistence, registered worker peak and final decision; and rejects altered or duplicated source opportunities.

**Insufficient camera trust, non-authoritative detector, or detector errors are not valid negative compliance outcomes.** Unknown authorization cannot be counted as a confirmed unauthorized-case positive or negative; review it separately. The report labels `practical_pipeline_trace` and, only with the explicit case mapping, `practical_case_trace`.

## Limitations

- CI uses synthetic video, a fake authoritative-labelled detector *within test mode only*, and fabricated model files for isolated verifier tests. Test-created receipts are marked `synthetic_test_only` and rejected until deliberately simulated for unit testing the downstream verifier.
- The receipt is **unsigned**. Hash verification and replay guard against accidental drift and obvious changes; they do not cryptographically authenticate inference execution, the independent case ground truth, or the claimed authority behind the supplied authorization.
- Motion is evidence of possible practical activity in a configured work zone, **not competency, exact task execution, identity, safety or legal authorization**.
- No real stage-footage scores or generalizable case TP/FP/FN/TN are established until genuine source files, model outputs, independent labels, and nonduplicated negative opportunities are qualified.

See [frozen-scorecards.md](frozen-scorecards.md), [final-media-freeze.md](final-media-freeze.md), and [SIH_MVP_TRACKER.md](SIH_MVP_TRACKER.md).
