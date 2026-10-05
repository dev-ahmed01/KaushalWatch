# Equipment Detection Validation

Equipment detection is deliberately **offline and replaceable** in the current SIH build.

## Why
GroundingDINO is useful because the selected training-centre equipment is not represented cleanly by ordinary COCO classes. It is also substantially heavier than the attendance detector. It must therefore never sit on the critical path for the stage demo.

## Validation path
1. Create a separate Python environment if desired.
2. Install:
   ```bash
   pip install -r backend/requirements.txt
   # CPU example; use the appropriate PyTorch install for your machine/GPU.
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install -r backend/requirements-grounding.txt
   ```
3. Run the precompute tool against the exact final demo video:
   ```bash
   python scripts/precompute_grounding_dino.py \
     --video data/raw/final-demo.avi \
     --seconds auto \
     --sample-count 5 \
     --out data/generated/final-demo-equipment.json
   ```
4. Visually inspect every annotated JPG in the generated `*-review/` directory before promoting the JSON to the stage-safe cache. The tool also writes a `.meta.json` sidecar with the exact model, prompts, threshold, video metadata and sample timestamps.
5. If the default prompts are not visually appropriate for the exact room, provide a reviewed JSON mapping with `--prompt-config` rather than changing labels after seeing the model output.
6. Record true equipment counts separately and compute equipment precision/recall on the controlled clip.

The script follows Hugging Face's supported GroundingDINO path with `AutoProcessor` and `AutoModelForZeroShotObjectDetection`. Heavy model packages are not part of the core API requirements.

## Stage behavior
The live product consumes the `EquipmentDetector`/cache format, not GroundingDINO directly. Therefore:

```text
GroundingDINO precompute
        ↓
reviewed JSON cache
        ↓
InfrastructureCompliancePipeline
        ↓
temporal manifest comparison
        ↓
minimal evidence
        ↓
persisted compliance case
```

If GroundingDINO underperforms, the attendance, camera-trust, evidence and officer-review paths remain functional.

## Important limitation
A detection means only that the object was visually grounded with some confidence. It does not by itself prove official compliance, quantity completeness, or mechanical operability.


## Verified isolated smoke
GitHub Actions workflow `grounding-smoke` successfully installed the CPU-only model environment and ran `IDEA-Research/grounding-dino-tiny` inference against a CC0 electrical-workroom image.

The smoke returned six prompt-grounded detections at threshold 0.30, including workbench/chair/panel/drill-related text prompts. This proves the model/inference wiring works in our reproducible environment. It **does not** establish equipment precision/recall; that must be measured on the exact controlled demo clip.


### Short-video safety

`--seconds auto` is the default. It derives in-bounds sample timestamps from the actual video duration, so a 7-second demo clip is never accidentally queried at 10 or 20 seconds. Explicit timestamps are still supported, but the tool now fails clearly when a requested timestamp is outside the video.

The generated cache keeps the existing detector-adapter schema, so it can be reviewed and promoted without changing the live infrastructure pipeline.


### Windows tokenizer compatibility

Some current Windows installations of the Transformers/tokenizers stack reject GroundingDINO's documented nested text-label shape with a `TextEncodeInput` `TypeError`. The precompute and smoke scripts now retry that specific failure with an equivalent period-separated text string. Other `TypeError` exceptions still propagate normally, so unrelated processor problems are not hidden.


## Reviewed DOD infrastructure profile

The public-domain `DOD_110930728.mp4` clip is now the reviewed infrastructure demo source.

- Source SHA-1 (published verification): `2ec8a58939656ffad0f38176835c22eb331bb96e`\n- Source SHA-256 (stage binding): `ba6ccded59533d0dbd0d21c8073d07e6dda7e7034ed85b10d0997e10ba7feb91`
- GroundingDINO review samples: 0, 2, 4, 6, 8, 10 and 12 seconds
- Accepted visual counts: one workbench and one electrical training panel
- Confirmed absent in the reviewed wide shots: training chairs and drill machine
- Rejected proposal: the 10.0 s drill-machine box covered the bench and was marked a false positive
- Apparent-activity window: 14.0–33.0 seconds on the training-panel ROI

The promoted cache uses `verification_confidence` only after explicit human review while retaining the original GroundingDINO `confidence`, boxes and scores. This avoids lowering the global detector confidence threshold merely to fit one clip and keeps the model proposal separate from the reviewed stage-safe observation.

The reviewed cache is frozen to the exact source SHA-256 (falling back to SHA-1 only for older metadata). Both the upload API and standalone rehearsal refuse to apply it to a different video.
