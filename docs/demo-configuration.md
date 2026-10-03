# Final Demo Configuration

The final demo can be swapped without editing Python source.

## Environment variables

```bash
KAUSHALWATCH_MANIFEST_PATH=configs/job_roles/construction_electrician.demo.json
KAUSHALWATCH_EQUIPMENT_CACHE=demo/cached_detections/construction_electrician.example.json
KAUSHALWATCH_SCENARIO_PATH=demo/scenarios/final-demo.example.json
KAUSHALWATCH_DEMO_VIDEO=data/raw/final-demo.avi
```

Relative paths are resolved from the repository root.

For the final presentation, point `KAUSHALWATCH_EQUIPMENT_CACHE` at the **reviewed GroundingDINO precompute output from the exact final video**, stored locally under a gitignored path such as:

```bash
data/generated/final-demo-equipment.json
```

Do not overwrite the checked-in example fixture with results and then forget which file is simulated.

## Readiness check

```bash
python scripts/check_demo_readiness.py \
  --video data/raw/final-demo.avi \
  --require-openvino
```

The command fails closed if an expected asset is missing or if the manifest contains an item that never appears in the equipment cache.

A green readiness check proves configuration completeness only. It does not prove model accuracy.
