# Phase 3C — independently annotated equipment boxes

**Status: software available, REAL MODEL NOT QUALIFIED.** The missing authorized electrician-room holdout and external reviewer audit keep issue #103 open.

This evaluator adds source-pinned per-class IoU box localization WITHOUT replacing the existing presence/count evaluation (evaluation/live_equipment_qualification.py). It reuses that frozen protocol, its calibration-vs-heldout controls, complete count/class manifest, offline model hashes, untouched source video and the existing real GroundingDINO adapter. Do not conflate presence/count MAE with localization recall or claim COCO mAP.

## Private frozen input

Outside the Git repository, prepare a localization.json:

~~~json
{
  "schema": "KW_EQUIPMENT_LOCALIZATION_V1",
  "status": "frozen",
  "fixture_only": false,
  "policy": {
    "id": "equipment-localization-human-audit-v1",
    "iou_threshold": 0.5,
    "min_reviewed_positive_boxes": 4,
    "min_reviewed_negative_opportunities": 4,
    "min_reviewed_classes": 2,
    "min_scored_recordings": 4
  },
  "presence_manifest": {"path": "count-protocol.json", "sha256": "<actual SHA-256>"},
  "annotations": {
    "EXACT-HELDOUT-SCENE-ID": {
      "labels": {"path": "reviewed-box-labels.json", "sha256": "<actual SHA-256>"},
      "roi": [0.05, 0.05, 0.95, 0.95],
      "roi_basis": "<actual camera-specific reason>",
      "reviewer_id": "<real independent reviewer ID>",
      "blinded_review": true,
      "previously_inspected": false,
      "annotation_origin": "<real annotation custody>",
      "license_basis": "<real permission>",
      "privacy_basis": "<real privacy grounds>"
    }
  }
}
~~~

The numerical ROI in this schema is illustrative and must be replaced by the independently reviewed camera ROI. Add one annotations entry for EVERY held-out scene of the existing count protocol. That base count protocol must pass its own video/model SHA, frozen prompts, multi-site heldout and calibration split checks.

Each SHA-pinned reviewed-box-labels.json must provide original-source normalized coordinates:

~~~json
{
  "schema":"KW_EQUIPMENT_BOX_LABELS_V1",
  "frames":[{
    "second":0,
    "labels":[
      {"item_id":"chair","state":"reviewed","boxes":[[0.1,0.2,0.3,0.4]]},
      {"item_id":"drill","state":"reviewed","boxes":[]}
    ]
  }]
}
~~~

Frames are exactly the already-frozen held-out timestamps. Every frame must cover ALL frozen prompt classes. State reviewed with empty boxes means an explicitly reviewed absence, not missing data. Occluded or unlabelable uses state unlabelable plus empty boxes, and the opportunity ABSTAINS; it never becomes FP, FN, or TN. Count truth cannot be considered independently known in an unlabelable frame. Any annotation outside the pinned ROI is blocked. Same site/camera must use the same frozen ROI.

## Local run

~~~powershell
python evaluation/equipment_localization_qualification.py --manifest "D:\Private\KW\localization.json" --out "D:\Private\KW\equipment-localization.local.json"
~~~

The private file is created once with mode 0600 and cannot be silently overwritten. The CLI does no footage upload, copy, or network download. Missing sources/labels produce status localization_blocked with exit 2, not fabricated zeros. Output binds every actual video SHA, model-weights SHA, frozen prompts digest, source/count-protocol SHA, annotation file SHAs, camera ROIs and reviewer identifiers.

**Matching:** the genuine saved offline local model adapter runs on each sample. Predictions require all classes, valid pixel boxes and explicit counts. Boxes normalize to video frame dimensions; only predicted centres inside frozen ROI are evaluated. Deterministic maximum-cardinality one-to-one matching at IoU >= 0.50 counts matches as TP, unmatched model proposals as FP, and unmatched independent reviewed boxes as FN. Duplicate surviving predictions are penalized. An unlabelable class/time abstains; negative controls are explicitly recorded.

Even a real detector result returns localization_measured_pending_independent_audit with qualified=false. Reviewer attestations and SHA pins cannot independently prove review integrity, model-execution authenticity, or legally approved camera rights. This is a diagnostic, not COCO mAP, mandated government equipment quantity, tool operability/safety, competence, live centre acceptance, or automatic enforcement.

The CI tests generate dummy frames/checkpoints and inject fake detections ONLY through a test-only entrypoint. They cover clean TP, wrong class, duplicate/overlap, missed object, negative/empty frame, occlusion, wrong timing, source/model/label SHA drift, camera ROI mismatch and held-out leakage. Such fixtures can never qualify field accuracy. Existing four officer modules and illustrative matrix remain unchanged.
