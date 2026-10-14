# Held-out attendance qualification gate (release continuation)

Status: **evaluation runner and acceptance policy implemented; real-world
qualification NOT established without independent input footage and labels**.

This workflow audits the *frozen OpenVINO person detector plus the actual
tracked, smoothed, temporal attendance decision*. It does not certify other
vision pillars, national-scale suitability or identity recognition.

## Why the gate exists

A training video used to tune the detector must never reappear as a supposedly
unseen benchmark. Adjacent clips from one recording are not independent.
A system that makes few predictions can report high accuracy if abstentions
silently disappear; this gate measures both coverage and performance. A
camera-integrity block is not a true-negative attendance decision.

## Inputs kept outside Git

Make a local frozen protocol, for example
`data/annotations/heldout-protocol.json`. It must declare:

- A unique `protocol_id`, `status: "frozen"`, `schema_version: 1`,
  `fixture_only: false`, and **exact policy object** from
  `evaluation/heldout_qualification.py::POLICY`.
- The active, unchanged vision profile under `vision_profile` and **both**
  OpenVINO `.xml` and `.bin` files under `model_artifacts`. Each file spec
  is `{"path":"relative/to/protocol.json","sha256":"<64 lowercase hex>"}`.
- At least one **calibration** scene: stable scene/recording/site/camera IDs,
  digest-pinned source video and meaningful `source_origin`,
  `license_basis`, and `privacy_basis` metadata.
- At least six separate **held-out** video recordings: different recording
  IDs **and file digests** from the calibration set and from one another,
  spanning at least **two sites and two cameras**. Each must include the same
  provenance fields and `reviewer_id`, `blinded_review: true`,
  `reported_attendance` (int), `reported_record_reference`,
  independently assigned `true_issue` (boolean), a SHA-pinned `video`,
  and SHA-pinned independent `truth` CSV.
- Four or more unique post-warmup timestamps per scene, at least 24 total,
  with `second,true_count` CSV header, strictly increasing seconds,
  no missing frames, and enough **positive AND negative case opportunities**
  (minimum two of each).

The path and file hashes are frozen before inference; the source videos,
annotations, profile and model artifacts are rechecked after scoring.
Transcripts, clips, faces, filenames and raw frames are deliberately omitted
from the output report. The independent-review attestation is metadata; the
program cannot cryptographically prove an annotator's independence.

### Schema illustration (not a usable manifest)

```json
{
  "schema_version": 1,
  "protocol_id": "CENTER-VALIDATION-2026-V1",
  "status": "frozen",
  "fixture_only": false,
  "policy": {"policy_id": "heldout-attendance-provisional-v1", "...": "all exact POLICY keys and values"},
  "vision_profile": {"path": "../configs/vision_profiles/kaushalwatch-fixed-camera-v1.json", "sha256": "SHA256"},
  "model_artifacts": {
    "xml": {"path": "../models/person-detection-retail-0013.xml", "sha256": "SHA256"},
    "bin": {"path": "../models/person-detection-retail-0013.bin", "sha256": "SHA256"}
  },
  "calibration": [
    {"scene_id": "CAL-001", "recording_id": "SESSION-CAL-001",
     "camera_id": "CAM-01", "site_id": "SITE-01",
     "source_origin": "legally authorized collection description",
     "license_basis": "documented permitted research evaluation use",
     "privacy_basis": "documented collection and retention basis",
     "video": {"path": "calibration.avi", "sha256": "SHA256"}}
  ],
  "heldout": [
    {"scene_id": "VAL-001", "recording_id": "SESSION-VAL-001",
     "camera_id": "CAM-02", "site_id": "SITE-02",
     "source_origin": "legally authorized collection description",
     "license_basis": "documented permitted research evaluation use",
     "privacy_basis": "documented collection and retention basis",
     "reviewer_id": "REVIEWER-02", "blinded_review": true,
     "reported_attendance": 10, "reported_record_reference": "REGISTER-ROW-01",
     "true_issue": true,
     "video": {"path": "heldout_01.avi", "sha256": "SHA256"},
     "truth": {"path": "heldout_01_counts.csv", "sha256": "SHA256"}}
  ]
}
```

This illustration deliberately omits required scenes and uses digest
placeholders; the validator **must reject** it. Do not copy it as real evidence.
The true-issue label is a **video-level independent case opportunity**,
not a per-frame prediction label; the reported-attendance record must be
established externally, before model inference.

## Real execution

Install OpenVINO dependencies and use the actual pinned model/profile.
Verify that detector confidence/tile configuration matches the profile.
The evaluator uses the production `VideoCompliancePipeline` and calls
`observation_sink` from that pass; it does not accept a user-supplied
prediction CSV.

```bash
# Input-only verification is never an accuracy pass:
python evaluation/heldout_qualification.py \
  --manifest data/annotations/heldout-protocol.json \
  --check-inputs --out evaluation/output/heldout-inputs.json

# Attempt actual (non-fixture) accuracy qualification:
KAUSHALWATCH_PERSON_DETECTOR=openvino \
KAUSHALWATCH_OPENVINO_TILED=1 \
python evaluation/heldout_qualification.py \
  --manifest data/annotations/heldout-protocol.json \
  --out evaluation/output/heldout-report.json
```

Configure additional OpenVINO environment settings only when they exactly
match the frozen profile. Set
`KAUSHALWATCH_OPENVINO_MODEL_XML` to the protocol-pinned XML file if needed.
The evaluator refuses a fallback detector, a model/configuration mismatch,
source-hash changes or missing video/annotations. It exits with status **2**
when blocked/failing; no accuracy pass is possible in input-only mode.

### Provisional minimum acceptance policy

| Gate | Required |
| --- | ---: |
| Independent recordings | 6 or more |
| Cameras / sites | 2 / 2 or more |
| Annotated count samples | 24 or more, at least 4 per scene |
| Positive and negative case opportunities | At least 2 each |
| Occupancy MAE (eligible samples) | 0.8 persons or less |
| Overall trusted count coverage | 90% or more |
| Each-scene trusted count coverage | 75% or more |
| Attendance case coverage | 90% or more |
| Attendance case recall | 85% or more |
| Attendance case false-positive rate | 15% or less |
| Detector failures | 0 |

These thresholds are **provisional, conservatively chosen engineering targets**,
not government specifications or empirically established deployment minima.
Lock an approved policy before the final field evaluation; do not tune policy
or model against held-out outcomes to manufacture a pass.

Metrics use **eligible trusted samples only**, after the profile's two-second
warmup. Count coverage reports withheld/blocked samples. Case-level confusion
is measured per recording (TP, FP, FN, TN); blocked camera/detector outcomes
are *abstentions*, not clean negatives. The aggregate output includes count
MAE, maximum error, count/case coverage, per-camera count MAE, confusion,
all criteria, file digests and non-certification notes.

## Synthetic CI vs actual qualification

`backend/tests/test_heldout_qualification.py` generates temporary synthetic
videos, hashes, independent-count *fixtures*, and an **injected fake inference
function** solely to exercise rejection conditions: annotation drift,
calibration/holdout overlap, duplicated sample positions, falsely trusted
counts, missing false-negative support, camera blockage, detector fallback,
model-profile mismatch and policy changes.

This path unconditionally returns
`synthetic_fixture_not_qualifying` and `qualified: false`, **even when
every numeric metric is perfect**. A CI-green test run therefore means only
that the evaluation machinery and safety gates work; it never upgrades
production model-accuracy claims.

## Unfinished qualification work

1. Obtain legally usable, independently annotated training-centre footage,
   including more than one camera/site and distinct calibration recordings.
2. Retain independent annotator logs and provenance of the external reported
   attendance records. Confirm actual positives/negatives and all scene
   eligibility constraints.
3. Run OpenVINO on the frozen clips; review blocked cases and accuracy/coverage
   tradeoffs. Do not change a locked model or threshold after seeing held-out
   results without resetting the evaluation cohort.
4. Repeat similar evidence-based gates for practical activity, infrastructure,
   apparent operability and Camera Trust before making those claims.
5. Pair this with protected, centrally durable media storage and the previously
   implemented PostgreSQL backend before piloting across backend workers.

**No real-footage PASS is claimed by this phase until an actual manifest,
footage, independent labels and model have satisfied the full non-fixture run.**
