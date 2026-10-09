"""Validate a frame-by-frame OpenVINO receipt against frozen scorecard rows.

This verifies byte identity, local model artifacts, sample alignment and
exact numeric predictions. A JSON receipt is not cryptographically signed;
matching it is narrower than authenticating an inference process.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from evaluation.capture_attendance_inference import _attendance_entries, sha256_file


def verify_attendance_receipt(
    manifest_path: Path,
    csv_path: Path,
    receipt_path: Path,
    manifest_sha256: str,
) -> dict:
    manifest_path = manifest_path.expanduser().resolve()
    csv_path = csv_path.expanduser().resolve()
    receipt_path = receipt_path.expanduser().resolve()
    record = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Attendance receipt does not match schema v1")
    if record.get("mode") != "authoritative_openvino" or record.get("detector_backend") != "openvino":
        raise ValueError("Attendance receipt is not from the explicit OpenVINO capture mode")
    if record.get("manifest_sha256") != manifest_sha256:
        raise ValueError("Attendance receipt was generated for a different frozen manifest")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = next(a for a in manifest["assets"] if a["role"] == "attendance")
    annotation = next(a for a in manifest["annotations"] if a["kind"] == "attendance")
    if (record.get("attendance_source_sha256") != source["sha256"].lower()
            or record.get("attendance_csv_sha256") != annotation["sha256"].lower()
            or sha256_file(csv_path) != annotation["sha256"].lower()):
        raise ValueError("Attendance receipt source/labels no longer match the frozen manifest")

    artifacts = record.get("model_artifacts")
    profile = record.get("vision_profile")
    if not isinstance(artifacts, dict) or not isinstance(profile, dict):
        raise ValueError("Attendance receipt does not include model artifacts and vision profile")
    for label, item in (("model XML", (artifacts.get("xml_path"), artifacts.get("xml_sha256"))),
                        ("model weights", (artifacts.get("bin_path"), artifacts.get("bin_sha256"))),
                        ("vision profile", (profile.get("path"), profile.get("sha256")))):
        path_str, expected = item
        if not isinstance(path_str, str) or not isinstance(expected, str):
            raise ValueError(f"Missing {label} provenance in attendance receipt")
        path = Path(path_str).expanduser().resolve()
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{label} no longer matches attendance inference receipt")

    samples = record.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Attendance receipt samples missing")
    expected_samples = dict(_attendance_entries(csv_path))
    seen: set[str] = set()
    observed: dict[str, tuple[int, int]] = {}
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("Malformed attendance inference sample")
        sid = sample.get("sample_id")
        if not isinstance(sid, str) or sid in seen or sid not in expected_samples:
            raise ValueError("Attendance receipt has duplicate or unexpected sample IDs")
        seen.add(sid)
        frame = sample.get("frame_index")
        count = sample.get("raw_person_detection_count")
        decoded = sample.get("decoded_frame_sha256")
        if not isinstance(frame, int) or isinstance(frame, bool) or frame != expected_samples[sid]:
            raise ValueError("Attendance receipt frame index differs from frozen sample schedule")
        if not isinstance(decoded, str) or len(decoded) != 64 or any(ch not in "0123456789abcdef" for ch in decoded):
            raise ValueError("Attendance receipt missing decoded frame hash")
        if sample.get("camera_trusted") is not True:
            # A withheld camera view cannot enter occupancy error statistics
            # with zero detections as an inferred count.
            raise ValueError("Withheld/untrusted camera sample cannot be scored as an attendance count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("Attendance receipt has invalid raw person count")
        observed[sid] = (frame, count)
    if seen != set(expected_samples):
        raise ValueError("Attendance receipt is missing frozen samples")

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, strict=True))
    for row in rows:
        sid = row["sample_id"].strip()
        if not sid or sid not in observed:
            raise ValueError("Attendance CSV contains an unmatched sample")
        try:
            predicted = int(row["pred_count"].strip())
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"Attendance CSV prediction is missing for {sid}") from exc
        if predicted != observed[sid][1]:
            raise ValueError(f"Attendance prediction differs from recorded OpenVINO output for {sid}")

    return {
        "status": "local_openvino_raw_count_receipt_matched",
        "receipt_sha256": sha256_file(receipt_path),
        "sample_count": len(seen),
        "model_xml_sha256": artifacts["xml_sha256"],
        "model_bin_sha256": artifacts["bin_sha256"],
        "vision_profile_sha256": profile["sha256"],
        "scope": "raw_frame_detector_counts_only",
        "authenticity": "unsigned_local_receipt_not_cryptographically_authenticated",
        "claim_boundary": (
            "This check matches CSV counts to the OpenVINO trace recorded locally. "
            "It does not validate human ground truth, camera trust recall, registered "
            "attendance, compliance-case predictions, or the origin of other CSVs."
        ),
    }
