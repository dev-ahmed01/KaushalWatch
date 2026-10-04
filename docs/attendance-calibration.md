# Attendance Calibration — Industrial Fixed-Camera Clip

This note records the target-clip calibration used for the SIH demo attendance profile.

## Ground truth

- Manually verified physical occupancy: **5 workers**
- Clip duration: approximately **6.95 s**
- Resolution: **1920×1080**
- Camera: fixed
- Calibration purpose: recover partially occluded / small workers without weakening the compliance discrepancy threshold

The manual count was established from the video itself before selecting a detector setting. It was not derived from KaushalWatch output.

## Sweep

The OpenVINO `person-detection-retail-0013` detector was evaluated at five confidence thresholds with both full-frame inference and an overlapping 2×2 tiled pass.

| Variant | Confidence | Stable occupancy | Registered MAE after 2s | Raw-count MAE | Decision with reported=5 |
| --- | ---: | ---: | ---: | ---: | --- |
| Full frame | 0.25 | 6 | 1.68 | 2.6857 | attendance_exception |
| Full frame | 0.30 | 6 | 1.16 | 1.7429 | attendance_exception |
| **Full frame** | **0.35** | **5** | **0.48** | **1.1714** | **compliant** |
| Full frame | 0.40 | 4 | 1.28 | 0.8000 | attendance_exception |
| Full frame | 0.45 | 4 | 1.28 | 0.9429 | attendance_exception |
| Tiled | 0.25 | 6 | 1.96 | 4.2857 | attendance_exception |
| Tiled | 0.30 | 6 | 1.48 | 2.8571 | attendance_exception |
| Tiled | 0.35 | 6 | 1.04 | 1.9143 | attendance_exception |
| Tiled | 0.40 | 5 | 0.40 | 1.2000 | compliant |
| **Tiled** | **0.45** | **5** | **0.36** | **0.7143** | **compliant** |

## Selected demo candidate

The selected profile is:

```text
KAUSHALWATCH_PERSON_DETECTOR=openvino
KAUSHALWATCH_PERSON_CONFIDENCE=0.45
KAUSHALWATCH_OPENVINO_TILED=1
KAUSHALWATCH_OPENVINO_TILE_OVERLAP=0.18
KAUSHALWATCH_OPENVINO_TILE_NMS_IOU=0.45
```

Measured on this clip:

- Stable occupancy: **5 / 5**
- Stable occupancy absolute error: **0**
- Registered-count MAE after 2 s: **0.36**
- Registered count exactly 5 after 2 s: **80% of eligible samples**
- Raw-count mode: **5**
- Raw-count median: **5**
- Raw-count range: **4–7**
- Raw-count MAE: **0.7143**
- Trusted sample ratio: **1.0**
- Detector failures: **0**
- Attendance decision when reported attendance = 5: **compliant**
- Discrepancy: **0%**

The 0.45 tiled candidate was preferred over 0.40 tiled because both reached the correct stable occupancy, while 0.45 produced lower registered-count MAE and lower raw-count MAE.

## Claim boundary

This calibration fixes a concrete undercount observed on the supplied five-worker target clip. It does **not** replace the existing EPFL benchmark and does not establish general CCTV accuracy.

The selected profile should be tested on held-out fixed-camera footage before making broader precision/recall or occupancy claims. The compliance discrepancy threshold remains unchanged; the fix improves the vision input rather than hiding the error downstream.
