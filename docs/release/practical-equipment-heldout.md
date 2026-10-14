# Phase 2B — Practical activity and equipment quality gates

**Status: evaluation implementation and synthetic regression coverage only.**
Independent real training-centre accuracy has NOT been measured.

## Practical activity — actual frozen pipeline

`evaluation/practical_holdout.py` replays the currently released
`PracticalActivityPipeline` on independently labelled, previously untouched
fixed-camera recordings. It uses the frozen OpenVINO `.xml/.bin` model and
active vision profile. No labels are passed into inference: only the scene
video, reviewed camera work zones, and an independently supplied external
authorization status.

Create a local frozen JSON manifest, outside Git, with:
- `schema_version:1`, `protocol_id`, `status:"frozen"`,
  `fixture_only:false`, and an **exact copy** of
  `evaluation/practical_holdout.py::POLICY`.
- SHA-pinned `vision_profile`, `model_artifacts.xml` and `.bin`.
- A distinct `calibration` list containing at least one recording with
  `scene_id`, `recording_id`, `site_id`, `camera_id`,
  `source_origin`, `license_basis`, `privacy_basis`, and pinned `video`.
- At least six distinct `heldout` recordings spanning two sites/cameras.
  Each includes the above, `true_activity` boolean,
  `authorization` (valid/absent/unknown), `external_record_reference`
  from an independent schedule, `reviewer_id`, `blinded_review:true`,
  `previously_inspected:false`, and a pinned `work_zones` file.
- Every `work_zones` JSON includes `{"reference_size":[WIDTH,HEIGHT],
  "zones":[{"zone_id":"...", "x":0,"y":0,"w":100,"h":100}]}` with
  camera-specific geometry; **do not reuse work-zone coordinates across
  unrelated cameras**.
- At least two positive and two negative true-activity scenes, two absent
  authorization scenes, and one unknown authorization scene.

`true_activity` means independently observed **persistent visible
worker-local activity**, not certified skills, completed practical hours,
safety compliance, or the person's identity.

Run using the frozen OpenVINO detector:
```powershell
$env:KAUSHALWATCH_PERSON_DETECTOR = "openvino"
python evaluation/practical_holdout.py --manifest data/annotations/practical-holdout.json --check-inputs --out evaluation/output/practical-inputs.json
python evaluation/practical_holdout.py --manifest data/annotations/practical-holdout.json --out evaluation/output/practical-score.json
```

The initial command checks frozen inputs only; it is **not** an accuracy pass.
Scoring requires actual authoritative OpenVINO inference with unchanged
thresholds. It reports activity recall, activity false positives, case
authorization consistency, no-decision coverage, detector failures and
unauthorized false positives for independently labelled normal opportunities.
Unknown authorization must never be turned into a definitive violation.
Abstention (`camera_evidence_insufficient` or `detector_unavailable`)
reduces coverage and does not count as a correct negative.
The provisional thresholds are locked in the code; they are engineering
targets, NOT government-certified requirements.

CI deliberately injects simulated decisions into synthetic generated clips
but can **never** return `qualified:true` from these fixtures. Real data,
model artifacts, reviewer attestation and exact work-zone geometry are
not available on the CI runner.

## Equipment — retrospective cache shadow, not a live detector

`evaluation/equipment_holdout.py` validates independent item counts
against both original proposal counts and separately reviewed counts from
SHA-pinned, per-timestamp caches. A single record has an item-level count,
not bounding-box localization proof. Required JSON manifest:

```json
{
  "schema_version": 1,
  "status": "frozen",
  "fixture_only": false,
  "policy": {
    "policy_id": "equipment-shadow-proposal-v1",
    "min_scenes": 2,
    "min_item_classes": 2,
    "min_positive_examples": 2,
    "min_negative_examples": 2
  },
  "scenes": [
    {
      "scene_id": "ROOM-A",
      "camera_id": "CAM-A",
      "source_origin": "documented source collection details",
      "license_basis": "documented authorized research use",
      "privacy_basis": "documented privacy and retention basis",
      "independent_label_reviewer": "independent reviewer identifier",
      "reviewed_independently": true,
      "video": {"path": "room-a.avi", "sha256": "actual SHA-256"},
      "proposal_cache": {"path": "raw-proposals.json", "sha256": "actual SHA-256"},
      "human_reviewed_cache": {"path": "reviewed-counts.json", "sha256": "actual SHA-256"},
      "truth": {"path": "independent-item-labels.csv", "sha256": "actual SHA-256"}
    }
  ]
}
```

Include at least two separate scenes. Each cache is a JSON list of
`{"second":0.0,"items":{"drill":1,"chair":0}}` observations; independent
truth CSV uses exactly `second,item_id,true_count`. Missing predictions
remain **unknown** and reduce coverage; they must never be silently scored
as zero objects.

```powershell
python evaluation/equipment_holdout.py --manifest data/annotations/equipment-shadow.json --out evaluation/output/equipment-shadow.json
```

Both proposal and human-reviewed count coverage, count MAE, count-presence
recall and false-presence rates are reported **separately**. The evaluator
does not load GroundingDINO weights or perform model inference. The existing
release `GroundingDinoAdapter` is still a placeholder, and the existing
reviewed DOD cache is not an independently replayable detector. **Even
apparently perfect shadow metrics always return `qualified:false`.**
A real equipment model qualification needs a working detector, frozen
weights/config, untouched videos, independent box/count annotations and
camera-specific validation.

## End-product gating

Before declaring multi-pillar visual compliance ready, independently pass
attendance, camera evidence usability and practical activity on authorized
unseen recordings. Build and qualify live equipment localization/inference
rather than converting human-corrected counts into detector performance.
Operability remains an apparent visual-motion proxy, not proof of electrical
or mechanical health. All case violations remain officer-reviewed.

**No private footage, people identifiers, source camera clips or keys are
added to GitHub during Phase 2B.**
