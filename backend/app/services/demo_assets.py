from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.config import demo_manifest_path, equipment_cache_path
from app.services.infrastructure import load_manifest


def equipment_cache_metadata_path():
    cache_path = equipment_cache_path()
    return cache_path.with_suffix(cache_path.suffix + ".meta.json")


def load_demo_equipment_metadata() -> dict:
    path = equipment_cache_metadata_path()
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Equipment cache metadata must contain a JSON object: {path}")
    return payload


def verify_equipment_profile_source(
    video_path: Path,
    metadata: dict,
) -> bool | None:
    """Verify that a reviewed equipment profile is applied only to its source clip.

    SHA-256 is preferred when present. SHA-1 remains supported for older reviewed
    metadata and published source checks. Profiles without a source digest return
    None so synthetic/development caches remain usable.
    """
    source = metadata.get("source_video") or {}
    expected_sha256 = str(source.get("sha256", "")).strip().lower()
    expected_sha1 = str(source.get("sha1", "")).strip().lower()
    if not expected_sha256 and not expected_sha1:
        return None

    algorithm = "sha256" if expected_sha256 else "sha1"
    expected = expected_sha256 or expected_sha1
    digest = hashlib.new(algorithm)
    with Path(video_path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expected


def require_equipment_profile_source(
    video_path: Path,
    metadata: dict,
) -> bool | None:
    matched = verify_equipment_profile_source(video_path, metadata)
    if matched is False:
        source_name = str(
            (metadata.get("source_video") or {}).get("filename", "reviewed source clip")
        )
        raise ValueError(
            f"The reviewed equipment profile is frozen to {source_name} "
            "and this video does not match its recorded digest."
        )
    return matched


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
