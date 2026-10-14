# Milestone 3 — Reproducible final scorecards

This phase links the final evaluation math to the **Milestone 2 frozen local media manifest**. It prevents a metrics report from being silently generated in final mode from unrelated example CSVs, changed annotations or duplicated scoring opportunities.

## Two distinct evaluation modes

**Development / example only** (does not require any real clip):

```powershell
python evaluation/evaluate_final_demo.py `
  --attendance evaluation/final_demo_attendance.example.csv `
  --equipment evaluation/final_demo_equipment.example.csv `
  --operability evaluation/final_demo_operability.example.csv `
  --cases evaluation/final_demo_cases.example.csv `
  --out-dir evaluation/output/example-scorecard
```

The JSON report is labelled `evaluation_mode: development_inputs_not_release_qualified`, `input_provenance: null`, `prediction_source_verified: false`. These outputs are only a computational smoke test. They are **not measured benchmark results** and must not be used as final SIH accuracy claims.

**Frozen final-input scoring** (requires the reviewed, SHA-frozen clips, cache and independently annotated CSVs to exist locally):

```powershell
python scripts/verify_release_assets.py --manifest demo/release-assets.local.json

python evaluation/evaluate_final_demo.py `
  --final `
  --asset-manifest demo/release-assets.local.json `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

The evaluation will **not** create an output directory or report unless the entire asset manifest qualifies, the four CSV paths match their registered paths, their actual hashes match, and the scoring rows pass validation.

The emitted `final_demo_report.json` contains `evaluation_mode: frozen_input_scorecard`, the manifest SHA, scenario SHA, source video SHA per role, annotation CSV hashes, sample counts and positive/negative case support. `prediction_source_verified` deliberately remains **false** because a supplied `pred_count`, `pred_issue`, or `pred_state` column does not prove it came from a specific live model run.

### What final mode rejects

- Missing/unqualified demo clips, unpinned or changed source files, example CSV substitutions, missing independent-label attestation, or a mismatched reviewed equipment cache.
- The same scoring opportunity repeated twice. For attendance the key is `sample_id`; for equipment/operability it is `(sample_id,item_id)`; for case decisions it is `(sample_id,case_type)`.
- Missing columns, empty cells, negative or non-integer counts, values such as `unknown` or `maybe` in binary truth/prediction columns, invalid apparent-operability states, and a case dataset without both actual positive and actual negative opportunities.
- Output percentages that would be mathematically unsupported by a denominator. When a class has no negative opportunities, **false-positive rate is null / not estimable**, not a perfect zero. The same principle applies to undefined precision/recall and no-decision operability accuracy.

The [attendance case decision trace](attendance-case-decision-trace.md) extends the operational receipt to ONE final attendance case decision, using `--attendance-case-sample-id` and explicit centre/batch/video/reported-count mapping. Camera-insufficient streams cannot be scored as ordinary attendance negatives. This does not authenticate other case opportunities or the full confusion matrix.

The [operational attendance trace](operational-attendance-trace.md) optionally verifies sampled **registered/confirmed and smoothed** occupancy predictions from the existing pipeline with `--operational-attendance-receipt`. It cannot be combined with `--attendance-receipt`, which scores a different raw-detector count. Neither mode authenticates the unsigned local receipt or verifies unrelated subsystems.

A future provider-specific model benchmark must separately preserve the inference logs, model version, thresholds, command/configuration, prediction-to-sample matching and independent labels. Only then can a scored result be attributed to a particular computer-vision system. The hash-bound CSV scorer **does not** make that attribution.

## Acceptance remaining before claiming Milestone 3

1. The user-selected actual footage must be present in local storage and qualify under `demo/release-assets.local.json`.
2. All four datasets must contain independent, timestamped annotations with an auditably correct relationship to their footage, including genuine negative opportunities.
3. Capture and version **actual model prediction outputs** against those samples; review miscounts, abstentions and false alarms.
4. Run full final-mode scoring and case-level evaluation with the frozen vision model, plus per-class equipment evaluations, camera insufficiency and edge bandwidth on the same selected clips.
5. Inspect the judge-facing claims against the produced JSON and CSV; never extrapolate the limited demo measurements to the full MSDE network.

See `docs/release/final-media-freeze.md` for media/provenance setup and `docs/release/SIH_MVP_TRACKER.md` for stage acceptance. The checked-in example media manifest is intentionally unqualified.
