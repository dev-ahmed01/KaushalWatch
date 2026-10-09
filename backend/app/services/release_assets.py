"""Strict, read-only qualification of locally stored SIH release media.

A manifest is not an assertion of detector accuracy: it pins real files and
annotation provenance so later evaluation can be reproduced. All files stay
local and outputs contain no footage or annotation rows.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2

REQUIRED_ROLES = frozenset({
    "attendance", "practical", "infrastructure", "operability", "camera_degraded"
})
REQUIRED_ANNOTATIONS = {
    "attendance": {"sample_id", "true_count", "pred_count", "true_issue", "pred_issue"},
    "equipment": {"sample_id", "item_id", "true_count", "pred_count"},
    "operability": {"sample_id", "item_id", "true_state", "pred_state"},
    "cases": {"sample_id", "case_type", "true_issue", "pred_issue"},
}
PLACEHOLDERS = {"", "tbd", "unknown", "todo", "placeholder", "example", "replace", "n/a"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg"}


def _nonplaceholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    clean = value.strip()
    return bool(clean) and clean.lower() not in PLACEHOLDERS and not any(
        marker in clean.lower() for marker in ("replace_with", "example-", "insert_here")
    )


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdefABCDEF" for char in value)
        and len(set(value.lower())) > 1
    )


def _resolve(manifest_path: Path, value: Any) -> Path | None:
    if not _nonplaceholder(value):
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (manifest_path.parent / path).resolve()


def _digest(path: Path, memo: dict[Path, str]) -> str:
    if path not in memo:
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(block)
        memo[path] = sha.hexdigest()
    return memo[path]


def _video_info(path: Path) -> dict[str, float | int] | None:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return None
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        readable, frame = capture.read()
    finally:
        capture.release()
    if not readable or frame is None or fps <= 0 or count <= 0 or width <= 0 or height <= 0:
        return None
    return {
        "fps": round(fps, 4), "frame_count": count, "width": width, "height": height,
        "duration_seconds": round(count / fps, 3),
    }


def qualify_release_assets(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    checks: list[dict[str, Any]] = []
    digests: dict[Path, str] = {}

    def record(code: str, passed: bool, detail: str) -> None:
        checks.append({"check": code, "ok": bool(passed), "detail": detail})

    def check_file(code: str, entry: Any, *, video: bool = False) -> tuple[Path | None, dict | None]:
        if not isinstance(entry, dict):
            record(code, False, "file specification is missing")
            return None, None
        path = _resolve(manifest_path, entry.get("path"))
        expected = entry.get("sha256")
        if path is None or not path.is_file() or path.stat().st_size == 0:
            record(code, False, "source file is missing or empty")
            return None, None
        if not _sha256(expected):
            record(code, False, "immutable SHA-256 is missing or still a placeholder")
            return path, None
        actual = _digest(path, digests)
        if actual != expected.lower():
            record(code, False, "SHA-256 mismatch; source must not be silently replaced")
            return path, None
        info = None
        if video:
            info = _video_info(path) if path.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS else None
            if info is None:
                record(code, False, "hash matched, but file is not a readable supported video")
                return path, None
        record(code, True, "SHA-256 matches" + ("; video metadata verified" if video else ""))
        return path, info

    if not manifest_path.is_file():
        record("asset_manifest", False, "local release asset manifest not found")
        return {"ready": False, "manifest_sha256": None, "checks": checks, "claim_boundary": "No final-media claims."}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record("asset_manifest", False, "manifest cannot be read as JSON")
        return {"ready": False, "manifest_sha256": None, "checks": checks, "claim_boundary": "No final-media claims."}

    if not isinstance(data, dict):
        record("asset_manifest", False, "manifest must be a JSON object")
        return {"ready": False, "manifest_sha256": None, "checks": checks, "claim_boundary": "No final-media claims."}

    record("schema_version", data.get("schema_version") == 1, "expected schema version 1")
    record("manifest_frozen", data.get("status") == "frozen" and ".example." not in manifest_path.name,
           "manifest must be frozen and not an example file")

    scenario = data.get("scenario")
    scenario_path, _ = check_file("scenario_digest", scenario)
    scenario_data: dict[str, Any] = {}
    if scenario_path and scenario_path.is_file():
        try:
            loaded = json.loads(scenario_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                scenario_data = loaded
        except (ValueError, OSError):
            pass
    record("scenario_identity", bool(
        scenario_data and ".example." not in (scenario_path.name if scenario_path else "")
        and _nonplaceholder(scenario_data.get("scenario_id"))
        and "EXAMPLE" not in str(scenario_data.get("status", "")).upper()
    ), "scenario ID must identify a frozen, non-example scenario")

    assets = data.get("assets")
    if not isinstance(assets, list):
        assets = []
    ids: set[str] = set()
    roles: set[str] = set()
    asset_metadata: dict[str, dict[str, Any]] = {}
    asset_paths: dict[str, Path] = {}
    for index, item in enumerate(assets):
        if not isinstance(item, dict):
            record(f"asset_{index}_shape", False, "asset row must be an object")
            continue
        asset_id, role = item.get("id"), item.get("role")
        valid_id = _nonplaceholder(asset_id) and asset_id not in ids
        record(f"asset_{index}_identity", bool(valid_id), "unique non-placeholder asset id required")
        if valid_id:
            ids.add(asset_id)
        if isinstance(role, str) and role in REQUIRED_ROLES:
            record(f"asset_{index}_unique_role", role not in roles,
                   "one frozen asset entry is required for each video role")
            roles.add(role)
        else:
            record(f"asset_{index}_role", False, "unsupported asset role")
        record(f"asset_{index}_provenance", all(_nonplaceholder(item.get(key)) for key in
            ("origin", "license", "privacy_basis", "centre_id", "batch_id")),
            "origin/license/privacy basis and centre/batch mapping required")
        path, metadata = check_file(f"asset_{index}_sha256_video", item, video=True)
        if valid_id and path:
            asset_paths[asset_id] = path
        if valid_id and metadata:
            asset_metadata[asset_id] = metadata
    record("required_video_roles", roles == REQUIRED_ROLES, f"expected exactly these roles: {sorted(REQUIRED_ROLES)}")

    annotations = data.get("annotations")
    if not isinstance(annotations, list):
        annotations = []
    annotation_kinds: set[str] = set()
    for index, item in enumerate(annotations):
        if not isinstance(item, dict):
            record(f"annotation_{index}_shape", False, "annotation row must be an object")
            continue
        kind = item.get("kind")
        if isinstance(kind, str) and kind in REQUIRED_ANNOTATIONS and kind not in annotation_kinds:
            annotation_kinds.add(kind)
        else:
            record(f"annotation_{index}_kind", False, "duplicate or unsupported annotation kind")
        record(f"annotation_{index}_independence",
               item.get("independent_of_predictions") is True and _nonplaceholder(item.get("reviewer_id")),
               "independently labelled source and reviewer ID required")
        path, _ = check_file(f"annotation_{index}_sha256", item)
        record(f"annotation_{index}_not_example", bool(path and ".example." not in path.name),
               "example annotations cannot establish final measured accuracy")
        if path and path.is_file():
            try:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.DictReader(handle)
                    columns = set(reader.fieldnames or [])
                    samples = list(reader)
                valid = (
                    isinstance(kind, str) and kind in REQUIRED_ANNOTATIONS
                    and REQUIRED_ANNOTATIONS[kind].issubset(columns)
                    and bool(samples)
                    and all(all(str(row.get(name) or "").strip() for name in REQUIRED_ANNOTATIONS[kind])
                            for row in samples)
                )
                # Ground-truth negatives are essential for meaningful case FP/TN.
                if kind == "cases":
                    values = {row.get("true_issue", "").strip().lower() for row in samples}
                    valid = valid and {"true", "false"}.issubset(values)
            except (OSError, UnicodeError, csv.Error, ValueError):
                valid = False
            record(f"annotation_{index}_schema", valid,
                   "required columns, non-empty labels, and negative case opportunities")
    record("required_annotations", annotation_kinds == set(REQUIRED_ANNOTATIONS),
           "attendance, equipment, operability and cases annotations all required")

    equipment = data.get("equipment_cache")
    cache_path, _ = check_file("equipment_cache_digest", equipment)
    record("equipment_cache_not_example", bool(cache_path and ".example." not in cache_path.name),
           "synthetic example cache cannot stand in for a reviewed final source")
    meta_path, _ = check_file("equipment_cache_metadata_digest",
                             equipment.get("metadata") if isinstance(equipment, dict) else None)
    if isinstance(equipment, dict):
        asset_id = equipment.get("asset_id")
    else:
        asset_id = None
    bound = False
    if meta_path and meta_path.is_file() and isinstance(asset_id, str) and asset_id in asset_paths:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            source = meta.get("source_video", {})
            bound = (
                _sha256(source.get("sha256"))
                and source["sha256"].lower() == _digest(asset_paths[asset_id], digests)
                and isinstance(meta.get("review"), dict)
                and bool(meta["review"])
            )
            if asset_id not in asset_metadata:
                bound = False
        except (ValueError, OSError, TypeError, AttributeError):
            pass
    record("equipment_cache_bound_to_source", bound and asset_id is not None and
           any(i.get("id") == asset_id and i.get("role") == "infrastructure" for i in assets if isinstance(i, dict)),
           "reviewed equipment metadata must identify the exact infrastructure clip by SHA-256")

    operability = data.get("operability") if isinstance(data.get("operability"), dict) else {}
    op_id = operability.get("asset_id")
    info = asset_metadata.get(op_id) if isinstance(op_id, str) else None
    op_role = any(i.get("id") == op_id and i.get("role") == "operability" for i in assets if isinstance(i, dict))
    roi = operability.get("roi")
    window = operability.get("window")
    try:
        coords = [int(roi[key]) for key in ("x1", "y1", "x2", "y2")]
        start, end = float(window["start_sec"]), float(window["end_sec"])
        valid = bool(info) and op_role and 0 <= coords[0] < coords[2] <= info["width"] and (
            0 <= coords[1] < coords[3] <= info["height"])
        valid = valid and math.isfinite(start) and math.isfinite(end) and (
            0 <= start < end <= info["duration_seconds"] + 1e-6)
        cuts = operability.get("camera_cuts")
        valid = valid and isinstance(cuts, list)
        if isinstance(cuts, list):
            for cut in cuts:
                cut_start, cut_end = float(cut["start_sec"]), float(cut["end_sec"])
                valid = valid and math.isfinite(cut_start) and math.isfinite(cut_end) and (
                    0 <= cut_start < cut_end <= info["duration_seconds"] + 1e-6)
                valid = valid and not (start < cut_end and cut_start < end)
    except (KeyError, ValueError, TypeError, OverflowError):
        valid = False
    record("operability_stable_roi_window", bool(valid),
           "ROI and stable measurement interval must fit clip and exclude documented camera cuts")

    practical = data.get("practical") if isinstance(data.get("practical"), dict) else {}
    p_id = practical.get("asset_id")
    valid_practical = (
        any(i.get("id") == p_id and i.get("role") == "practical" for i in assets if isinstance(i, dict))
        and isinstance(practical.get("authorization"), str)
        and practical.get("authorization") in {"valid", "absent", "unknown"}
        and _nonplaceholder(practical.get("zone_profile"))
    )
    record("practical_authorization_context", valid_practical,
           "practical clip must have zone profile and explicitly documented authorization input")

    primary_id = scenario.get("primary_asset_id") if isinstance(scenario, dict) else None
    primary = next((i for i in assets if isinstance(i, dict) and i.get("id") == primary_id), None)
    record("scenario_asset_binding", bool(
        primary and isinstance(primary_id, str) and primary_id in asset_metadata and
        primary.get("centre_id") == scenario_data.get("centre_id") and
        primary.get("batch_id") == scenario_data.get("batch_id")
    ), "frozen scenario must identify the exact centre/batch and primary reviewed clip")

    return {
        "ready": bool(checks) and all(check["ok"] for check in checks),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "asset_roles_seen": sorted(roles),
        "checks": checks,
        "claim_boundary": (
            "File identity, provenance and annotation-schema qualification only; "
            "not model precision, recall, equipment accuracy or authorization truth."
        ),
    }
