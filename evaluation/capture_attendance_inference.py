"""Privacy-preserving per-frame attendance detector trace, not a case verdict.

The CLI requires a frozen asset manifest and authoritative OpenVINO.
Unit tests may inject a deterministic test detector, in which case the receipt
is explicitly marked test_fixture and can never qualify for final scoring.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.camera_trust import assess_camera
from app.services.person_detector import build_person_detector, _resolve_openvino_xml
from app.services.release_assets import qualify_release_assets
from app.services.vision_profile import active_profile_path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source(manifest_path: Path, entry: dict) -> Path:
    value = Path(entry["path"]).expanduser()
    return value.resolve() if value.is_absolute() else (manifest_path.parent / value).resolve()


def _attendance_entries(csv_path: Path) -> list[tuple[str, int]]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        if not reader.fieldnames or not {"sample_id", "frame_index"}.issubset(reader.fieldnames):
            raise ValueError("Attendance annotation CSV must contain sample_id and frame_index")
        rows = list(reader)
    if not rows:
        raise ValueError("Attendance annotation CSV has no samples")
    output: list[tuple[str, int]] = []
    seen: set[str] = set()
    for row in rows:
        sample_id = str(row.get("sample_id") or "").strip()
        raw_frame = str(row.get("frame_index") or "").strip()
        try:
            frame_index = int(raw_frame)
        except ValueError as exc:
            raise ValueError("frame_index must be a zero-based integer") from exc
        if not sample_id or sample_id in seen or frame_index < 0:
            raise ValueError("Attendance sample IDs must be unique, with nonnegative frame_index")
        seen.add(sample_id)
        output.append((sample_id, frame_index))
    if len({frame for _, frame in output}) != len(output):
        raise ValueError("Attendance frame_index must not be reused across sample IDs")
    return output


def capture_attendance_trace(
    manifest_path: Path,
    csv_path: Path,
    *,
    detector=None,
    test_fixture: bool = False,
) -> dict:
    manifest_path = manifest_path.expanduser().resolve()
    csv_path = csv_path.expanduser().resolve()
    qualification = qualify_release_assets(manifest_path)
    if not qualification["ready"]:
        raise ValueError("Final asset manifest is unqualified; no inference receipt created")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    annotation = next(x for x in manifest["annotations"] if x["kind"] == "attendance")
    if csv_path != _source(manifest_path, annotation):
        raise ValueError("The sample schedule is not the frozen attendance annotation CSV")
    if sha256_file(csv_path) != annotation["sha256"].lower():
        raise ValueError("Attendance sample schedule differs from the frozen hash")
    schedule = _attendance_entries(csv_path)
    asset = next(x for x in manifest["assets"] if x["role"] == "attendance")
    video = _source(manifest_path, asset)
    if sha256_file(video) != asset["sha256"].lower():
        raise ValueError("Attendance video differs from the frozen hash")

    if test_fixture:
        if detector is None:
            raise ValueError("Test fixture mode needs an injected detector")
        backend = "test_fixture"
        model_hashes = None
        profile_digest = None
        mode = "synthetic_test_only"
    else:
        if detector is not None:
            raise ValueError("Real capture must instantiate the detector, not accept an injected model")
        if os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "").strip().lower() != "openvino":
            raise ValueError("Explicit KAUSHALWATCH_PERSON_DETECTOR=openvino is required")
        xml = _resolve_openvino_xml().resolve()
        weights = xml.with_suffix(".bin")
        profile = active_profile_path().resolve()
        for path in (xml, weights, profile):
            if not path.is_file():
                raise ValueError(f"Required inference model/profile is absent: {path}")
        detector = build_person_detector()
        if detector.info.backend != "openvino" or not detector.info.authoritative:
            raise ValueError("Only authoritative OpenVINO is accepted for inference receipts")
        backend = detector.info.backend
        model_hashes = {
            "xml_path": str(xml), "xml_sha256": sha256_file(xml),
            "bin_path": str(weights), "bin_sha256": sha256_file(weights),
        }
        profile_digest = {"path": str(profile), "sha256": sha256_file(profile)}
        mode = "authoritative_openvino"

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Could not decode frozen attendance clip")
    output: list[dict] = []
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        for sample_id, frame_index in schedule:
            if frame_index >= total_frames:
                raise ValueError(f"Sample {sample_id} requests frame beyond end of video")
            if not cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
                raise ValueError(f"Could not seek to frame for {sample_id}")
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError(f"Could not decode sample frame for {sample_id}")
            position = cap.get(cv2.CAP_PROP_POS_FRAMES)
            if abs(position - (frame_index + 1)) > 0.5:
                raise ValueError(f"Decoder returned an unexpected frame for {sample_id}")
            # Source and model are real; the camera may still be unsuitable.
            trust = assess_camera(frame, previous_frame=None, reference_frame=frame)
            trusted = bool(trust.trusted)
            raw_count = len(detector.detect(frame)) if trusted else None
            output.append({
                "sample_id": sample_id,
                "frame_index": frame_index,
                "decoded_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                "camera_trusted": trusted,
                "camera_reasons": list(trust.reasons),
                "raw_person_detection_count": raw_count,
            })
    finally:
        cap.release()

    return {
        "schema_version": 1,
        "receipt_type": "raw_person_frame_detections",
        "mode": mode,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": qualification["manifest_sha256"],
        "attendance_source_sha256": asset["sha256"].lower(),
        "attendance_csv_sha256": annotation["sha256"].lower(),
        "detector_backend": backend,
        "detector_description": detector.info.message,
        "model_artifacts": model_hashes,
        "vision_profile": profile_digest,
        "samples": output,
        "trusted_samples": sum(bool(s["camera_trusted"]) for s in output),
        "withheld_samples": sum(not s["camera_trusted"] for s in output),
        "claim_boundary": (
            "Raw per-frame person detections with conservative camera gating. "
            "NOT tracked/registered attendance, attendance-case accuracy, "
            "identity tracking, or proof of real-world ground-truth accuracy. "
            "Receipt content is unsigned and requires operator-controlled provenance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture exact OpenVINO attendance detections for frozen samples")
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--attendance", required=True,
                        help="Exact frozen annotation CSV including sample_id and frame_index")
    parser.add_argument("--out", default="evaluation/output/final-demo/attendance-inference.json")
    args = parser.parse_args()
    record = capture_attendance_trace(Path(args.asset_manifest), Path(args.attendance))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() in {Path(args.attendance).resolve(), Path(args.asset_manifest).resolve()}:
        raise SystemExit("Output must not overwrite source annotations or asset manifest")
    output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output), "mode": record["mode"],
        "samples": len(record["samples"]), "trusted_samples": record["trusted_samples"],
        "withheld_samples": record["withheld_samples"],
        "claim_boundary": record["claim_boundary"],
    }, indent=2))


if __name__ == "__main__":
    main()
