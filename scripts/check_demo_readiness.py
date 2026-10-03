from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import demo_manifest_path, equipment_cache_path, demo_scenario_path


REQUIRED_SCENARIO_EVENTS = {
    "baseline",
    "attendance_discrepancy",
    "infrastructure_discrepancy",
    "operability_proxy",
    "camera_integrity",
    "offline_sync",
    "duplicate_evidence",
}


def check_json(path: Path, expected_type: type) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path}"
    try:
        value = json.loads(path.read_text())
    except Exception as exc:
        return False, f"invalid JSON: {path}: {exc}"
    if not isinstance(value, expected_type):
        return False, f"unexpected JSON type in {path}: expected {expected_type.__name__}"
    return True, "ok"


def inspect_video(path: Path) -> tuple[bool, str, dict]:
    if not path.exists() or path.stat().st_size <= 0:
        return False, f"missing or empty: {path}", {}

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return False, f"OpenCV could not open: {path}", {}

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, frame = cap.read()
        if not ok or frame is None:
            return False, f"video opened but first frame could not be read: {path}", {}
    finally:
        cap.release()

    duration_seconds = frame_count / fps if frame_count > 0 and fps > 0 else None
    metadata = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "fps": round(fps, 4),
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": round(duration_seconds, 3) if duration_seconds is not None else None,
    }
    valid = fps > 0 and frame_count > 0 and width > 0 and height > 0
    return valid, "ok" if valid else f"invalid video metadata: {metadata}", metadata


def check_operability_roi(
    scenario: dict,
    *,
    width: int,
    height: int,
) -> tuple[bool, str]:
    roi = scenario.get("operability_roi") or {}
    required = ("x1", "y1", "x2", "y2")
    if not all(key in roi for key in required):
        return False, "operability_roi must define x1,y1,x2,y2"

    try:
        x1, y1, x2, y2 = (int(roi[key]) for key in required)
    except (TypeError, ValueError):
        return False, "operability_roi coordinates must be integers"

    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        return False, f"invalid ROI ordering/bounds: {(x1, y1, x2, y2)}"
    if width > 0 and height > 0 and (x2 > width or y2 > height):
        return False, (
            f"ROI {(x1, y1, x2, y2)} exceeds video dimensions "
            f"{width}x{height}"
        )
    return True, f"ROI {(x1, y1, x2, y2)} within {width}x{height}"


def required_cache_labels(manifest: dict) -> set[str]:
    return {
        str(item.get("id"))
        for item in manifest.get("items", [])
        if item.get("id")
        and item.get("verification_tier") != "officer_verification_required"
    }


def final_mode_checks(
    scenario: dict,
    *,
    scenario_path: Path,
    cache_path: Path,
    detector: str,
) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    status = str(scenario.get("status", "")).strip()
    is_example = "EXAMPLE" in status.upper() or ".example." in scenario_path.name
    checks.append((
        "final_scenario_not_example",
        not is_example,
        "ok" if not is_example else "replace the checked-in example scenario with the exact recorded scenario",
    ))

    cache_is_example = ".example." in cache_path.name
    checks.append((
        "final_equipment_cache_not_example",
        not cache_is_example,
        "ok" if not cache_is_example else "point KAUSHALWATCH_EQUIPMENT_CACHE at reviewed detections from the exact final clip",
    ))

    checks.append((
        "final_detector_openvino",
        detector == "openvino",
        f"configured detector: {detector}",
    ))

    event_names = {
        str(row.get("event"))
        for row in scenario.get("events_to_record", [])
        if isinstance(row, dict)
    }
    missing_events = sorted(REQUIRED_SCENARIO_EVENTS - event_names)
    checks.append((
        "final_scenario_event_coverage",
        not missing_events,
        "ok" if not missing_events else f"missing scenario events: {missing_events}",
    ))

    roi_note = str((scenario.get("operability_roi") or {}).get("note", ""))
    placeholder_roi = "replace" in roi_note.lower()
    checks.append((
        "final_operability_roi_frozen",
        not placeholder_roi,
        "ok" if not placeholder_roi else "replace placeholder ROI coordinates/note after final camera framing",
    ))

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="KaushalWatch final-demo readiness check")
    parser.add_argument("--video", default=os.getenv("KAUSHALWATCH_DEMO_VIDEO"))
    parser.add_argument("--require-openvino", action="store_true")
    parser.add_argument(
        "--final",
        action="store_true",
        help=(
            "Fail closed on example scenario/cache, placeholder ROI, missing scenario events, "
            "or a non-OpenVINO attendance detector."
        ),
    )
    args = parser.parse_args()

    checks: list[tuple[str, bool, str]] = []
    video_metadata: dict = {}

    manifest_path = demo_manifest_path()
    cache_path = equipment_cache_path()
    scenario_path = demo_scenario_path()

    ok, note = check_json(manifest_path, dict)
    checks.append(("manifest", ok, note))
    ok, note = check_json(cache_path, list)
    checks.append(("equipment_cache", ok, note))
    ok, note = check_json(scenario_path, dict)
    checks.append(("scenario", ok, note))

    scenario = json.loads(scenario_path.read_text()) if scenario_path.exists() else {}

    if args.video:
        video = Path(args.video).expanduser().resolve()
        ok, note, video_metadata = inspect_video(video)
        checks.append(("demo_video_readable", ok, note))
        if video_metadata:
            roi_ok, roi_note = check_operability_roi(
                scenario,
                width=int(video_metadata.get("width", 0)),
                height=int(video_metadata.get("height", 0)),
            )
            checks.append(("operability_roi_within_video", roi_ok, roi_note))
    else:
        checks.append((
            "demo_video_readable",
            False,
            "KAUSHALWATCH_DEMO_VIDEO/--video not configured",
        ))

    detector = os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "hog").strip().lower()
    if args.require_openvino or args.final or detector == "openvino":
        raw = os.getenv(
            "KAUSHALWATCH_OPENVINO_MODEL_XML",
            "../models/openvino/person-detection-retail-0013/FP16/person-detection-retail-0013.xml",
        )
        model = Path(raw).expanduser()
        if not model.is_absolute():
            model = (BACKEND / model).resolve()
        bin_path = model.with_suffix(".bin")
        checks.append(("openvino_xml", model.exists(), str(model)))
        checks.append(("openvino_bin", bin_path.exists(), str(bin_path)))

    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else []
    manifest_ids = required_cache_labels(manifest)
    cache_labels = {
        det.get("label")
        for row in cache if isinstance(row, dict)
        for det in row.get("detections", [])
        if isinstance(det, dict)
    }
    missing_cache_labels = sorted(x for x in manifest_ids if x and x not in cache_labels)
    checks.append((
        "manifest_cache_alignment",
        not missing_cache_labels,
        "ok" if not missing_cache_labels else f"missing cache labels: {missing_cache_labels}",
    ))

    if args.final:
        checks.extend(
            final_mode_checks(
                scenario,
                scenario_path=scenario_path,
                cache_path=cache_path,
                detector=detector,
            )
        )

    rows = [
        {"check": name, "ok": ok, "detail": detail}
        for name, ok, detail in checks
    ]
    payload = {
        "ready": all(row["ok"] for row in rows),
        "mode": "final" if args.final else "configuration",
        "video": video_metadata,
        "checks": rows,
        "claim_boundary": (
            "Readiness validates assets/configuration only. It does not create or validate final accuracy claims."
        ),
    }
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if payload["ready"] else 2)


if __name__ == "__main__":
    main()
