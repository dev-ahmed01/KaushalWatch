# Milestone 3 — Equipment cache-to-scorecard provenance

This phase introduces a **reviewed-cache receipt**, rather than pretending that the final-stage equipment cache is a fresh AI inference result. The product's reviewed DOD source contains GroundingDINO proposals plus separately approved human corrections. A report must keep these two channels distinct.

## Data contract

The SHA-frozen equipment CSV must include an explicit `second` column in addition to `sample_id,item_id,true_count,pred_count`:

```csv
sample_id,item_id,second,true_count,pred_count
DOD-00,training_panel,0.0,1,1
DOD-00,drill_machine,0.0,0,0
```

These are format illustrations only, **not measured evaluation data**. Every pair `(second,item_id)` must match *exactly one* equipment detection in the reviewed cache. A `sample_id` must resolve to one timestamp, and every `(sample_id,item_id)` must occur at most once. Missing detection entries are **not** silently interpreted as count zero.

Populate `true_count` from a reviewer **independent of the person who corrected the model proposals**. Merely labeling the cache values as truth is invalid. Update the frozen equipment CSV SHA-256 in `demo/release-assets.local.json` before capture.

## Two scoring bases

**Option A — Model proposals:** the CSV's `pred_count` must equal the cache's `model_count`, i.e. the preserved original GroundingDINO proposal count **before** review. This checks cached proposal values against independently labelled counts. It does not establish model weights or a fresh reproducible inference run.

**Option B — Human-reviewed counts:** the CSV's `pred_count` must equal the cache's corrected `count`, and every referenced item must retain its `review_status` and per-item review metadata. This measures *human-assisted output*, not model-only accuracy. Human-corrected results may be higher than the original model proposals and must not be described as detector-only precision.

Both modes are linked to the source clip, reviewed cache and review metadata by exact SHA-256 hashes. A cache sample also must carry the `groundingdino_human_reviewed` source marker. The file gate rejects unverified statuses or missing review metadata rather than accepting optimistic counts.

## Commands

From the repository root, after qualifying the actual local video and full release manifest:

```powershell
python scripts/verify_release_assets.py --manifest demo/release-assets.local.json

# Proposal-only counts from cached original model output:
python evaluation/equipment_cache_trace.py `
  --asset-manifest demo/release-assets.local.json `
  --equipment data/annotations/equipment.csv `
  --basis model_proposal `
  --out evaluation/output/final-demo/equipment-cache-receipt.json
```

For **human-assisted** scoring, change `--basis` to `human_reviewed`, correct the CSV prediction counts accordingly, update its SHA in the local manifest, then regenerate the receipt.

Pass the resulting receipt to the final scorer alongside all four actual frozen CSVs:

```powershell
python evaluation/evaluate_final_demo.py `
  --final --asset-manifest demo/release-assets.local.json `
  --equipment-receipt evaluation/output/final-demo/equipment-cache-receipt.json `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

Final evaluation rechecks the manifest, every source digest, per-sample timestamps, item IDs, model/reviewer count basis and the complete receipt. If the receipt was altered, the model proposal count is missing, the annotation changes, the source cache is replaced, or the CSV combines reviewed and raw counts, the report fails before being produced.

The scorecard's `equipment_cache_trace` says whether the model-proposal or human-reviewed count field was scored. `model_inference_execution_verified=false` and `prediction_source_verified=false` remain intentional.

## Limitations and Milestone 3 acceptance

- This is **cached detection/review value traceability**, **not** a run of GroundingDINO on the target machine. The frozen metadata records `model_id`, threshold and original video source, but the receipt does not attest to weights, inference logs, or preprocessing.
- The metadata's human-review claims are an attestation of review activity, not an independent accuracy label. For a formal model-only benchmark, preserve uncorrected proposal outputs, exact weights/configuration, and separately created labels.
- Counts alone cannot evaluate **bounding-box localisation**. Any TP/FP/FN reported here is *count-derived*, as the existing evaluator explicitly notes.
- Required sanctioned equipment quantities are simulated unless official item-by-item requirements are sourced. A model finding an object cannot independently prove regulatory noncompliance.
- Case-level equipment exceptions, apparent-operability and practical activity remain separate inference/label workflows.

The bundled DOD cache is a useful reviewed demonstration artefact; final licensed local footage and independent held-out annotations still need to be validated. See [final media freeze](final-media-freeze.md), [frozen scorecards](frozen-scorecards.md), and [release tracker](SIH_MVP_TRACKER.md).
