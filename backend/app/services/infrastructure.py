from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text())


def aggregate_cached_observations(rows: list[dict]) -> dict[str, dict]:
    per_item: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        for det in row.get("detections", []):
            per_item[det["label"]].append((int(det.get("count", 0)), float(det.get("confidence", 0.0))))
    out: dict[str, dict] = {}
    for label, values in per_item.items():
        counts = sorted(v[0] for v in values)
        out[label] = {
            "observed_count": counts[len(counts)//2],
            "mean_confidence": sum(v[1] for v in values) / len(values),
            "samples": len(values),
        }
    return out


def compare_manifest(manifest: dict, observed: dict[str, dict]) -> list[dict]:
    results: list[dict] = []
    for item in manifest.get("items", []):
        tier = item.get("verification_tier")
        required = item.get("required")
        if tier == "officer_verification_required":
            results.append({
                "id": item["id"], "label": item["label"], "required": required,
                "observed": None, "state": "OFFICER_VERIFICATION_REQUIRED", "confidence": None,
            })
            continue
        obs = observed.get(item["id"], {"observed_count": 0, "mean_confidence": 0.0})
        count = int(obs.get("observed_count", 0))
        confidence = float(obs.get("mean_confidence", 0.0))
        if confidence < 0.55:
            state = "UNCERTAIN"
        elif count >= int(required):
            state = "COMPLIANT"
        else:
            state = "DISCREPANCY"
        results.append({
            "id": item["id"], "label": item["label"], "required": required,
            "observed": count, "state": state, "confidence": round(confidence, 3),
        })
    return results
