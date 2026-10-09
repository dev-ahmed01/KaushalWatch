# Milestone 3 — Apparent-operability ROI motion provenance

**Purpose:** tie a final evaluation row to the exact source video and the **same visible-motion algorithm used by the infrastructure evidence pipeline**, with transparent uncertainty. Apparent activity is **not** equipment health, electrical/mechanical readiness, or proof of safe operation.

## The source-of-truth calculation

`backend/app/services/operability.py:trace_apparent_motion` now provides one shared sampling and scoring function. The infrastructure case pipeline calls it when requested; the independent evaluator uses the *same* function even when no infrastructure-compliance case exists. This avoids erroneously dropping a healthy scene merely because there was no equipment discrepancy.

The tool validates the manifest SHA, operability video digest, centred/batch-linked annotation file, bounded ROI, stable start/end times, known camera cuts, detection item ID, numeric threshold, and frame cap. The pixel-frame contents are never written to the receipt; only actual decoded frame SHA-256 values, frame indices, requested sampling times, ROI bounds, score, and final `APPARENTLY_ACTIVE`, `APPARENTLY_INACTIVE`, or `UNCERTAIN` state are retained.

The frame sampler mirrors the product: for a configured stable time window, evenly request `min(max_frames, max(3, int(duration * 2) + 1))` frames; score median of mean Gaussian-blurred grayscale differences between consecutive ROI crops. Fewer than three readable frames abstains as `UNCERTAIN`. It does **not** infer operability from training panel presence alone.

## Freeze one labelled opportunity per ROI/window

In the local `demo/release-assets.local.json` `operability` section, add:

```json
{
  "asset_id": "operability",
  "item_id": "training_panel",
  "roi": {"x1": 650, "y1": 250, "x2": 1500, "y2": 900},
  "window": {"start_sec": 14, "end_sec": 33},
  "camera_cuts": [{"start_sec": 13.3, "end_sec": 13.7}],
  "motion_threshold": 0.8,
  "max_frames": 30
}
```

**These coordinates and timing are examples from the DOD reviewed profile and must match the exact selected clip.** Never copy them to an unrelated video. The manifest verifier rejects windows overlapping declared camera cuts or with invalid ROI dimensions.

The frozen operability annotation CSV uses:

```csv
sample_id,item_id,source_asset_id,centre_id,batch_id,true_state,pred_state
```

For this one frozen ROI/window, provide **exactly one row**. The independently labelled `true_state` must be APPARENTLY_ACTIVE or APPARENTLY_INACTIVE, using a documented human observation rule. The `pred_state` must equal the actual ROI-motion output, or the capture fails; `UNCERTAIN` is a valid abstaining *prediction* but not an independent truth label.

Rehash the independent CSV after editing it; pin its SHA-256 in the asset manifest before capturing.

## Operator commands (PowerShell)

```powershell
python scripts/verify_release_assets.py --manifest demo/release-assets.local.json

python evaluation/operability_motion_trace.py `
  --asset-manifest demo/release-assets.local.json `
  --operability data/annotations/operability.csv `
  --out evaluation/output/final-demo/operability-receipt.json

python evaluation/evaluate_final_demo.py `
  --final --asset-manifest demo/release-assets.local.json `
  --operability-receipt evaluation/output/final-demo/operability-receipt.json `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

The final scorecard independently **replays** the ROI decoder and motion algorithm and compares the entire receipt, including the selected decoded frame SHA-256 values. A changed clip, shifted ROI/window, altered threshold, duplicate opportunity, swapped annotation, fabricated state, or edited receipt aborts output.

The resulting `operability_motion_trace` records the verified activity proxy and `mechanical_health_verified=false`. `prediction_source_verified` still remains `false` for the **overall** report: neither the OpenVINO attendance detector, the reviewed GroundingDINO cache, nor this pixel-motion proxy establishes accuracy for other independently labelled modalities.

## Acceptance and limits

- CI uses entirely synthetic videos, including still and changing ROI samples. Passing tests establishes reproducibility of code paths, not external validity of activity detection.
- Visually moving hands at a trainer board can support an *apparent interaction* observation, but cannot prove equipment's circuit health, power supply, sanctioned quantity, or actual functioning.
- A single ROI/window is one opportunity, not a representative sample population. To report meaningful active/inactive/uncertain coverage or estimated accuracy, freeze multiple independently labelled *videos/windows* with separate reviewed manifests and receipts; do not duplicate one case as multiple opportunities.
- Stage footage, reviewer-supplied truth labels and real demo-machine parameter freeze are **still pending**.

See [final media freeze](final-media-freeze.md), [equipment cache trace](equipment-cache-trace.md), [frozen scorecards](frozen-scorecards.md), and the [release tracker](SIH_MVP_TRACKER.md).
