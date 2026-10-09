# Milestone 3 — OpenVINO frame-level attendance trace

This is an additional reproducibility layer over the [frozen scorecard](frozen-scorecards.md). It records **raw person detections on explicitly annotated video frames** using the configured OpenVINO model and the exact SHA-pinned source clip, then checks that the final evaluation's attendance `pred_count` values match the receipt.

It does **not** establish tracked/registered attendance, case-level verdict accuracy, individual identity or authenticated execution provenance.

## Freeze sample frames first

In `data/annotations/attendance.csv`, add a `frame_index` field to each labelled attendance row. This is an exact, **zero-based** frame number in the frozen attendance clip. Preserve `sample_id,true_count,pred_count,true_issue,pred_issue`; `frame_index` is additional. Independently label `true_count` without looking at the machine predictions. Keep samples unique by ID **and** frame index.

The CSV is part of the frozen media manifest. Hash the actual final CSV and update the manifest's attendance annotation digest. If you change the CSV again, regenerate the manifest digest **and** inference receipt; do not edit the receipt's counts.

The raw detector result is not the temporal attendance count the operational pipeline uses. Do not reuse its values for `pred_issue` or treat it as an attendance-case decision. Any mismatch or untrusted camera period must be handled conservatively.

## Capture frame-level detector results

Using the same Python environment that runs the app, with the frozen OpenVINO weights installed:

```powershell
$env:KAUSHALWATCH_PERSON_DETECTOR="openvino"
python evaluation/capture_attendance_inference.py `
  --asset-manifest demo/release-assets.local.json `
  --attendance data/annotations/attendance.csv `
  --out evaluation/output/final-demo/attendance-inference.json
```

The capture tool verifies the frozen media manifest, exact attendance CSV path/hash, source video hash, explicit authoritative OpenVINO backend, its XML and BIN SHA-256, and the selected vision profile hash.

For every annotated frame it saves **only** sample ID, frame index, decoded-frame SHA, trust outcome/reasons and raw person count; no RGB frames, bounding boxes, inferred names or video footage. Untrusted camera samples get `raw_person_detection_count: null`, never a fabricated zero. The receipt is stored under Git-ignored `evaluation/output/`.

If the camera is untrusted, do not claim an attendance MAE for that frame: the matched-scorecard check will explicitly refuse scoring it as a count.

## Check matched predictions before final report

After the frozen attendance CSV's `pred_count` columns reflect the recorded raw detector results, update its SHA in the local manifest, **then recapture** to produce an identical-source trace. Run:

```powershell
python evaluation/evaluate_final_demo.py `
  --final --asset-manifest demo/release-assets.local.json `
  --attendance-receipt evaluation/output/final-demo/attendance-inference.json `
  --attendance data/annotations/attendance.csv `
  --equipment data/annotations/equipment.csv `
  --operability data/annotations/operability.csv `
  --cases data/annotations/cases.csv `
  --out-dir evaluation/output/final-demo
```

The report's `attendance_raw_frame_trace` field records whether exact sample IDs, frame indices and raw counts matched, along with hashes of the local model XML, BIN and vision profile. A changed model file, different sample frame, **re-decoded frame SHA mismatch**, missing camera-trust evidence, missing/duplicated sample or mismatch between CSV `pred_count` and captured detector result stops scoring **before report output**.

Without `--attendance-receipt`, final-mode scorecards still require frozen CSVs, but have `attendance_raw_frame_trace: null` and cannot claim detector-output corroboration.

### Important scientific and implementation limits

- Only **raw per-frame OpenVINO person counts** are connected to a specific local detector invocation. The actual attendance compliance engine also uses trust, temporal sampling, tracking, confirmation, registration, persistence and report comparisons.
- The frame receipt is a local **unsigned JSON** record. It protects against accidental mismatch, not deliberate operator falsification. Reproducible reruns, restricted local access and independent review are still required.
- This is not a new measured accuracy result. Synthetic test detectors exercise the code in CI and their receipts carry `synthetic_test_only`; these receipts are rejected by the final scorecard.
- This release does not yet provide equivalent automatically sourced inference receipts for equipment, practical work, apparent operability or compliance-case predictions. `prediction_source_verified` remains `false` globally. Those workflows require their own faithful engine-to-annotation matching before authoritatively attributing full-system metrics.

## Automated tests

```powershell
python -m pytest -q backend/tests/test_release_assets.py backend/tests/test_final_evaluator.py
```

See [SIH MVP release tracker](SIH_MVP_TRACKER.md) for the actual footage and complete Milestone 3 acceptance gates.
