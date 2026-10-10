# Milestone 2 — Final SIH demo media freeze

This is the **local-only** qualification system for clips and independent labels. It does not search for, download, fabricate, or certify missing footage. CI exercises its failure and success paths with generated non-person imagery; those tests are **not real-video validation**.

## Why this gate exists

The original controlled-rehearsal script correctly checks the SHA-bound DOD equipment metadata against the clip passed to that script, but a passing synthetic CI run does not prove that the attendance, practical, operability, camera-quality and case-evaluation datasets correspond to actual stage footage.

The release qualifier verifies one fixed manifest containing:

- Five *roles*: `attendance`, `practical`, `infrastructure`, `operability`, `camera_degraded`. Several roles may share one physical clip **only when truthful**. It verifies readability, actual SHA-256, centre ID, batch ID, origin, usage/license basis and privacy basis.
- Four required **independently recorded** CSV files: attendance (`sample_id,true_count,pred_count,true_issue,pred_issue`), equipment (`sample_id,item_id,true_count,pred_count`), operability (`sample_id,item_id,true_state,pred_state`), compliance-case opportunities (`sample_id,case_type,true_issue,pred_issue`). Files must be nonempty and SHA-pinned. The cases CSV must include **both positive and negative opportunities**; a set of only expected failures is not an accurate benchmark.
- The frozen scenario's SHA-256, identifier and its primary infrastructure clip/centre/batch binding.
- The human-reviewed equipment cache and metadata SHA-256; the metadata's **source_video.sha256 must equal the infrastructure clip**.
- The practical authorization input and configured work-cell profile (not evidence of external authorization by itself).
- The apparent-operability ROI, stable time interval, and **explicit known camera cuts**. Any overlap between an identified cut and the interval fails.

The gate does **not** automatically prove independent annotation, source license ownership, absence of unknown camera cuts, or that equipment labels are semantically correct. Those remain human sign-offs and separate model evaluation criteria.

## Windows/PowerShell operator steps

From the repository root, without altering source code or checked-in example files:

```powershell
Copy-Item demo\release-assets.example.json demo\release-assets.local.json
Copy-Item demo\scenarios\final-demo.example.json demo\scenarios\final-demo.local.json
```

Edit the two **local Git-ignored** copies. Record the *actual* centre, batch, timestamps, ROI, stable operability window, documented camera cuts, external authorization and ground-truth source. Remove all `REPLACE`, `TBD` or other placeholders. Change the scenario status to `FINAL CONTROLLED DEMO`. Set the manifest `status` to `frozen`, and enter its exact `scenario.sha256` after finishing the scenario.

Keep private/raw sources and independently prepared annotation CSVs in `data/raw/` and `data/annotations/`. The template's paths are relative to **the manifest's directory** (`demo/` for the recommended location). Use `Get-FileHash` for **every** pinned clip, CSV, scenario, cache and metadata file:

```powershell
(Get-FileHash "data\raw\DOD_110930728.mp4" -Algorithm SHA256).Hash.ToLower()
(Get-FileHash "data\annotations\cases.csv" -Algorithm SHA256).Hash.ToLower()
(Get-FileHash "demo\scenarios\final-demo.local.json" -Algorithm SHA256).Hash.ToLower()
```

There is no requirement to copy a 1.7 GB file into the repository. A manifest can reference a local absolute path on the demo laptop, but such manifests are not portable to a different computer until paths are corrected. Git ignores the `*.local.json` freeze files and `demo_assets/`.

Provide the manifest and scenario as environment variables in the **backend/CLI runtime**:

```powershell
$env:KAUSHALWATCH_RELEASE_ASSET_MANIFEST="demo/release-assets.local.json"
$env:KAUSHALWATCH_SCENARIO_PATH="demo/scenarios/final-demo.local.json"
$env:KAUSHALWATCH_EQUIPMENT_CACHE="demo/cached_detections/dod_110930728.reviewed.json"
$env:KAUSHALWATCH_PERSON_DETECTOR="openvino"
```

If you use a different independently reviewed equipment source, change both the runtime cache path and the manifest cache/metadata/digest entries. Do **not** pair the DOD human-reviewed cache with unrelated footage.

### Run qualification *before* model execution

```powershell
python scripts/verify_release_assets.py --manifest demo/release-assets.local.json
```

Exit code `0` means source files, pins, labels and formal mappings qualified. Exit code `2` means not qualified. The output includes pass/fail checks but **does not dump footage or annotation rows**. A failed or missing asset does not get replaced with a synthetic clip.

Then prepare/verify the model using the same Python environment that launches the backend:

```powershell
python scripts/prepare_demo_vision.py --install
python scripts/check_demo_readiness.py --video "data/raw/DOD_110930728.mp4" --final --asset-manifest demo/release-assets.local.json
python scripts/run_final_demo_rehearsal.py --video "data/raw/DOD_110930728.mp4" --final --asset-manifest demo/release-assets.local.json
```

The `--final` readiness and rehearsal paths now require the frozen registry; they reject runtime scenario/cache or clip SHA mismatch. The exact same primary infrastructure video must be supplied to these commands. Other roles must still be analyzed with their actual annotated source clips during final evaluation.

**Important:** Do not take percentages or detection accuracy from `demo/release-assets.example.json`, synthetic CI tests, or unreviewed per-frame predictions. Metrics belong to the independently annotated exact clips only. After freezing actual files, run the **final-mode** scorer described in [frozen-scorecards.md](frozen-scorecards.md); passing the file-integrity gate alone does not establish model-output provenance.

## Remaining Milestone 2 acceptance

The code and fail-closed validation gate are available; the milestone itself remains **open** until the actual final assets are present on the demo laptop, SHA-verified, independently labelled, licensed/privacy-reviewed, and mapped to the selected five-centre narrative. No model-accuracy, practical-authorization or operability claim is implied by a passing manifest alone.
