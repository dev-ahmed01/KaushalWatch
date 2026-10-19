"""Phase 3C: independent, source-pinned per-class box localization.

Complements (never replaces) live_equipment_qualification presence/count gate.
The real path executes the existing SHA-pinned GroundingDINO adapter. Synthetic
injection is allowed ONLY in unit tests and can never qualify a model.

All coordinates are normalized [x1,y1,x2,y2] in original video-frame space.
Unlabelable/occluded opportunities abstain; missing classes are never zeros.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
for location in (ROOT, ROOT / "backend"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from evaluation import live_equipment_qualification as presence
from evaluation.heldout_qualification import sha256_file
from app.services.live_equipment import GroundingDinoAdapter, verify_model_snapshot

POLICY = {
    "id": "equipment-localization-human-audit-v1",
    "iou_threshold": 0.5,
    "min_reviewed_positive_boxes": 4,
    "min_reviewed_negative_opportunities": 4,
    "min_reviewed_classes": 2,
    "min_scored_recordings": 4,
}
SHA = set("0123456789abcdef")


def _digest(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _pin(root: Path, value: object, description: str) -> Path:
    # Reuse the existing equipment evaluator's SHA-pinned private-file loader.
    return presence._file(root, value, description)


def _ident(value: object, name: str) -> str:
    return presence._identifier(value, name)


def _box(raw: object, roi: list[float]) -> list[float]:
    if (not isinstance(raw, list) or len(raw) != 4
        or any(type(x) not in (float, int) or not math.isfinite(x) for x in raw)):
        raise ValueError("Invalid finite normalized box")
    x1, y1, x2, y2 = [float(v) for v in raw]
    if (not 0 <= x1 < x2 <= 1 or not 0 <= y1 < y2 <= 1
        or x1 < roi[0] or y1 < roi[1] or x2 > roi[2] or y2 > roi[3]):
        raise ValueError("Annotation box must be inside the frozen camera ROI")
    return [x1, y1, x2, y2]


def _roi(raw: object) -> list[float]:
    if (not isinstance(raw, list) or len(raw) != 4
        or any(type(v) not in (float, int) or not math.isfinite(v) for v in raw)):
        raise ValueError("Invalid camera ROI")
    x1, y1, x2, y2 = map(float, raw)
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("Camera ROI must fit normalized frame")
    return [x1, y1, x2, y2]


def _video_size(file: Path) -> tuple[int, int]:
    import cv2
    cap = cv2.VideoCapture(str(file))
    try:
        if not cap.isOpened():
            raise ValueError("Pinned localization video cannot decode")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not (32 <= width <= 4096 and 32 <= height <= 4096):
            raise ValueError("Invalid source geometry")
        return width, height
    finally:
        cap.release()


def load(protocol: Path, *, test_fixture: bool = False) -> dict:
    protocol = Path(protocol).expanduser().resolve()
    if not protocol.is_file():
        raise ValueError("Frozen localization protocol missing")
    raw = json.loads(protocol.read_text(encoding="utf-8"))
    if (not isinstance(raw, dict) or raw.get("schema") != "KW_EQUIPMENT_LOCALIZATION_V1"
        or raw.get("status") != "frozen" or type(raw.get("fixture_only")) is not bool
        or raw.get("policy") != POLICY):
        raise ValueError("Unfrozen or unreviewed localization policy")
    if raw["fixture_only"] and not test_fixture:
        raise ValueError("Synthetic localization data cannot qualify")
    base_path = _pin(protocol.parent, raw.get("presence_manifest"), "presence/count protocol")
    base = presence.load(base_path, test_fixture=test_fixture)
    base_doc = json.loads(base_path.read_text(encoding="utf-8"))
    if base_doc["fixture_only"] != raw["fixture_only"]:
        raise ValueError("Count and localization fixture modes disagree")
    annotations = raw.get("annotations")
    if not isinstance(annotations, dict) or len(annotations) != len(base["heldout"]):
        raise ValueError("Require exactly one independent annotation for every held-out recording")
    counts_by_scene = {s["scene_id"]: s for s in base["heldout"]}
    metadata_by_scene = {row["scene_id"]: row for row in base_doc["heldout"]}
    if set(annotations) != set(counts_by_scene):
        raise ValueError("Localization annotations do not match held-out scene IDs")

    camera_rois: dict[tuple[str, str], list[float]] = {}
    scenes = []
    labels_pinned = {}
    total_positive = total_negative = 0
    reviewed_classes = set()
    for scene_id, metadata in annotations.items():
        _ident(scene_id, "held-out scene")
        if not isinstance(metadata, dict):
            raise ValueError("Missing annotation custody")
        expected = {"labels", "roi", "roi_basis", "reviewer_id", "blinded_review",
                    "previously_inspected", "annotation_origin", "license_basis", "privacy_basis"}
        if set(metadata) != expected:
            raise ValueError("Incomplete independent annotation custody")
        if metadata["blinded_review"] is not True or metadata["previously_inspected"] is not False:
            raise ValueError("Reviewer must be blinded to independent held-out source predictions")
        _ident(metadata["reviewer_id"], "independent box reviewer")
        for key in ("roi_basis", "annotation_origin", "license_basis", "privacy_basis"):
            v = metadata[key]
            if (not isinstance(v, str) or len(v.strip()) < 12 or
                (not test_fixture and any(t in v.lower() for t in
                    ("synthetic", "sample", "placeholder", "unknown", "example")))):
                raise ValueError("Missing non-placeholder annotation provenance")
        roi = _roi(metadata["roi"])
        row = metadata_by_scene[scene_id]
        camera = (row["site_id"], row["camera_id"])
        if camera in camera_rois and camera_rois[camera] != roi:
            raise ValueError("Same camera has conflicting frozen ROIs")
        camera_rois[camera] = roi
        file = _pin(protocol.parent, metadata["labels"], "independent box annotations")
        labels_pinned[scene_id] = sha256_file(file)
        annotation = json.loads(file.read_text(encoding="utf-8"))
        if (not isinstance(annotation, dict)
            or set(annotation) != {"schema", "frames"}
            or annotation["schema"] != "KW_EQUIPMENT_BOX_LABELS_V1"
            or not isinstance(annotation["frames"], list)):
            raise ValueError("Invalid independent box annotation document")
        scene = counts_by_scene[scene_id]
        expected_seconds = scene["timestamps"]
        if len(annotation["frames"]) != len(expected_seconds):
            raise ValueError("Localization frame coverage incomplete")
        width, height = _video_size(scene["video"])
        frames = {}
        for expected_second, frame in zip(expected_seconds, annotation["frames"]):
            if (not isinstance(frame, dict) or set(frame) != {"second", "labels"}
                or type(frame["second"]) not in (int, float)
                or not math.isfinite(frame["second"]) or frame["second"] != expected_second
                or not isinstance(frame["labels"], list)
                or len(frame["labels"]) != len(base["model"]["prompts"])):
                raise ValueError("Wrong timestamp or incomplete annotation class matrix")
            item_truth = {}
            for label in frame["labels"]:
                if (not isinstance(label, dict) or set(label) != {"item_id", "state", "boxes"}
                    or label["item_id"] not in base["model"]["prompts"]
                    or label["item_id"] in item_truth
                    or label["state"] not in ("reviewed", "unlabelable")
                    or not isinstance(label["boxes"], list) or len(label["boxes"]) > 250):
                    raise ValueError("Invalid or duplicate per-class independent annotation")
                boxes = [_box(b, roi) for b in label["boxes"]]
                if label["state"] == "unlabelable" and boxes:
                    raise ValueError("Occluded/unlabelable class must abstain, not claim boxes")
                item_truth[label["item_id"]] = {"state": label["state"], "boxes": boxes}
                if label["state"] == "reviewed":
                    reviewed_classes.add(label["item_id"])
                    total_positive += len(boxes)
                    total_negative += int(not boxes)
            if set(item_truth) != set(base["model"]["prompts"]):
                raise ValueError("Every source timestamp must cover every frozen prompt")
            frames[expected_second] = item_truth
        scenes.append({
            "scene_id": scene_id, "video": scene["video"], "sha": scene["sha"],
            "timestamps": expected_seconds, "width": width, "height": height,
            "roi": roi, "truth": frames, "reviewer_id": metadata["reviewer_id"],
        })
    if (len(scenes) < POLICY["min_scored_recordings"]
        or len(reviewed_classes) < POLICY["min_reviewed_classes"]
        or total_positive < POLICY["min_reviewed_positive_boxes"]
        or total_negative < POLICY["min_reviewed_negative_opportunities"]):
        raise ValueError("Insufficient independently reviewable localization support")
    return {
        "manifest_sha256": sha256_file(protocol), "presence_manifest_sha256": base["manifest_sha256"],
        "model": base["model"], "model_dir": base["model_dir"], "model_files": base["files"],
        "scenes": scenes, "annotations_sha256": labels_pinned,
        "prompt_digest": _digest(base["model"]["prompts"]),
    }


def iou(a: list[float], b: list[float]) -> float:
    intersection = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    if intersection == 0:
        return 0.0
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return intersection / (area_a + area_b - intersection)


def match_boxes(truth: list[list[float]], proposals: list[list[float]], threshold: float = 0.5) -> tuple[int, int, int]:
    """Deterministic maximum-cardinality bipartite matching; one prediction per truth."""
    edges = [
        sorted((j for j, pred in enumerate(proposals) if iou(gt, pred) >= threshold),
               key=lambda j: (-iou(gt, proposals[j]), j))
        for gt in truth
    ]
    owner: dict[int, int] = {}
    def augment(i: int, visited: set[int]) -> bool:
        for j in edges[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in owner or augment(owner[j], visited):
                owner[j] = i
                return True
        return False
    for i in range(len(truth)):
        augment(i, set())
    tp = len(owner)
    return tp, len(proposals) - tp, len(truth) - tp


def _normal_predictions(rows: object, scene: dict, prompts: dict) -> dict:
    if not isinstance(rows, dict) or set(rows) != set(scene["timestamps"]):
        raise ValueError("Missing frame proposal is unknown, not an empty frame")
    out = {}
    for second in scene["timestamps"]:
        detections = rows[second]
        if not isinstance(detections, list) or len(detections) != len(prompts):
            raise ValueError("Missing class is unknown, not a zero prediction")
        per_class = {}
        for d in detections:
            if (not isinstance(d, dict) or d.get("proposal_status") != "unreviewed_model_proposal"
                or d.get("label") not in prompts or d["label"] in per_class
                or not isinstance(d.get("boxes"), list)
                or type(d.get("count")) is not int or d["count"] != len(d["boxes"])
                or d["count"] > 250):
                raise ValueError("Unreviewed detector class/count/boxes invalid")
            # Real adapter emits pixel geometry. Injected test detections must
            # obey exactly the same pixel contract, not receive labels or ROI.
            boxes = []
            for b in d["boxes"]:
                if (not isinstance(b, list) or len(b) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in b)):
                    raise ValueError("Invalid detector pixel box")
                normalized = [b[0] / scene["width"], b[1] / scene["height"],
                              b[2] / scene["width"], b[3] / scene["height"]]
                if not (0 <= normalized[0] < normalized[2] <= 1 and
                        0 <= normalized[1] < normalized[3] <= 1):
                    raise ValueError("Detector returned out-of-frame boxes")
                # Restrict score to the frozen camera ROI by box centre.
                cx, cy = (normalized[0]+normalized[2])/2, (normalized[1]+normalized[3])/2
                r = scene["roi"]
                if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                    boxes.append(normalized)
            per_class[d["label"]] = boxes
        out[second] = per_class
    return out


def evaluate(protocol: Path, *, injected: Callable | None = None, test_fixture: bool = False) -> dict:
    if test_fixture != (injected is not None):
        raise ValueError("Synthetic injection allowed ONLY for nonqualifying CI fixtures")
    loaded = load(protocol, test_fixture=test_fixture)
    model = loaded["model"]
    adapter = None
    if not test_fixture:
        adapter = GroundingDinoAdapter(model["prompts"], model_dir=loaded["model_dir"],
             model_files=loaded["model_files"], threshold=model["threshold"],
             nms_iou=model["nms_iou"], device=model["device"])
        adapter.setup()
    totals, per_class = Counter(), {}
    try:
        for scene in loaded["scenes"]:
            # Critical blind split: inference sees source/time only, never labels,
            # reviewer IDs or truth; test injection must respect this contract.
            input_scene = {k:scene[k] for k in ("scene_id", "video", "sha", "timestamps", "width", "height")}
            if test_fixture:
                rows = injected(input_scene, {"prompts": model["prompts"]})
            else:
                adapter.bind_video(scene["video"], scene["sha"])
                rows = {second: adapter.detect_at(second) for second in scene["timestamps"]}
            predictions = _normal_predictions(rows, scene, model["prompts"])
            for second, labels in scene["truth"].items():
                for item, gt in labels.items():
                    if gt["state"] == "unlabelable":
                        totals["abstained"] += 1
                        continue
                    tp, fp, fn = match_boxes(gt["boxes"], predictions[second][item],
                                             POLICY["iou_threshold"])
                    totals.update({"tp": tp, "fp": fp, "fn": fn, "reviewed": 1})
                    totals["reviewed_negative"] += int(not gt["boxes"])
                    bucket = per_class.setdefault(item, Counter())
                    bucket.update({"tp": tp, "fp": fp, "fn": fn, "reviewed": 1})
    finally:
        if adapter:
            adapter.close()
    after = load(protocol, test_fixture=test_fixture)
    for key in ("manifest_sha256", "presence_manifest_sha256", "model_files",
                "annotations_sha256", "prompt_digest"):
        if after[key] != loaded[key]:
            raise ValueError("Frozen localization input or annotation changed during inference")
    if [s["sha"] for s in after["scenes"]] != [s["sha"] for s in loaded["scenes"]]:
        raise ValueError("Equipment recording changed during held-out scoring")
    if verify_model_snapshot(loaded["model_dir"], loaded["model_files"]) != loaded["model_files"]:
        raise ValueError("Frozen model snapshot drift")
    def metrics(bucket: Counter) -> dict:
        tp, fp, fn = (bucket[k] for k in ("tp", "fp", "fn"))
        return {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp+fp) if tp+fp else None,
            "recall": tp / (tp+fn) if tp+fn else None,
            "reviewed_opportunities": bucket["reviewed"],
        }
    return {
        "schema": "KW_EQUIPMENT_LOCALIZATION_RECEIPT_V1",
        "qualified": False,
        "status": "synthetic_localization_test_not_qualified" if test_fixture
                  else "localization_measured_pending_independent_audit",
        "policy": POLICY,
        "metrics": metrics(totals),
        "per_class": {key: metrics(value) for key, value in sorted(per_class.items())},
        "support": {"recordings": len(loaded["scenes"]), "abstained_class_windows": totals["abstained"],
                    "reviewed_negative_class_windows": totals["reviewed_negative"]},
        "provenance": {
            "localization_manifest_sha256": loaded["manifest_sha256"],
            "presence_protocol_sha256": loaded["presence_manifest_sha256"],
            "model_artifact_sha256": loaded["model_files"],
            "prompts_sha256": loaded["prompt_digest"],
            "annotations_sha256_by_scene": loaded["annotations_sha256"],
            "camera_roi_by_scene": {s["scene_id"]: s["roi"] for s in loaded["scenes"]},
            "independent_reviewer_id_by_scene": {s["scene_id"]: s["reviewer_id"] for s in loaded["scenes"]},
            "source_video_sha256_by_scene": {s["scene_id"]: s["sha"] for s in loaded["scenes"]},
            "prediction_source": "synthetic_injection" if test_fixture else "offline_groundingdino",
        },
        "limitations": [
            "Independent reviewer attestations require external audit; this is not a signed certification.",
            "IoU 0.50 box matching does not measure COCO mAP or verified equipment compliance.",
            "Occluded/unlabelable windows abstain; count-only scores must not include them as known zeros.",
            "Verified model and source file SHA-256 values establish file identity, not true model accuracy.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent box localization using pinned equipment model")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(args.manifest)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result = {"schema": "KW_EQUIPMENT_LOCALIZATION_RECEIPT_V1",
                  "qualified": False, "status": "localization_blocked",
                  "reason": str(exc)[:250]}
    target = args.out.expanduser().resolve()
    if target.exists():
        raise SystemExit("Refusing to overwrite an existing frozen qualification receipt")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "qualified": False,
                      "receipt_written": True}))
    if result["status"] == "localization_blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
