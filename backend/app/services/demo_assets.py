from __future__ import annotations

import json

from app.config import demo_manifest_path, equipment_cache_path
from app.services.infrastructure import load_manifest


def load_demo_manifest_and_cache() -> tuple[dict, list[dict]]:
    manifest_path = demo_manifest_path()
    cache_path = equipment_cache_path()

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not cache_path.exists():
        raise FileNotFoundError(f"Equipment cache not found: {cache_path}")

    manifest = load_manifest(manifest_path)
    rows = json.loads(cache_path.read_text())
    if not isinstance(rows, list):
        raise ValueError(f"Equipment cache must contain a JSON list: {cache_path}")

    return manifest, rows



def build_compliant_demo_cache(manifest: dict, samples: int = 5) -> list[dict]:
    """Create an explicit stage-safe compliant detector cache for demo portrayal.

    This is synthetic demo telemetry, not measured equipment inference. It exists
    so the walkthrough can demonstrate the system correctly *not* creating a case.
    """
    rows: list[dict] = []
    for sample_index in range(samples):
        detections = []
        for item in manifest.get("items", []):
            if item.get("verification_tier") == "officer_verification_required":
                continue
            detections.append({
                "label": item["id"],
                "count": int(item.get("required", 0)),
                "confidence": 0.95,
            })
        rows.append({
            "second": float(sample_index),
            "detections": detections,
            "source": "synthetic_compliant_demo_profile",
        })
    return rows
