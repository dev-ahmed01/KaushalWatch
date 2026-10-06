from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_PATH = (
    REPO_ROOT
    / "configs"
    / "vision_profiles"
    / "kaushalwatch-fixed-camera-v1.json"
)
DATASET_DIR = REPO_ROOT / "configs" / "datasets"


def _resolve_repo_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def active_profile_path() -> Path:
    raw = os.getenv("KAUSHALWATCH_VISION_PROFILE")
    return _resolve_repo_path(raw) if raw else DEFAULT_PROFILE_PATH


def validate_vision_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_sections = {
        "deployment",
        "person_detection",
        "attendance",
        "practical_activity",
        "camera_trust",
        "infrastructure",
        "operability",
        "evaluation",
    }
    if not str(profile.get("profile_id") or "").strip():
        errors.append("profile_id is required")
    missing = sorted(required_sections - set(profile))
    if missing:
        errors.append("missing sections: " + ", ".join(missing))

    detector = profile.get("person_detection") or {}
    confidence = detector.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 < float(confidence) < 1:
        errors.append("person_detection.confidence must be between 0 and 1")

    attendance = profile.get("attendance") or {}
    if attendance.get("count_source") not in {"confirmed", "registered"}:
        errors.append("attendance.count_source must be confirmed or registered")
    smoother = attendance.get("smoother_window")
    if not isinstance(smoother, int) or smoother < 1:
        errors.append("attendance.smoother_window must be a positive integer")
    persistence = attendance.get("persistence_threshold")
    if not isinstance(persistence, (int, float)) or not 0 <= float(persistence) <= 1:
        errors.append("attendance.persistence_threshold must be between 0 and 1")

    practical = profile.get("practical_activity") or {}
    if practical.get("geometry_policy") != "same_fixed_camera_view_only":
        errors.append(
            "practical_activity.geometry_policy must preserve fixed-camera geometry"
        )

    infrastructure = profile.get("infrastructure") or {}
    for key in (
        "job_role_manifest",
        "reviewed_cache",
        "reviewed_cache_metadata",
    ):
        raw = infrastructure.get(key)
        if not raw:
            errors.append(f"infrastructure.{key} is required")
        elif not _resolve_repo_path(str(raw)).exists():
            errors.append(f"infrastructure.{key} does not exist: {raw}")

    zone_config = practical.get("zone_config")
    if zone_config and not _resolve_repo_path(str(zone_config)).exists():
        errors.append(f"practical_activity.zone_config does not exist: {zone_config}")

    return errors


def load_vision_profile(path: Path | None = None) -> dict[str, Any]:
    selected = path or active_profile_path()
    if not selected.exists():
        raise FileNotFoundError(f"Vision profile not found: {selected}")
    try:
        profile = json.loads(selected.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Vision profile is invalid JSON: {selected}") from exc
    if not isinstance(profile, dict):
        raise ValueError("Vision profile root must be a JSON object")
    errors = validate_vision_profile(profile)
    if errors:
        raise ValueError("Invalid vision profile: " + "; ".join(errors))
    return profile


def validate_dataset_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    dataset_id = str(manifest.get("dataset_id") or "").strip()
    if not dataset_id:
        errors.append("dataset_id is required")

    camera = manifest.get("camera")
    if not isinstance(camera, dict):
        errors.append("camera object is required")
    elif camera.get("mode") != "fixed_camera":
        warnings.append(
            "KaushalWatch is tuned for fixed-camera footage; moving-camera data "
            "must not be promoted without a separate profile."
        )

    splits = manifest.get("splits")
    if not isinstance(splits, list) or not splits:
        errors.append("at least one split is required")
        splits = []

    roles = {
        str(item.get("role") or "")
        for item in splits
        if isinstance(item, dict)
    }
    status = str(manifest.get("status") or "")
    candidate = status in {"candidate", "calibration_candidate", "promotion_candidate"}
    if candidate:
        if "calibration" not in roles:
            errors.append("candidate dataset requires a calibration split")
        if not ({"held_out", "held_out_benchmark"} & roles):
            errors.append("candidate dataset requires a held-out split")

    purposes = {
        str(item)
        for item in (manifest.get("purpose") or [])
        if str(item).strip()
    }
    annotation_keys = set()
    for item in splits:
        if not isinstance(item, dict):
            continue
        annotations = item.get("annotations")
        if isinstance(annotations, dict):
            annotation_keys.update(
                key for key, value in annotations.items() if value
            )
        labels = item.get("labels")
        if isinstance(labels, list):
            annotation_keys.update(str(label) for label in labels)

    purpose_requirements = {
        "attendance": {"attendance_counts_csv", "occupancy_count"},
        "person_detection": {"person_boxes"},
        "practical_activity": {"work_zones_json"},
        "infrastructure": {"equipment_csv"},
        "operability": {"operability_csv"},
        "camera_trust": {"camera_events_csv"},
    }
    coverage: dict[str, bool] = {}
    for purpose in sorted(purposes):
        expected = purpose_requirements.get(purpose, set())
        coverage[purpose] = bool(expected & annotation_keys) if expected else True
        if candidate and expected and not coverage[purpose]:
            warnings.append(
                f"{purpose} is declared but no matching annotation field is populated"
            )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "dataset_id": dataset_id or None,
        "status": status or None,
        "purposes": sorted(purposes),
        "split_roles": sorted(role for role in roles if role),
        "annotation_coverage": coverage,
    }


def load_dataset_manifests() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not DATASET_DIR.exists():
        return rows
    for path in sorted(DATASET_DIR.glob("*.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            rows.append({
                "path": str(path.relative_to(REPO_ROOT)),
                "valid": False,
                "errors": [str(exc)],
            })
            continue
        if not isinstance(manifest, dict):
            rows.append({
                "path": str(path.relative_to(REPO_ROOT)),
                "valid": False,
                "errors": ["manifest root must be a JSON object"],
            })
            continue
        validation = validate_dataset_manifest(manifest)
        rows.append({
            "path": str(path.relative_to(REPO_ROOT)),
            "manifest": manifest,
            **validation,
        })
    return rows


def _detector_runtime(detector: object) -> dict[str, Any]:
    info = getattr(detector, "info", detector)
    return {
        "backend": getattr(info, "backend", "unknown"),
        "mode": getattr(info, "mode", "unknown"),
        "authoritative": bool(getattr(info, "authoritative", False)),
        "message": str(getattr(info, "message", "")),
        "confidence": getattr(detector, "confidence", None),
        "tiled": getattr(detector, "tiled", None),
        "tile_overlap": getattr(detector, "tile_overlap", None),
        "tile_nms_iou": getattr(detector, "tile_nms_iou", None),
    }


def _setting(env_name: str, fallback: Any, cast):
    raw = os.getenv(env_name)
    if raw is None:
        return fallback
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return raw


def _flag(env_name: str, fallback: bool) -> bool:
    raw = os.getenv(env_name)
    if raw is None:
        return fallback
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_vision_governance(*, detector: object) -> dict[str, Any]:
    path = active_profile_path()
    profile = load_vision_profile(path)
    runtime = _detector_runtime(detector)
    expected_detector = profile["person_detection"]
    expected_attendance = profile["attendance"]

    expected = {
        "backend": expected_detector["backend"],
        "confidence": float(expected_detector["confidence"]),
        "tiled": bool(expected_detector["tiled"]),
        "tile_overlap": float(expected_detector["tile_overlap"]),
        "tile_nms_iou": float(expected_detector["tile_nms_iou"]),
        "count_source": expected_attendance["count_source"],
        "smoother_window": int(expected_attendance["smoother_window"]),
    }
    effective = {
        **runtime,
        "count_source": os.getenv(
            "KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE",
            "registered",
        ).strip().lower(),
        "smoother_window": _setting(
            "KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW",
            5,
            int,
        ),
    }

    checks = {
        "backend": effective["backend"] == expected["backend"],
        "confidence": (
            effective["confidence"] is not None
            and abs(float(effective["confidence"]) - expected["confidence"]) < 1e-9
        ),
        "tiled": effective["tiled"] is expected["tiled"],
        "tile_overlap": (
            effective["tile_overlap"] is not None
            and abs(float(effective["tile_overlap"]) - expected["tile_overlap"]) < 1e-9
        ),
        "tile_nms_iou": (
            effective["tile_nms_iou"] is not None
            and abs(float(effective["tile_nms_iou"]) - expected["tile_nms_iou"]) < 1e-9
        ),
        "count_source": effective["count_source"] == expected["count_source"],
        "smoother_window": effective["smoother_window"] == expected["smoother_window"],
    }
    aligned = all(checks.values()) and bool(effective["authoritative"])

    manifests = load_dataset_manifests()
    datasets = [
        {
            "dataset_id": item.get("dataset_id"),
            "status": item.get("status"),
            "path": item.get("path"),
            "valid": item.get("valid"),
            "purposes": item.get("purposes", []),
            "split_roles": item.get("split_roles", []),
            "annotation_coverage": item.get("annotation_coverage", {}),
            "warnings": item.get("warnings", []),
            "is_template": str(item.get("path") or "").endswith(".template.json"),
        }
        for item in manifests
    ]

    infra = profile["infrastructure"]
    equipment_meta_path = _resolve_repo_path(infra["reviewed_cache_metadata"])
    equipment_meta = json.loads(equipment_meta_path.read_text(encoding="utf-8"))

    return {
        "profile": {
            "profile_id": profile["profile_id"],
            "status": profile.get("status"),
            "path": str(path.relative_to(REPO_ROOT))
            if path.is_relative_to(REPO_ROOT)
            else str(path),
            "valid": True,
        },
        "runtime_alignment": {
            "aligned": aligned,
            "checks": checks,
            "expected": expected,
            "effective": effective,
            "note": (
                "Alignment means the running detector/attendance settings match the "
                "frozen profile. It is not a claim of general real-world accuracy."
            ),
        },
        "engines": {
            "attendance": {
                "profiled": True,
                "runtime_authoritative": bool(effective["authoritative"]),
                "detector_backend": effective["backend"],
                "claim_boundary": (
                    "Anonymous visual occupancy is compared with an external reported "
                    "attendance value; no worker identity is retained."
                ),
            },
            "practical_activity": {
                "profiled": True,
                "zone_config": profile["practical_activity"]["zone_config"],
                "geometry_policy": profile["practical_activity"]["geometry_policy"],
                "claim_boundary": (
                    "Worker-centric motion/work-cell evidence is an activity proxy, "
                    "not skill quality or individual productivity."
                ),
            },
            "infrastructure": {
                "profiled": True,
                "adapter": infra["observation_adapter"],
                "source_digest_required": bool(infra["source_digest_required"]),
                "reviewed_source_sha256": (
                    equipment_meta.get("source_video") or {}
                ).get("sha256"),
                "claim_boundary": infra["quantity_claim"],
            },
            "operability": {
                "profiled": True,
                "method": profile["operability"]["method"],
                "claim_boundary": profile["operability"]["claim_boundary"],
            },
            "camera_trust": {
                "profiled": True,
                "thresholds": profile["camera_trust"],
                "claim_boundary": (
                    "Untrusted camera evidence suspends dependent conclusions."
                ),
            },
        },
        "datasets": datasets,
        "evaluation": profile["evaluation"],
        "promotion_ready": {
            "profile_valid": True,
            "runtime_aligned": aligned,
            "candidate_dataset_registered": any(
                item.get("status") in {
                    "candidate",
                    "calibration_candidate",
                    "promotion_candidate",
                }
                and not item.get("is_template")
                for item in datasets
            ),
            "note": (
                "A new profile should be promoted only after calibration and separate "
                "held-out evaluation are registered and reviewed."
            ),
        },
    }
