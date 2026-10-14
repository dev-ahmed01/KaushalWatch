# Phase 2C — Optional live equipment proposals and visual-motion qualification

**Implementation stage:** Model adapter + CLI + independent evaluation gates.
**Live model accuracy and real-camera operational acceptance: NOT VERIFIED.**

## What changed

The previous `GroundingDinoAdapter` was a placeholder raising an exception.
It now points to `app.services.live_equipment.GroundingDinoAdapter`, which
can execute **real zero-shot GroundingDINO frame inference** using a fully
local, SHA-256-pinned Transformers model snapshot, with no network download,
no remote Python model code, and no silent fallback to precomputed counts.
PyTorch/Transformers load lazily in the optional equipment environment;
attendance and other API paths remain independent.

Every frozen class prompt is evaluated on each decoded video frame. Bounding
boxes/scores are validated for finiteness, nondegenerate geometry and image
bounds, then per-class IoU overlap suppression prevents two nearly identical
boxes counting as two items. The adapter outputs counts, confidence, boxes,
raw model count and the explicit `unreviewed_model_proposal` status. This
is **not** proof of official equipment quantity or competency; a reviewing
officer must still decide before it is trusted in infrastructure compliance.

The existing offline precompute and stage-safe human-reviewed demo stay
unchanged. The new adapter is **opt-in only** and does not automatically
publish cases from unreviewed predictions.

## Optional environment and offline model snapshot

Install the equipment-specific dependencies in an isolated environment:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r backend/requirements-grounding.txt
```

Before a release run, obtain a permitted Hugging Face snapshot
(e.g. `IDEA-Research/grounding-dino-tiny`), vet the license, revision,
tokenizer, processor and all model files, and store it **outside Git**.
Pin the SHA-256 of **every file** in that exact snapshot. No untracked files,
symlink escapes, remotely loaded code, floating model IDs or network
downloads are accepted. Checkpoint weights are substantial, and no weights
are committed in this PR.

Create an operator-controlled local manifest similar to:

```json
{
  "schema_version": 1,
  "status": "frozen",
  "model": {
    "directory": "../private-model/groundingdino",
    "files": {
      "config.json": "<actual lowercase sha256>",
      "model.safetensors": "<actual lowercase sha256>"
    },
    "prompts": {
      "drill_machine": "power drill",
      "training_panel": "electrical control panel"
    },
    "threshold": 0.35,
    "nms_iou": 0.5,
    "device": "cpu"
  },
  "video": {
    "path": "../private-recordings/room-a.avi",
    "sha256": "<actual lowercase sha256>"
  },
  "sample_seconds": [0.0, 1.0, 2.0]
}
```

The example pins only two snapshot files for illustration. Actual
Transformers model folders also require complete pinned processor/tokenizer
files and any other local files used by the chosen revision.

Run:

```powershell
python scripts/run_live_equipment.py --manifest data/annotations/live-equipment-run.json --out data/private/live-proposals.json
```

The script writes a private, non-overwriting receipt (user-only permissions
where OS support permits), including the model SHA pins, video/manifest
digests and a timestamped array of per-item unreviewed boxes/counts.
Video bytes, face crops and images are not written to the receipt. Decode
failure, model error, changed video or missing model file **fails closed**:
no fabricated zero-item result, no fallback to the stage cache. Do not
upload a raw or identifiable private receipt to public CI logs.

## Independent LIVE equipment evaluation

`evaluation/live_equipment_qualification.py` takes a frozen, SHA-pinned
manifest with:
- `schema_version:1`, `status:"frozen"`, `fixture_only:false`,
  a unique `protocol_id`, and the exact `POLICY` from the evaluator.
- `model` as above, with a common offline snapshot and fixed reviewed prompts.
- At least one separate calibration clip and **four independent new held-out
  recordings**, spanning two sites and cameras. Each recording requires
  `recording_id`, `scene_id`, `camera_id`, `site_id`, pinned `video`,
  honest source/license/privacy provenance and, in held-out only,
  `reviewer_id`, `blinded_review:true`,
  `previously_inspected:false`, and SHA-pinned `labels`.
- CSV labels with columns exactly `second,item_id,true_count`, covering
  **every pinned item** at each sampled timestamp, including independently
  labelled zero-count (true-negative) opportunities. Missing model
  predictions are errors, not zero items.
- At least four positive and four negative item opportunities over at least
  two equipment classes.

The scorer runs the **actual GroundingDINO model** through the new adapter,
compares predictions to separately recorded true counts and reports:
presence recall, false-presence rate, mean absolute count error and per-item
count MAE. Provisional gates: recall >=80%, false-presence <=15%, count MAE
<=0.8 and complete label/prediction coverage. These are *engineering*
thresholds, not government requirements. This does **not** measure bounding
box localisation mAP, visibility of occluded objects or actual sanctioned
quantities; a separate box benchmark and policy review are needed.

```powershell
python evaluation/live_equipment_qualification.py --manifest data/annotations/live-equipment-holdout.json --check-inputs --out evaluation/output/equipment-inputs.json
python evaluation/live_equipment_qualification.py --manifest data/annotations/live-equipment-holdout.json --out evaluation/output/equipment-model-only.json
```

A synthetic injected regression can **never** return `qualified:true`.
Actual benchmark videos, immutable model weights and verified independent
labels are still absent from this repository.

## Multi-video apparent-motion proxy qualification

`evaluation/operability_holdout.py` scores the existing **production
`trace_apparent_motion` function**, using pinned videos, per-camera ROIs,
time windows and independently reviewed truth labels:

- `APPARENTLY_ACTIVE` — visually clear motion in ROI
- `APPARENTLY_INACTIVE` — visually no motion in ROI
- `UNDETERMINABLE` — obscured, flickering, or otherwise insufficient video

It requires a separate calibration set, at least six unseen labelled windows
from two sites/cameras, with two positive and two negative windows and one
unlabelable window. The manifest pins full video files, source IDs, reviewer
and privacy permission, integer ROI pixels and actual in-bounds start/end
seconds. The 0.8 apparent-motion threshold is fixed in the policy.

Metrics: visible-motion recall, false active rate, decisive coverage and
**unsafe certainty rate when a human could not label the footage**. Unknown
truth must produce `UNCERTAIN`, not a definite operating claim, for the
provisional gate. This will likely highlight current ROI-motion limitations;
it **does not** measure mechanical/electrical health or ability to perform
training operations.

```powershell
python evaluation/operability_holdout.py --manifest data/annotations/apparent-motion-holdout.json --check-inputs --out evaluation/output/motion-inputs.json
python evaluation/operability_holdout.py --manifest data/annotations/apparent-motion-holdout.json --out evaluation/output/motion-score.json
```

## What is deliberately NOT claimed

CI tests the local snapshot safety checks, inference adapter with a fake
model, synthetic held-out datasets and blocked-input cases. CI **does not**
download a real GroundingDINO checkpoint or run scored unseen footage.
The pre-existing optional grounding-smoke workflow previously established
basic remote-model wiring on a public-domain image, not this exact offline
snapshot or end-to-end private camera accuracy.

The model-only equipment evaluator **can** eventually produce a benchmark
result with approved real data; the earlier `equipment_holdout.py` continues
to be nonqualifying cached-proposal/human-review diagnostics.

No existing officer cases, frozen profile, SIH stage cache, Camera Trust PR
#54 or release-branch merge status is changed by Phase 2C.
