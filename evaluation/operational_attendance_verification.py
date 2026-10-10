"""Validate an operational attendance receipt against SHA-frozen samples.

Records are unsigned local integration evidence, not cryptographic proof
of detector execution or correctness of independently labelled ground truth.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2

from evaluation.capture_attendance_inference import _attendance_entries, _source, sha256_file
from evaluation.final_scorecard_guard import _strict_bool


def verify_operational_attendance_receipt(
    manifest_path: Path,
    csv_path: Path,
    receipt_path: Path,
    manifest_sha256: str,
) -> dict:
    manifest_path = Path(manifest_path).expanduser().resolve()
    csv_path = Path(csv_path).expanduser().resolve()
    receipt_path = Path(receipt_path).expanduser().resolve()
    record = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Operational receipt must be a schema v1 object")
    if record.get("receipt_type") != "operational_attendance_pipeline":
        raise ValueError("Receipt was not emitted from operational attendance tracing")
    if (record.get("mode") != "authoritative_openvino_pipeline"
            or record.get("detector_backend") != "openvino"):
        raise ValueError("Synthetic/fallback receipts cannot qualify as OpenVINO operational traces")
    if record.get("manifest_sha256") != manifest_sha256:
        raise ValueError("Operational receipt belongs to a different frozen manifest")

    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    clip = next(x for x in frozen["assets"] if x["role"] == "attendance")
    annotation = next(x for x in frozen["annotations"] if x["kind"] == "attendance")
    if (record.get("attendance_source_sha256") != clip["sha256"].lower()
            or record.get("attendance_csv_sha256") != annotation["sha256"].lower()
            or sha256_file(csv_path) != annotation["sha256"].lower()):
        raise ValueError("Operational receipt source or annotation SHA changed")

    artifacts = record.get("model_artifacts")
    profile = record.get("vision_profile")
    if not isinstance(artifacts, dict) or not isinstance(profile, dict):
        raise ValueError("Operational receipt missing authoritative model/profile provenance")
    for label, path_key, hash_key, source in (
        ("model XML", "xml_path", "xml_sha256", artifacts),
        ("model weights", "bin_path", "bin_sha256", artifacts),
        ("vision profile", "path", "sha256", profile),
    ):
        path_string, expected = source.get(path_key), source.get(hash_key)
        if not isinstance(path_string, str) or not isinstance(expected, str):
            raise ValueError(f"Operational receipt missing {label} digest")
        actual_path = Path(path_string).expanduser().resolve()
        if not actual_path.is_file() or sha256_file(actual_path) != expected:
            raise ValueError(f"Operational {label} no longer matches its receipt")

    params = record.get("pipeline_parameters")
    result = record.get("pipeline_result")
    if not isinstance(params, dict) or not isinstance(result, dict):
        raise ValueError("Operational receipt missing configured parameters or result")
    if result.get("detector_authoritative") is not True or result.get("detector_failures") != 0:
        raise ValueError("Operational receipt included unavailable/fallback detector decisions")
    if params.get("occupancy_count_source") not in {"confirmed", "registered"}:
        raise ValueError("Unknown operational attendance count source")
    if not isinstance(params.get("occupancy_smoother_window"), int) or params["occupancy_smoother_window"] < 1:
        raise ValueError("Invalid operational smoother configuration")

    schedule = dict(_attendance_entries(csv_path))
    samples = record.get("samples")
    if not isinstance(samples, list) or len(samples) != len(schedule):
        raise ValueError("Operational receipt missing frozen attendance samples")
    by_id = {}
    for item in samples:
        if not isinstance(item, dict):
            raise ValueError("Malformed operational attendance sample")
        sample_id, frame = item.get("sample_id"), item.get("frame_index")
        if not isinstance(sample_id, str) or sample_id in by_id or sample_id not in schedule:
            raise ValueError("Operational receipt duplicated or changed a sample ID")
        if type(frame) is not int or frame != schedule[sample_id]:
            raise ValueError("Operational receipt frame index does not match frozen schedule")
        if item.get("camera_trusted") is not True or item.get("detector_eligible") is not True:
            raise ValueError("Withheld camera/warmup observation cannot be scored as attendance")
        if not isinstance(item.get("decoded_frame_sha256"), str):
            raise ValueError("Missing operational decoded-frame hash")
        for count_key in ("raw_count", "candidate_count", "confirmed_count",
                          "registered_count", "smoothed_count"):
            number = item.get(count_key)
            if type(number) is not int or number < 0:
                raise ValueError(f"Operational {count_key} must be an eligible nonnegative integer")
        if type(item.get("sample_mismatch")) is not bool:
            raise ValueError("Operational sample mismatch decision must be a boolean")
        by_id[sample_id] = item
    if set(by_id) != set(schedule):
        raise ValueError("Operational receipt does not cover every frozen sample")

    video = _source(manifest_path, clip)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("Frozen operational attendance clip cannot be decoded")
    try:
        for item in samples:
            frame_index = item["frame_index"]
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
                raise ValueError("Operational receipt sample seek failed")
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError("Operational receipt sample cannot be decoded")
            if abs(capture.get(cv2.CAP_PROP_POS_FRAMES) - (frame_index + 1)) > 0.5:
                raise ValueError("Operational receipt frame position changed")
            if hashlib.sha256(frame.tobytes()).hexdigest() != item["decoded_frame_sha256"]:
                raise ValueError("Operational receipt decoded-frame SHA does not match frozen source")
    finally:
        capture.release()

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        csv_rows = list(csv.DictReader(handle, strict=True))
    for row in csv_rows:
        sid = row["sample_id"].strip()
        item = by_id[sid]
        if int(row["pred_count"]) != item["smoothed_count"]:
            raise ValueError(f"Operational attendance pred_count differs from engine for {sid}")
        if _strict_bool(row["pred_issue"], f"{sid}.pred_issue") != item["sample_mismatch"]:
            raise ValueError(f"Operational per-sample pred_issue differs from engine for {sid}")

    return {
        "status": "local_openvino_operational_attendance_receipt_matched",
        "scope": "sampled_temporal_pipeline_counts_and_eligible_mismatch_flags_only",
        "receipt_sha256": sha256_file(receipt_path),
        "sample_count": len(by_id),
        "model_xml_sha256": artifacts["xml_sha256"],
        "model_bin_sha256": artifacts["bin_sha256"],
        "vision_profile_sha256": profile["sha256"],
        "pipeline_parameters": params,
        "pipeline_result": result,
        "authenticity": "unsigned_local_receipt_not_cryptographically_authenticated",
        "claim_boundary": (
            "Provenance is limited to internally recorded temporal attendance "
            "samples and instantaneous mismatch flags. The overall human-review "
            "case is NOT independently validated here; external reported counts "
            "and independent true labels also require verification."
        ),
    }
