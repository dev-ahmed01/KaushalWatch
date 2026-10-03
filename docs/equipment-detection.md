# Equipment Detection Validation

Equipment detection is deliberately **offline and replaceable** in the current SIH build.

## Why
GroundingDINO is useful because the selected training-centre equipment is not represented cleanly by ordinary COCO classes. It is also substantially heavier than the attendance detector. It must therefore never sit on the critical path for the stage demo.

## Validation path
1. Create a separate Python environment if desired.
2. Install:
   ```bash
   pip install -r backend/requirements.txt
   pip install -r backend/requirements-grounding.txt
   ```
3. Run the precompute tool against the exact final demo video:
   ```bash
   python scripts/precompute_grounding_dino.py \
     --video data/raw/final-demo.avi \
     --seconds 0,10,20 \
     --out data/generated/final-demo-equipment.json
   ```
4. Visually inspect every sampled frame and detection before promoting the generated JSON to the stage-safe cache.
5. Record true equipment counts separately and compute equipment precision/recall on the controlled clip.

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
