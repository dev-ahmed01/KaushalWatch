"""SHA-frozen practical-work operational evidence; never identity or skill assessment.

One run yields an anonymized complete sampled timeline and external authorization
context. The verifier decodes frames again and recomputes the overall decision.
Local receipts are UNSIGNED, so consistency is not cryptographic authenticity.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.person_detector import build_person_detector, _resolve_openvino_xml
from app.services.practical_activity_pipeline import PracticalActivityPipeline
from app.services.release_assets import qualify_release_assets
from app.services.vision_profile import active_profile_path


PARAMETERS = {
    "confirmation_seconds": 1.0,
    "registration_seconds": 2.0,
    "grace_seconds": 0.8,
    "sample_every_seconds": 0.2,
    "activity_window_seconds": 1.0,
    "activity_required_ratio": 0.60,
    "motion_threshold": 0.02,
    "motion_pixel_delta": 18,
    "minimum_zone_overlap": 0.15,
    "minimum_trusted_ratio": 0.50,
}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source(root: Path, text: str) -> Path:
    path = Path(text).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _frozen_context(manifest_path: Path) -> tuple[dict, dict, dict, Path, Path, list[dict], tuple[int, int] | None, dict]:
    qualification = qualify_release_assets(manifest_path)
    if not qualification["ready"]:
        raise ValueError("Practical trace requires a qualified frozen release manifest")
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset = next(a for a in frozen["assets"] if a["role"] == "practical")
    config = frozen.get("practical")
    if not isinstance(config, dict) or config.get("asset_id") != asset["id"]:
        raise ValueError("Practical configuration source is not the frozen practical clip")
    zone_spec = config.get("zone_config")
    if not isinstance(zone_spec, dict) or not isinstance(zone_spec.get("path"), str):
        raise ValueError("Practical frozen zone_config path and SHA-256 are required")
    zones_path = _source(manifest_path.parent, zone_spec["path"])
    video_path = _source(manifest_path.parent, asset["path"])
    if _sha(zones_path) != zone_spec.get("sha256", "").lower():
        raise ValueError("Practical work-zone JSON changed since freeze")
    if _sha(video_path) != asset["sha256"].lower():
        raise ValueError("Practical source video changed since freeze")
    parsed = json.loads(zones_path.read_text(encoding="utf-8"))
    profile = config.get("zone_profile")
    if not isinstance(profile, str) or not profile:
        raise ValueError("Practical zone profile missing")
    reference = None
    if isinstance(parsed, dict) and isinstance(parsed.get("_reference"), dict):
        reference = (parsed["_reference"]["width"], parsed["_reference"]["height"])
        if any(type(d) is not int or d <= 0 for d in reference):
            raise ValueError("Practical zone reference dimensions are invalid")
    if isinstance(parsed, dict) and isinstance(parsed.get("zones"), list):
        zones = parsed["zones"]
    elif isinstance(parsed, dict) and isinstance(parsed.get(profile), list):
        zones = parsed[profile]
    elif isinstance(parsed, list) and profile == "default":
        zones = parsed
    else:
        raise ValueError("Practical zone profile does not resolve to a zone list")
    if not zones or not all(isinstance(z, dict) for z in zones):
        raise ValueError("Practical work-zone list is empty or malformed")
    params = dict(PARAMETERS)
    overrides = config.get("pipeline_parameters", {})
    if not isinstance(overrides, dict) or set(overrides) - set(params):
        raise ValueError("Practical pipeline_parameters contains unsupported keys")
    params.update(overrides)
    for name, value in params.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Practical parameter {name} must be finite numeric")
        if name == "motion_pixel_delta":
            if type(value) is not int or not (1 <= value <= 255):
                raise ValueError("Practical motion_pixel_delta must be integer 1..255")
        elif name == "minimum_trusted_ratio":
            if not 0 < value <= 1:
                raise ValueError("Practical minimum_trusted_ratio must be in (0,1]")
        elif name in {"activity_required_ratio", "minimum_zone_overlap"}:
            if not 0 < value <= 1:
                raise ValueError(f"Practical {name} must be in (0,1]")
        elif name in {"sample_every_seconds", "activity_window_seconds"} and value <= 0:
            raise ValueError(f"Practical {name} must be positive")
        elif value < 0:
            raise ValueError(f"Practical {name} cannot be negative")
    return qualification, frozen, asset, video_path, zones_path, zones, reference, params


def capture_practical_trace(manifest_path: Path, *, detector=None, test_fixture: bool = False) -> dict:
    manifest_path = Path(manifest_path).expanduser().resolve()
    qualified, frozen, asset, video, zones_file, zones, reference, params = _frozen_context(manifest_path)
    config = frozen["practical"]
    if test_fixture:
        if detector is None:
            raise ValueError("Synthetic practical test capture requires injected detector")
        mode, model, profile = "synthetic_test_only", None, None
    else:
        if detector is not None:
            raise ValueError("Qualifying practical inference cannot accept an injected detector")
        if os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "").strip().lower() != "openvino":
            raise ValueError("Explicit KAUSHALWATCH_PERSON_DETECTOR=openvino required")
        xml = _resolve_openvino_xml().resolve()
        binary = xml.with_suffix(".bin")
        vision_profile = active_profile_path().resolve()
        for path in (xml, binary, vision_profile):
            if not path.is_file():
                raise ValueError(f"Missing frozen practical model/profile artifact: {path}")
        detector = build_person_detector()
        if detector.info.backend != "openvino" or not detector.info.authoritative:
            raise ValueError("Practical qualifying run requires authoritative OpenVINO")
        mode = "authoritative_openvino_practical_pipeline"
        model = {"xml_path": str(xml), "xml_sha256": _sha(xml),
                 "bin_path": str(binary), "bin_sha256": _sha(binary)}
        profile = {"path": str(vision_profile), "sha256": _sha(vision_profile)}
    observations: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="kaushalwatch-practical-review-") as folder:
        root = Path(folder)
        engine = PracticalActivityPipeline(root / "evidence", root / "evidence.json", detector=detector)
        result = engine.run(
            video_path=video,
            zones=zones,
            authorization=config["authorization"],
            centre_id=asset["centre_id"],
            batch_id=asset["batch_id"],
            camera_id="FROZEN-PRACTICAL-CAMERA",
            zone_reference_size=reference,
            observation_sink=observations.append,
            **params,
        )
    if not observations:
        raise ValueError("Practical trace produced no sampled observations")
    return {
        "schema_version": 1,
        "receipt_type": "full_practical_activity_pipeline",
        "mode": mode,
        "manifest_sha256": qualified["manifest_sha256"],
        "source_video_sha256": asset["sha256"].lower(),
        "source_asset_id": asset["id"],
        "centre_id": asset["centre_id"],
        "batch_id": asset["batch_id"],
        "zone_config_sha256": _sha(zones_file),
        "zone_profile": config["zone_profile"],
        "authorization": config["authorization"],
        "authorization_basis": "external_input_not_inferred_from_video",
        "pipeline_parameters": params,
        "model_artifacts": model,
        "vision_profile": profile,
        "timeline": observations,
        "result": {
            "decision": result.decision,
            "case_type": result.case.case_type if result.case else None,
            "frames_processed": result.frames_processed,
            "trusted_frame_ratio": result.trusted_frame_ratio,
            "peak_stable_workers": result.peak_stable_workers,
            "practical_activity_fraction": result.practical_activity_fraction,
            "first_practical_activity_time_sec": result.first_practical_activity_time_sec,
            "active_work_cells": result.active_work_cells,
            "detector_authoritative": result.detector_authoritative,
            "detector_failures": result.detector_failures,
            "zone_scaled": result.zone_scaled,
        },
        "claim_boundary": (
            "Same operational tracking, registration, zone-motion persistence and "
            "externally supplied authorization; no identity, worker competency or "
            "legal authorization inferred from video. Unsigned local receipt and "
            "not independently measured real-video accuracy."
        ),
    }


def verify_practical_trace(manifest_path: Path, receipt_path: Path, manifest_sha256: str) -> dict:
    manifest_path = Path(manifest_path).expanduser().resolve()
    receipt_path = Path(receipt_path).expanduser().resolve()
    stored = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or stored.get("receipt_type") != "full_practical_activity_pipeline" or stored.get("schema_version") != 1:
        raise ValueError("Practical trace receipt schema is invalid")
    if stored.get("mode") != "authoritative_openvino_practical_pipeline":
        raise ValueError("Practical synthetic/fallback receipt cannot qualify")
    if _sha(manifest_path) != manifest_sha256 or stored.get("manifest_sha256") != manifest_sha256:
        raise ValueError("Practical receipt is for a different frozen manifest")
    _, frozen, asset, video, zone_file, zones, _, params = _frozen_context(manifest_path)
    if stored.get("source_video_sha256") != asset["sha256"].lower():
        raise ValueError("Practical source SHA differs")
    if (stored.get("source_asset_id") != asset["id"]
            or stored.get("centre_id") != asset["centre_id"]
            or stored.get("batch_id") != asset["batch_id"]):
        raise ValueError("Practical source identity/centre/batch differs from frozen file")
    if (stored.get("zone_config_sha256") != _sha(zone_file)
            or stored.get("zone_profile") != frozen["practical"]["zone_profile"]):
        raise ValueError("Practical zone geometry/profile differs from frozen file")
    if stored.get("pipeline_parameters") != params:
        raise ValueError("Practical thresholds or sampling settings differ from frozen parameters")
    if stored.get("authorization") != frozen["practical"]["authorization"]:
        raise ValueError("Practical receipt authorization differs from frozen external state")
    model, profile = stored.get("model_artifacts"), stored.get("vision_profile")
    if not isinstance(model, dict) or not isinstance(profile, dict):
        raise ValueError("Practical OpenVINO model and profile evidence missing")
    for name, document, path_key, digest_key in (
        ("model XML", model, "xml_path", "xml_sha256"),
        ("model BIN", model, "bin_path", "bin_sha256"),
        ("vision profile", profile, "path", "sha256"),
    ):
        path_value, digest = document.get(path_key), document.get(digest_key)
        if not isinstance(path_value, str) or not isinstance(digest, str):
            raise ValueError(f"Practical {name} SHA/path missing")
        path = Path(path_value).expanduser().resolve()
        if not path.is_file() or _sha(path) != digest:
            raise ValueError(f"Practical {name} changed or disappeared")
    if not isinstance(stored.get("timeline"), list) or not stored["timeline"]:
        raise ValueError("Practical receipt full timeline missing")
    sample_rows = stored["timeline"]
    if any(not isinstance(row, dict) for row in sample_rows):
        raise ValueError("Malformed practical sample in receipt")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Could not decode frozen practical clip")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if fps <= 0:
        cap.release()
        raise ValueError("Frozen practical video has invalid FPS")
    try:
        previous = -1
        seen: set[int] = set()
        for entry in sample_rows:
            frame = entry.get("frame_index")
            sec = entry.get("second")
            if type(frame) is not int or frame <= previous or frame in seen:
                raise ValueError("Practical frames not unique and strictly increasing")
            previous = frame
            seen.add(frame)
            if not isinstance(sec, (int, float)) or abs(sec - frame / fps) > 0.0001:
                raise ValueError("Practical sample frame time inconsistent with source")
            if not cap.set(cv2.CAP_PROP_POS_FRAMES, frame):
                raise ValueError("Practical video frame seek failed")
            ok, decoded = cap.read()
            if not ok or decoded is None or hashlib.sha256(decoded.tobytes()).hexdigest() != entry.get("decoded_frame_sha256"):
                raise ValueError("Practical decoded frame SHA differs from frozen source")
    finally:
        cap.release()
    result = stored.get("result")
    if not isinstance(result, dict) or result.get("frames_processed") != len(sample_rows):
        raise ValueError("Practical timeline not complete for reported result")
    trusted = sum(row.get("camera_trusted") is True for row in sample_rows)
    if any(type(row.get("camera_trusted")) is not bool for row in sample_rows):
        raise ValueError("Practical camera trust labels invalid")
    trusted_ratio = trusted / len(sample_rows)
    if abs(trusted_ratio - result.get("trusted_frame_ratio", -1)) > 0.00011:
        raise ValueError("Practical trusted ratio disagrees with timeline")
    if result.get("detector_authoritative") is not True or result.get("detector_failures") != 0:
        raise ValueError("Practical detector unavailable; cannot score compliance")
    configured_zone_ids = {
        str(zone.get("zone_id") or f"work_zone_{i+1}") for i, zone in enumerate(zones)
    }
    practical_frames = 0
    active_zones: set[str] = set()
    peak = 0
    first_activity = None
    for row in sample_rows:
        available = row.get("detector_available")
        trust = row["camera_trusted"]
        if type(available) is not bool:
            raise ValueError("Practical per-frame detector availability missing")
        if not available:
            raise ValueError("Practical trace contains a failed detector")
        active = row.get("practical_active")
        count = row.get("registered_workers")
        zone_ids = row.get("active_work_zones")
        if not isinstance(zone_ids, list) or len(zone_ids) != len(set(zone_ids)) or not set(zone_ids).issubset(configured_zone_ids):
            raise ValueError("Practical active zones not part of frozen zone profile")
        if trust:
            if type(active) is not bool or type(count) is not int or count < 0:
                raise ValueError("Practical trusted sample requires valid activity and registered count")
            if type(row.get("raw_person_count")) is not int or row["raw_person_count"] < 0:
                raise ValueError("Practical trusted sample missing detector count")
            if active != bool(zone_ids) or (active and not count):
                raise ValueError("Practical zone activity contradicts registered workers")
            peak = max(peak, count)
            if active:
                practical_frames += 1
                active_zones.update(zone_ids)
                if first_activity is None:
                    first_activity = row["second"]
        else:
            if active is not None or count is not None or row.get("raw_person_count") is not None or zone_ids:
                raise ValueError("Practical untrusted frame cannot become a positive or negative count")
    fraction = practical_frames / len(sample_rows)
    if abs(fraction - result.get("practical_activity_fraction", -1)) > 0.00011:
        raise ValueError("Practical activity persistence disagrees with full timeline")
    if result.get("active_work_cells") != len(active_zones) or result.get("peak_stable_workers") != peak:
        raise ValueError("Practical registered workers/active cells disagree with timeline")
    expected_first = round(first_activity, 3) if first_activity is not None else None
    if result.get("first_practical_activity_time_sec") != expected_first:
        raise ValueError("Practical first activity time differs from timeline")
    if trusted_ratio < params["minimum_trusted_ratio"]:
        raise ValueError("Insufficient camera trust; do not score an absent-activity negative")
    authorization = stored["authorization"]
    expected_decision = "no_persistent_practical_activity"
    expected_case = None
    if practical_frames:
        if authorization == "valid":
            expected_decision = "authorized_practical_activity"
        elif authorization == "absent":
            expected_decision, expected_case = "unauthorized_practical_activity", "practical_activity_authorization"
        else:
            expected_decision, expected_case = "authorization_review_required", "practical_activity_authorization_review"
    if result.get("decision") != expected_decision or result.get("case_type") != expected_case:
        raise ValueError("Final practical authorization decision inconsistent with timeline")
    return {
        "status": "local_practical_decision_timeline_matched",
        "mode": stored["mode"],
        "decision": expected_decision,
        "case_type": expected_case,
        "authorization": authorization,
        "source_video_sha256": asset["sha256"].lower(),
        "zone_config_sha256": stored["zone_config_sha256"],
        "model_xml_sha256": model["xml_sha256"],
        "model_bin_sha256": model["bin_sha256"],
        "frames_processed": len(sample_rows),
        "trusted_ratio": round(trusted_ratio, 4),
        "practical_activity_fraction": round(fraction, 4),
        "receipt_sha256": _sha(receipt_path),
        "authenticity": "unsigned_local_receipt_not_cryptographically_authenticated",
        "claim_boundary": stored["claim_boundary"],
    }


def verify_practical_case(
    manifest_path: Path, cases_csv_path: Path, receipt_path: Path,
    manifest_sha256: str, case_sample_id: str,
) -> dict:
    verified = verify_practical_trace(manifest_path, receipt_path, manifest_sha256)
    if verified["authorization"] == "unknown":
        raise ValueError("Unknown authorization requires officer review, not binary authorization accuracy")
    manifest_path = Path(manifest_path).expanduser().resolve()
    cases_csv_path = Path(cases_csv_path).expanduser().resolve()
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = next(a for a in frozen["assets"] if a["role"] == "practical")
    annotation = next(a for a in frozen["annotations"] if a["kind"] == "cases")
    if cases_csv_path != _source(manifest_path.parent, annotation["path"]) or _sha(cases_csv_path) != annotation["sha256"].lower():
        raise ValueError("Practical cases CSV differs from frozen source")
    with cases_csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, strict=True))
    matches = [row for row in rows if row.get("sample_id", "").strip() == case_sample_id
               and row.get("case_type", "").strip() == "practical_activity_authorization"]
    if len(matches) != 1:
        raise ValueError("Exactly one practical authorization case opportunity must be specified")
    row = matches[0]
    if row.get("source_asset_id", "").strip() != source["id"]:
        raise ValueError("Practical case source asset differs from frozen clip")
    same_video = [r for r in rows if r.get("case_type", "").strip() == "practical_activity_authorization"
                  and r.get("source_asset_id", "").strip() == source["id"]]
    if len(same_video) != 1:
        raise ValueError("One practical video may not count as multiple independent case opportunities")
    if (row.get("centre_id", "").strip() != source["centre_id"]
            or row.get("batch_id", "").strip() != source["batch_id"]):
        raise ValueError("Practical case centre/batch mismatch")
    if row.get("authorization", "").strip() != verified["authorization"]:
        raise ValueError("Practical case external authorization changed")
    predicted = verified["decision"] == "unauthorized_practical_activity"
    pred = str(row.get("pred_issue") or "").strip().lower()
    truth = str(row.get("true_issue") or "").strip().lower()
    if pred not in {"true", "false"} or truth not in {"true", "false"}:
        raise ValueError("Practical case truth and prediction must be true or false")
    if (pred == "true") != predicted:
        raise ValueError("Practical case prediction differs from actual final decision")
    return {
        "status": "one_practical_case_opportunity_matched",
        "case_sample_id": case_sample_id,
        "predicted_issue": predicted,
        "independent_label_in_csv": truth == "true",
        "decision_trace_sha256": verified["receipt_sha256"],
        "source_video_sha256": verified["source_video_sha256"],
        "authorization": verified["authorization"],
        "independent_truth_verified": False,
        "claim_boundary": (
            "Matches one frozen externally authorized practical-work decision. "
            "Does not prove the independently supplied truth or generalize across centres."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record frozen OpenVINO practical-work decision without identity")
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--out", default="evaluation/output/final-demo/practical-trace.json")
    args = parser.parse_args()
    output = Path(args.out).expanduser().resolve()
    if output == Path(args.asset_manifest).expanduser().resolve():
        parser.error("Practical receipt cannot overwrite source manifest")
    trace = capture_practical_trace(Path(args.asset_manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "mode": trace["mode"],
                      "decision": trace["result"]["decision"],
                      "frames_processed": trace["result"]["frames_processed"],
                      "claim_boundary": trace["claim_boundary"]}, indent=2))


if __name__ == "__main__":
    main()
