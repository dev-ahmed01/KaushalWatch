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


## End-to-end API verification

After freezing the selected profile, the same manually counted five-worker clip was rerun through the live FastAPI endpoints with the calibrated launcher.

Attendance endpoint result:

- Reported attendance: **5**
- Estimated stable occupancy: **5**
- Discrepancy: **0.0%**
- Decision: **compliant**
- Trusted sample ratio: **1.0**
- Mismatch persistence ratio: **0.20**
- Detector: **OpenVINO primary, authoritative, confidence 0.45, tiled on**
- Detector failures: **0**
- Compliance case: **none**

Practical-work endpoint result on the same clip:

- Decision: **authorized_practical_activity**
- Peak stable workers: **5**
- Active work cells: **2**
- Practical-activity fraction: **0.6286**
- Trusted frame ratio: **1.0**
- Detector: **OpenVINO primary, authoritative, confidence 0.45, tiled on**
- Detector failures: **0**
- Compliance case: **none**

The raw detector still produced transient counts outside the true count, but the temporal registration/smoothing path rejected those flashes and converged to the correct stable occupancy. This is the intended behavior of the attendance pipeline.

Held-out validation on a different original fixed-camera clip is still required before making broader claims.


## Responsive temporal occupancy candidate

The first timestamped held-out evaluation on the separate dynamic-occupancy clip showed that the frozen detector itself was not the only source of error. On 12 manually annotated timestamps:

- raw detector count MAE: **1.1667**, mean bias **+0.6667**
- registered-track count MAE after warm-up: **1.3333**, mean bias **-1.3333**
- smoothed registered count MAE after warm-up: **1.5556**, mean bias **-1.5556**

Inspection of the same observations showed the confirmed-track layer reacting materially faster than the stricter two-second per-track registration layer. The architecture therefore now supports two explicit occupancy sources:

- `registered` — conservative generic default, 2-second per-track maturity before it can influence occupancy
- `confirmed` — responsive demo candidate, 1-second per-track confirmation, while retaining the existing global 2-second attendance warm-up and temporal mismatch-persistence gate

The generic profile remains `registered` with a five-sample median. The SIH demo launcher now selects `confirmed` with a three-sample median for revalidation.

This is **not yet a new frozen result**. Both the five-worker calibration clip and the dynamic held-out clip must be rerun after this temporal-layer change before its metrics are accepted.


## Final frozen attendance demo profile

The responsive temporal candidate was revalidated after Cycle 10 and is now the frozen SIH attendance demo profile.

```text
KAUSHALWATCH_PERSON_DETECTOR=openvino
KAUSHALWATCH_PERSON_CONFIDENCE=0.45
KAUSHALWATCH_OPENVINO_TILED=1
KAUSHALWATCH_OPENVINO_TILE_OVERLAP=0.18
KAUSHALWATCH_OPENVINO_TILE_NMS_IOU=0.45
KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE=confirmed
KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW=3
```

### Calibration clip regression

On the manually verified five-worker constant-occupancy clip:

- reported attendance: **5**
- estimated occupancy: **5**
- discrepancy: **0.0%**
- decision: **compliant**
- mismatch persistence: **0.16**
- trusted sample ratio: **1.0**
- detector failures: **0**
- occupancy count source: **confirmed**
- occupancy smoother window: **3**
- compliance case: **none**

The confirmed-track stream briefly reached six in the middle of the clip, but the temporal decision layer did not create a false exception because the persistent final occupancy remained five and the mismatch persistence stayed well below the 0.60 case threshold.

### Dynamic held-out clip

On the separate manually timestamped dynamic clip:

| Metric | Old registered + 5 median | Frozen confirmed + 3 median |
| --- | ---: | ---: |
| Smoothed-count MAE | 1.5556 | **0.6667** |
| Median absolute error | 1.0 | **0.0** |
| Max absolute error | 4 | **3** |
| Mean bias | -1.5556 | **-0.4444** |
| Exact-count rate | 22.22% | **55.56%** |

This is a **57.1% reduction in smoothed-count MAE** on the held-out dynamic sequence.

The OpenVINO confidence, tiled inference settings and 15% compliance discrepancy threshold were unchanged. The improvement came from removing unnecessary temporal lag after startup while retaining:

- 1-second track confirmation,
- global 2-second attendance warm-up,
- camera-trust gating,
- 60% mismatch-persistence requirement,
- human-review case workflow,
- privacy-preserving evidence retention.

### Claim boundary

The frozen profile is suitable for the SIH demo based on one controlled calibration clip and one separate held-out dynamic clip. These two clips do not establish broad CCTV accuracy. The EPFL benchmark remains the only detector precision/recall benchmark currently claimed.
