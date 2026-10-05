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
