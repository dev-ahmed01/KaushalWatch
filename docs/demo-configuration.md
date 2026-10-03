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

## Configuration readiness check

During development, use the ordinary readiness check:

```bash
python scripts/check_demo_readiness.py \
  --video data/raw/final-demo.avi
```

It validates that the configured JSON assets exist, the video is non-empty and readable by OpenCV, the video has usable FPS/frame/dimension metadata, the apparent-operability ROI fits inside the actual video frame, and the manifest/cache labels align.

## Strict final-presentation gate

Before freezing the SIH demo, run:

```bash
python scripts/check_demo_readiness.py \
  --video data/raw/final-demo.avi \
  --final
```

`--final` fails closed when any of these stage-risk conditions remain:

- the checked-in example scenario is still configured;
- the example equipment cache is still configured instead of reviewed detections from the exact clip;
- the attendance detector is not OpenVINO;
- required demo scenario events are missing;
- the apparent-operability ROI still carries the placeholder/replace marker;
- the OpenVINO XML/BIN assets are missing;
- the video cannot be opened/read or its ROI falls outside the real frame.

Set the detector/model environment used for the final run, for example:

```bash
KAUSHALWATCH_PERSON_DETECTOR=openvino
KAUSHALWATCH_OPENVINO_MODEL_XML=models/openvino/person-detection-retail-0013/FP16/person-detection-retail-0013.xml
KAUSHALWATCH_OPENVINO_DEVICE=CPU
KAUSHALWATCH_PERSON_CONFIDENCE=0.45
```

A green readiness check proves **asset and configuration readiness only**. It does not prove model accuracy. Final accuracy still comes only from independent annotations of the exact controlled clip and `evaluation/evaluate_final_demo.py`.
