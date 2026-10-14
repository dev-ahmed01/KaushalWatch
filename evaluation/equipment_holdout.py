"""Equipment proposal vs human-reviewed count shadow benchmark.

The shipped equipment adapter does not execute GroundingDINO. Even with
independent labels, SHA-locked caches can only give retrospective proposal
quality: no result from this module is a qualifying LIVE detector accuracy
result. Never mix model_count and reviewed count in one score.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for location in (ROOT, ROOT / "backend"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from evaluation.heldout_qualification import sha256_file

HEX = re.compile(r"^[a-f0-9]{64}$")
POLICY = {
    "policy_id": "equipment-shadow-proposal-v1",
    "min_scenes": 2,
    "min_item_classes": 2,
    "min_positive_examples": 2,
    "min_negative_examples": 2,
}


def pinned(root: Path, spec: object, label: str) -> Path:
    if not isinstance(spec, dict) or set(spec) != {"path", "sha256"}:
        raise ValueError(f"{label} requires path and immutable SHA-256")
    name, digest = spec["path"], spec["sha256"]
    if not isinstance(name, str) or not name.strip() or not isinstance(digest, str) or not HEX.fullmatch(digest):
        raise ValueError(f"{label} has invalid path or SHA-256")
    file = (root / name).resolve()
    if not file.is_file() or not file.stat().st_size or sha256_file(file) != digest:
        raise ValueError(f"{label}: source missing, empty or SHA-256 mismatch")
    return file


def nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label}: count must be a nonnegative integer")
    return value


def load(path: Path) -> dict:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError("Frozen equipment shadow manifest is missing")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or doc.get("status") != "frozen" or doc.get("policy") != POLICY:
        raise ValueError("Frozen equipment shadow evaluation policy is missing or altered")
    if type(doc.get("fixture_only")) is not bool:
        raise ValueError("An explicit synthetic fixture flag is mandatory")
    if not isinstance(doc.get("scenes"), list) or len(doc["scenes"]) < POLICY["min_scenes"]:
        raise ValueError("Insufficient equipment shadow scenes")
    ids, videos, seen_samples, cameras, results, classes = set(), set(), set(), set(), [], set()
    positive = negative = 0
    for scene in doc["scenes"]:
        if not isinstance(scene, dict):
            raise ValueError("Invalid equipment scene")
        sid = scene.get("scene_id")
        camera = scene.get("camera_id")
        if not isinstance(sid, str) or len(sid) < 3 or sid in ids or not isinstance(camera, str) or len(camera) < 3:
            raise ValueError("Equipment scene/camera ID missing or duplicated")
        ids.add(sid)
        cameras.add(camera)
        for label in ("source_origin", "license_basis", "privacy_basis", "independent_label_reviewer"):
            value = scene.get(label)
            if not isinstance(value, str) or len(value.strip()) < 8:
                raise ValueError(f"{label} provenance is required")
        if scene.get("reviewed_independently") is not True:
            raise ValueError("Independent equipment truth annotations are not attested")
        video = pinned(path.parent, scene.get("video"), "video")
        digest = sha256_file(video)
        if digest in videos:
            raise ValueError("Duplicate source video or near-duplicate recording split")
        videos.add(digest)
        cache = pinned(path.parent, scene.get("proposal_cache"), "proposal_cache")
        reviewed = pinned(path.parent, scene.get("human_reviewed_cache"), "human_reviewed_cache")
        truth = pinned(path.parent, scene.get("truth"), "truth")
        proposals = json.loads(cache.read_text(encoding="utf-8"))
        corrections = json.loads(reviewed.read_text(encoding="utf-8"))
        if not isinstance(proposals, list) or not isinstance(corrections, list):
            raise ValueError("Equipment caches must be lists of observations")
        def lookup(rows: list, key: str):
            index = {}
            for entry in rows:
                if not isinstance(entry, dict) or not isinstance(entry.get("items"), dict):
                    raise ValueError(f"{key} cache entry missing count map")
                stamp = entry.get("second")
                if type(stamp) not in (int, float) or stamp < 0 or stamp != stamp or stamp in index:
                    raise ValueError(f"{key} cache time invalid or duplicated")
                for item, count in entry["items"].items():
                    if not isinstance(item, str) or not item:
                        raise ValueError("Empty equipment item ID")
                    nonnegative(count, key)
                index[stamp] = entry["items"]
            return index
        proposal_index = lookup(proposals, "proposal")
        reviewed_index = lookup(corrections, "reviewed")
        with truth.open(newline="", encoding="utf-8-sig") as file:
            rows = csv.DictReader(file, strict=True)
            if rows.fieldnames != ["second", "item_id", "true_count"]:
                raise ValueError("Independent truth must contain exactly second,item_id,true_count")
            label_count = 0
            for record in rows:
                try:
                    second = float(record["second"])
                    truth_count = int(record["true_count"])
                except (TypeError, ValueError) as exc:
                    raise ValueError("Invalid independent equipment observation") from exc
                item = record["item_id"]
                if (not second >= 0 or second == float("inf") or item is None or not item.strip()
                    or truth_count < 0 or str(truth_count) != record["true_count"]):
                    raise ValueError("Invalid equipment timestamp/class/count")
                key = (sid, second, item)
                if key in seen_samples:
                    raise ValueError("Equipment truth scoring opportunity duplicated")
                seen_samples.add(key)
                classes.add(item)
                positive += int(truth_count > 0)
                negative += int(truth_count == 0)
                proposed = proposal_index.get(second, {}).get(item)
                corrected = reviewed_index.get(second, {}).get(item)
                # Missing means abstention/unknown — never silently count as absent.
                if proposed is not None:
                    nonnegative(proposed, "model_proposal")
                if corrected is not None:
                    nonnegative(corrected, "human_reviewed")
                results.append({
                    "scene": sid, "class": item, "truth": truth_count,
                    "proposal": proposed, "reviewed": corrected,
                })
                label_count += 1
            if label_count == 0:
                raise ValueError("Equipment scene needs independent truth observations")
    if (len(classes) < POLICY["min_item_classes"] or positive < POLICY["min_positive_examples"]
        or negative < POLICY["min_negative_examples"]):
        raise ValueError("Insufficient equipment class and positive/negative support")
    return {"rows": results, "scenes": len(ids), "cameras": len(cameras),
            "manifest_sha256": sha256_file(path),
            "sources": videos, "fixture_only": doc["fixture_only"]}


def analyze(path: Path) -> dict:
    dataset = load(path)
    scored = {}
    for kind in ("proposal", "reviewed"):
        tp = fp = fn = tn = evaluated = missed = error_sum = 0
        per_class: dict[str, dict] = {}
        for row in dataset["rows"]:
            prediction = row[kind]
            if prediction is None:
                missed += 1
                continue
            true = row["truth"]
            per = per_class.setdefault(row["class"], {"samples": 0, "mae_numerator": 0})
            per["samples"] += 1
            per["mae_numerator"] += abs(prediction - true)
            evaluated += 1
            error_sum += abs(prediction - true)
            if true > 0 and prediction > 0:
                tp += 1
            elif true == 0 and prediction > 0:
                fp += 1
            elif true > 0:
                fn += 1
            else:
                tn += 1
        scored[kind] = {
            "coverage": evaluated/len(dataset["rows"]),
            "missing_predictions": missed,
            "count_mae": error_sum/evaluated if evaluated else None,
            "positive_recall_on_scored": tp/(tp+fn) if tp+fn else None,
            "false_presence_rate_on_scored": fp/(fp+tn) if fp+tn else None,
            "scored_confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "per_item_count_mae_on_scored": {
                item: round(val["mae_numerator"]/val["samples"], 5)
                for item, val in sorted(per_class.items()) if val["samples"]
            },
        }
    after = load(path)
    if after["manifest_sha256"] != dataset["manifest_sha256"] or after["sources"] != dataset["sources"]:
        raise ValueError("Frozen equipment inputs changed during scoring")
    return {
        "status": "synthetic_shadow_diagnostic" if dataset["fixture_only"] else "reviewed_cache_shadow_not_live_model",
        "qualified": False,
        "live_model_executed": False,
        "prediction_origin": "pinned_cached_proposals_and_separately_reviewed_counts",
        "policy_id": POLICY["policy_id"],
        "manifest_sha256": dataset["manifest_sha256"],
        "support": {"scenes": dataset["scenes"], "cameras": dataset["cameras"],
                    "independent_truth_opportunities": len(dataset["rows"])},
        "metrics": scored,
        "limitations": [
            "The release GroundingDINO adapter has no live inference implementation.",
            "Cached proposals are not independently reproducible live detector outputs.",
            "The reviewer-corrected count must never be described as model-only accuracy.",
            "Missing item predictions are unknown, not count zero; coverage is disclosed.",
            "Count-presence accuracy is not bounding-box localization accuracy.",
            "Live model inference, immutable weights and independent camera footage remain release blockers.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Nonqualifying cached equipment shadow diagnostic")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.manifest)
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result = {"qualified": False, "status": "equipment_shadow_blocked", "reason": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    # A shadow diagnostic is useful but is NEVER a live model qualification.
    if result["status"] == "equipment_shadow_blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
