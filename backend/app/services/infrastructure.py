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
            per_item[det["label"]].append(
                (int(det.get("count", 0)), float(det.get("confidence", 0.0)))
            )

    out: dict[str, dict] = {}
    for label, values in per_item.items():
        counts = [v[0] for v in values]
        confidences = [v[1] for v in values]
        ordered = sorted(counts)
        out[label] = {
            "observed_count": ordered[len(ordered) // 2],
            "mean_confidence": sum(confidences) / len(confidences),
            "samples": len(values),
            # Kept for temporal consensus. These are tiny demo/edge telemetry arrays,
            # not raw video or identity data.
            "sample_counts": counts,
            "sample_confidences": confidences,
        }
    return out


def compare_manifest(
    manifest: dict,
    observed: dict[str, dict],
    confidence_threshold: float = 0.55,
) -> list[dict]:
    results: list[dict] = []

    for item in manifest.get("items", []):
        tier = item.get("verification_tier")
        required = item.get("required")
        persistence_required = float(item.get("temporal_required_ratio") or 0.8)

        if tier == "officer_verification_required":
            results.append({
                "id": item["id"],
                "label": item["label"],
                "required": required,
                "observed": None,
                "state": "OFFICER_VERIFICATION_REQUIRED",
                "confidence": None,
                "samples": 0,
                "deficit_ratio": None,
                "required_persistence_ratio": None,
            })
            continue

        obs = observed.get(
            item["id"],
            {
                "observed_count": 0,
                "mean_confidence": 0.0,
                "samples": 0,
                "sample_counts": [],
                "sample_confidences": [],
            },
        )
        count = int(obs.get("observed_count", 0))
        confidence = float(obs.get("mean_confidence", 0.0))
        sample_counts = [int(x) for x in obs.get("sample_counts", [])]
        sample_confidences = [float(x) for x in obs.get("sample_confidences", [])]

        confident_counts = [
            c for c, conf in zip(sample_counts, sample_confidences)
            if conf >= confidence_threshold
        ]

        if not confident_counts or confidence < confidence_threshold:
            state = "UNCERTAIN"
            deficit_ratio = None
        else:
            deficit_samples = sum(c < int(required) for c in confident_counts)
            deficit_ratio = deficit_samples / len(confident_counts)
            # Temporal Proof: a transient bad observation does not create a violation.
            state = (
                "DISCREPANCY"
                if deficit_ratio >= persistence_required
                else "COMPLIANT"
            )

        results.append({
            "id": item["id"],
            "label": item["label"],
            "required": required,
            "observed": count,
            "state": state,
            "confidence": round(confidence, 3),
            "samples": len(confident_counts),
            "deficit_ratio": round(deficit_ratio, 3) if deficit_ratio is not None else None,
            "required_persistence_ratio": persistence_required,
        })

    return results
