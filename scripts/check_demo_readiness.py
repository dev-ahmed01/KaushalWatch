from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import demo_manifest_path, equipment_cache_path, demo_scenario_path


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


def main() -> None:
    parser = argparse.ArgumentParser(description="KaushalWatch final-demo readiness check")
    parser.add_argument("--video", default=os.getenv("KAUSHALWATCH_DEMO_VIDEO"))
    parser.add_argument("--require-openvino", action="store_true")
    args = parser.parse_args()

    checks: list[tuple[str, bool, str]] = []

    manifest_path = demo_manifest_path()
    cache_path = equipment_cache_path()
    scenario_path = demo_scenario_path()

    ok, note = check_json(manifest_path, dict)
    checks.append(("manifest", ok, note))
    ok, note = check_json(cache_path, list)
    checks.append(("equipment_cache", ok, note))
    ok, note = check_json(scenario_path, dict)
    checks.append(("scenario", ok, note))

    if args.video:
        video = Path(args.video).expanduser()
        checks.append(("demo_video", video.exists() and video.stat().st_size > 0, str(video)))
    else:
        checks.append(("demo_video", False, "KAUSHALWATCH_DEMO_VIDEO/--video not configured"))

    detector = os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "hog").strip().lower()
    if args.require_openvino or detector == "openvino":
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
    manifest_ids = {item.get("id") for item in manifest.get("items", [])}
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

    rows = [
        {"check": name, "ok": ok, "detail": detail}
        for name, ok, detail in checks
    ]
    payload = {
        "ready": all(row["ok"] for row in rows),
        "checks": rows,
        "claim_boundary": (
            "Readiness validates files/configuration only. It does not create or validate final accuracy claims."
        ),
    }
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if payload["ready"] else 2)


if __name__ == "__main__":
    main()
