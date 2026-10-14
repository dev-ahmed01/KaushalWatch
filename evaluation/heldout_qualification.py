"""Independent multi-recording held-out attendance release gate.

Real qualification re-runs the frozen OpenVINO temporal engine on pinned source
videos and never gives true-count annotations to inference. A test-injected
inference function is permitted for CI but ALWAYS marks the result non-qualifying.
No raw images, participant identities or annotation rows enter the report.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.vision_profile import active_profile_path
from evaluation.evaluate_final_demo import classification_metrics

HEX = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,100}$")
POLICY = {
    "policy_id": "heldout-attendance-provisional-v1",
    "min_scenes": 6, "min_cameras": 2, "min_sites": 2,
    "min_count_annotations": 24,
    "min_positive_cases": 2, "min_negative_cases": 2,
    "max_occupancy_mae": 0.8,
    "min_count_coverage": 0.9,
    "min_scene_count_coverage": 0.75,
    "min_scene_annotations": 4,
    "min_case_coverage": 0.9,
    "min_case_recall": 0.85,
    "max_case_false_positive_rate": 0.15,
    "max_detector_failures": 0,
    "max_timestamp_delta_seconds": 0.12,
    "registration_warmup_seconds": 2.0,
}
REJECT_WORDS = ("synthetic", "example", "placeholder", "unknown", "tbd", "generated test")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _path(manifest: Path, desc: dict, role: str) -> Path:
    if not isinstance(desc, dict) or set(desc) != {"path", "sha256"}:
        raise ValueError(f"{role}: requires exactly path and sha256")
    name, digest = desc["path"], desc["sha256"]
    if not isinstance(name, str) or not name.strip() or not isinstance(digest, str):
        raise ValueError(f"{role}: invalid path or digest")
    if not HEX.fullmatch(digest):
        raise ValueError(f"{role}: expected lowercase SHA-256 digest")
    file = (manifest.parent / name).resolve()
    if not file.is_file() or not file.stat().st_size:
        raise ValueError(f"{role}: missing or empty source")
    if sha256_file(file) != digest:
        raise ValueError(f"{role}: source SHA-256 mismatch")
    return file


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"{name}: invalid stable identifier")
    return value


def _provenance(entry: dict, *, allow_fixture: bool) -> None:
    for field in ("source_origin", "license_basis", "privacy_basis"):
        val = entry.get(field)
        if not isinstance(val, str) or len(val.strip()) < 12:
            raise ValueError(f"{field}: meaningful provenance is mandatory")
        if not allow_fixture and any(word in val.lower() for word in REJECT_WORDS):
            raise ValueError(f"{field}: fixture/placeholder provenance is ineligible")


def _bool(value: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError("true_issue must be exactly true or false")
    return value == "true"


def _truth(path: Path, *, warmup: float, duration: float) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as src:
        reader = csv.DictReader(src, strict=True)
        if reader.fieldnames != ["second", "true_count"]:
            raise ValueError("Ground-truth CSV columns must be exactly second,true_count")
        rows = list(reader)
    if not rows:
        raise ValueError("Held-out scene must have independent timestamped counts")
    times = set()
    values = []
    for row in rows:
        try:
            second = float(row["second"])
            count = int(row["true_count"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid independent timestamped count") from exc
        if (not math.isfinite(second) or second < warmup or second >= duration
                or count < 0 or count > 10000 or second in times):
            raise ValueError("Ground-truth timestamp/count outside valid window or duplicated")
        times.add(second)
        values.append({"second": second, "true_count": count})
    if values != sorted(values, key=lambda x: x["second"]):
        raise ValueError("Ground-truth timestamps must be strictly increasing")
    return values


def _video_metadata(path: Path) -> dict:
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Pinned source video cannot be decoded")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, first = cap.read()
        if not ok or first is None or fps <= 0 or frames < 1 or not math.isfinite(fps):
            raise ValueError("Pinned source video is corrupt or lacks timing metadata")
        return {"fps": fps, "frames": frames, "duration": frames / fps}
    finally:
        cap.release()


def load_protocol(manifest_path: Path, *, allow_fixture: bool = False) -> dict:
    manifest_path = Path(manifest_path).expanduser().resolve()
    if not manifest_path.is_file():
        raise ValueError("Held-out release protocol manifest is missing")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Unsupported held-out release protocol schema")
    if raw.get("status") != "frozen" or ".example." in manifest_path.name:
        raise ValueError("Protocol must be frozen, not a template")
    if raw.get("fixture_only") is not False and not allow_fixture:
        raise ValueError("Only explicit non-fixture protocols may request real qualification")
    if not isinstance(raw.get("fixture_only"), bool):
        raise ValueError("fixture_only must be explicit")
    if raw.get("policy") != POLICY:
        raise ValueError("Qualification thresholds drifted from the reviewed policy")
    _id(raw.get("protocol_id"), "protocol_id")

    profile = _path(manifest_path, raw.get("vision_profile"), "vision_profile")
    if profile != active_profile_path().resolve():
        raise ValueError("Selected runtime vision profile differs from protocol")
    settings = json.loads(profile.read_text(encoding="utf-8"))
    if settings.get("status") != "frozen_sih_candidate":
        raise ValueError("A frozen candidate profile is required")
    if settings.get("person_detection", {}).get("backend") != "openvino":
        raise ValueError("Current qualifying engine must be frozen OpenVINO")
    if settings.get("attendance", {}).get("count_source") not in {"confirmed", "registered"}:
        raise ValueError("Attendance count source is invalid")

    model = raw.get("model_artifacts")
    if not isinstance(model, dict):
        raise ValueError("Frozen OpenVINO artifact digests are mandatory")
    xml, bin_path = _path(manifest_path, model.get("xml"), "model_xml"), _path(
        manifest_path, model.get("bin"), "model_bin")
    if xml.suffix != ".xml" or bin_path != xml.with_suffix(".bin"):
        raise ValueError("Frozen OpenVINO .xml/.bin model pair mismatch")

    calibration = raw.get("calibration")
    heldout = raw.get("heldout")
    if not isinstance(calibration, list) or not calibration or not isinstance(heldout, list):
        raise ValueError("Calibration and held-out partitions are required")
    if len(heldout) < POLICY["min_scenes"]:
        raise ValueError("Too few independent held-out scenes")

    calib_ids, hold_ids = set(), set()
    calib_sources, hold_sources = set(), set()
    calib_recordings, hold_recordings = set(), set()
    cameras, sites = set(), set()
    true_positives = true_negatives = count_samples = 0
    scenes = []
    for label, items in (("calibration", calibration), ("heldout", heldout)):
        for row in items:
            if not isinstance(row, dict):
                raise ValueError(f"{label}: invalid scene record")
            _provenance(row, allow_fixture=allow_fixture)
            scene_id = _id(row.get("scene_id"), "scene_id")
            recording = _id(row.get("recording_id"), "recording_id")
            camera = _id(row.get("camera_id"), "camera_id")
            site = _id(row.get("site_id"), "site_id")
            target_ids = calib_ids if label == "calibration" else hold_ids
            if scene_id in target_ids or scene_id in calib_ids | hold_ids:
                raise ValueError("Scene IDs must be unique across partitions")
            target_ids.add(scene_id)
            video = _path(manifest_path, row.get("video"), "video")
            digest = sha256_file(video)
            target_sources = calib_sources if label == "calibration" else hold_sources
            if digest in target_sources:
                raise ValueError("Duplicate source video inside one partition")
            target_sources.add(digest)
            target_recordings = calib_recordings if label == "calibration" else hold_recordings
            target_recordings.add(recording)
            if label == "calibration":
                continue
            if recording in {item["recording_id"] for item in scenes}:
                raise ValueError("Hold-out requires independent source recordings, not adjacent clips")
            if row.get("blinded_review") is not True or not _id(row.get("reviewer_id"), "reviewer_id"):
                raise ValueError("Hold-out needs independently blinded review attestation")
            if type(row.get("reported_attendance")) is not int or row["reported_attendance"] < 0:
                raise ValueError("External reported-attendance record is mandatory")
            if not isinstance(row.get("reported_record_reference"), str) or len(
                row["reported_record_reference"].strip()) < 8:
                raise ValueError("External reported-attendance record provenance is mandatory")
            if type(row.get("true_issue")) is not bool:
                raise ValueError("Independent case opportunity must be boolean")
            truth_file = _path(manifest_path, row.get("truth"), "truth")
            if not allow_fixture and any(
                marker in truth_file.name.lower() for marker in ("example", "synthetic", "fixture")
            ):
                raise ValueError("Fixture/example annotations cannot establish held-out accuracy")
            metadata = _video_metadata(video)
            truth = _truth(truth_file, warmup=POLICY["registration_warmup_seconds"],
                           duration=metadata["duration"])
            if len(truth) < POLICY["min_scene_annotations"]:
                raise ValueError("Too few independent count annotations in held-out scene")
            true_positives += int(row["true_issue"])
            true_negatives += int(not row["true_issue"])
            count_samples += len(truth)
            cameras.add((site, camera))
            sites.add(site)
            scenes.append({**row, "video_path": video, "truth_path": truth_file,
                           "truth_rows": truth, "duration": metadata["duration"]})

    if calib_sources & hold_sources or calib_recordings & hold_recordings:
        raise ValueError("Calibration/held-out leakage: duplicate source video or recording")
    if (len(cameras) < POLICY["min_cameras"] or len(sites) < POLICY["min_sites"]
            or true_positives < POLICY["min_positive_cases"]
            or true_negatives < POLICY["min_negative_cases"]
            or count_samples < POLICY["min_count_annotations"]):
        raise ValueError("Held-out camera/site/sample or positive/negative support insufficient")
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "profile_sha256": sha256_file(profile),
        "model_xml_sha256": sha256_file(xml),
        "model_bin_sha256": sha256_file(bin_path),
        "xml_path": xml, "scenes": scenes, "camera_count": len(cameras),
        "site_count": len(sites), "annotations": count_samples,
        "positive_cases": true_positives, "negative_cases": true_negatives,
        "fixture_only": raw["fixture_only"],
    }


def infer_scene(video_path: Path, reported_attendance: int, camera_id: str,
                profile: dict) -> dict:
    """Run the actual detector/temporal engine without reading truth CSV."""
    from app.services.person_detector import build_person_detector, _resolve_openvino_xml
    from app.services.video_pipeline import VideoCompliancePipeline
    active_xml = _resolve_openvino_xml().resolve()
    if active_xml != profile["xml_path"]:
        raise ValueError("Runtime OpenVINO model differs from protocol's pinned source")
    detector = build_person_detector()
    if detector.info.backend != "openvino" or not detector.info.authoritative:
        raise ValueError("Authoritative OpenVINO required; fallback detector not valid")
    settings = json.loads(active_profile_path().read_text(encoding="utf-8"))
    expected = settings["person_detection"]
    if (abs(detector.confidence - expected["confidence"]) > 1e-9
            or detector.tiled is not expected["tiled"]
            or abs(detector.tile_overlap - expected["tile_overlap"]) > 1e-9
            or abs(detector.tile_nms_iou - expected["tile_nms_iou"]) > 1e-9):
        raise ValueError("Runtime detector settings drifted from frozen vision profile")
    attendance = settings["attendance"]
    frames = []
    with tempfile.TemporaryDirectory(prefix="kw-heldout-") as folder:
        out = Path(folder)
        engine = VideoCompliancePipeline(out / "evidence", out / "index.json", detector=detector)
        summary = engine.run(
            video_path=video_path, centre_id="EVAL-HELDOUT", batch_id="EVAL-HELDOUT",
            camera_id=camera_id, reported_attendance=reported_attendance,
            sample_every_seconds=attendance["sample_every_seconds"],
            occupancy_count_source=attendance["count_source"],
            occupancy_smoother_window=attendance["smoother_window"],
            observation_sink=frames.append,
        )
    return {
        "backend": summary.detector_backend, "authoritative": summary.detector_authoritative,
        "failures": summary.detector_failures, "decision": summary.decision,
        "samples": [{
            "second": float(p["second"]), "smoothed_count": p["smoothed_count"],
            "eligible": p["detector_eligible"],
            "frame_index": p["frame_index"],
            "camera_trusted": p["camera_trusted"],
        } for p in frames],
    }


def qualify(manifest_path: Path, *, inference: Callable | None = None,
            test_fixture: bool = False) -> dict:
    """Never return a real PASS for injected inference, even if metrics look good."""
    if (inference is None) == test_fixture:
        raise ValueError("Real inference requires no injected function; fixture requires one")
    if inference is None and os.environ.get("KAUSHALWATCH_PERSON_DETECTOR") != "openvino":
        raise ValueError("Real qualification requires explicit OpenVINO detector selection")
    protocol = load_protocol(manifest_path, allow_fixture=test_fixture)
    if inference is None and protocol["fixture_only"]:
        raise ValueError("Synthetic fixture cannot qualify for real-footage release")
    # Fail before starting inference if the runtime profile/model is already
    # inconsistent. Final media/profile hashes are checked again afterwards.
    run = inference or infer_scene
    counts, eligible_counts = [], []
    scene_coverages = []
    confusion = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    decision_eligible = 0
    total_errors = []
    failures = 0
    problems = []
    per_camera: dict[str, list[int]] = defaultdict(list)
    for scene in protocol["scenes"]:
        output = run(scene["video_path"], scene["reported_attendance"],
                     scene["camera_id"], protocol)
        if not isinstance(output, dict) or output.get("backend") != "openvino" or (
            type(output.get("authoritative")) is not bool
        ) or not output["authoritative"]:
            raise ValueError("Non-authoritative detector output cannot establish held-out accuracy")
        if type(output.get("failures")) is not int or output["failures"] < 0:
            raise ValueError("Detector failure count missing or invalid")
        failures += output["failures"]
        samples = output.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ValueError("Missing actual temporal pipeline sampling trace")
        sample_times = [p.get("second") for p in samples]
        if any(type(t) not in (int, float) or not math.isfinite(t) for t in sample_times) or (
            sample_times != sorted(set(sample_times))
        ):
            raise ValueError("Invalid or duplicated engine sample timestamps")
        used_frames = set()
        scene_eligible = 0
        for truth in scene["truth_rows"]:
            nearest = min(samples, key=lambda p: abs(p["second"] - truth["second"]))
            delta = abs(nearest["second"] - truth["second"])
            frame = nearest.get("frame_index")
            if (delta > POLICY["max_timestamp_delta_seconds"] or
                    type(frame) is not int or frame in used_frames):
                raise ValueError("Ground-truth timestamp cannot match a unique temporal sample")
            used_frames.add(frame)
            if (type(nearest.get("eligible")) is not bool or
                    type(nearest.get("camera_trusted")) is not bool):
                raise ValueError("Invalid engine sample eligibility")
            eligible = nearest["eligible"] and nearest["camera_trusted"]
            count = nearest.get("smoothed_count")
            if eligible and (type(count) is not int or count < 0):
                raise ValueError("Invalid eligible smoothed-count evidence")
            if not eligible and count is not None:
                raise ValueError("Untrusted samples must withhold measured counts")
            counts.append(1)
            if eligible:
                scene_eligible += 1
                eligible_counts.append(1)
                error = abs(count - truth["true_count"])
                total_errors.append(error)
                per_camera[scene["site_id"] + "/" + scene["camera_id"]].append(error)
        scene_coverages.append(scene_eligible / len(scene["truth_rows"]))
        decision = output.get("decision")
        if decision not in {"attendance_exception", "compliant",
                            "camera_integrity_exception", "detector_unavailable"}:
            raise ValueError("Unknown attendance decision")
        if output["failures"] or decision in {"camera_integrity_exception", "detector_unavailable"}:
            problems.append("abstained_case_opportunity")
            continue
        decision_eligible += 1
        true_issue = scene["true_issue"]
        predicted = decision == "attendance_exception"
        if true_issue and predicted:
            confusion["tp"] += 1
        elif not true_issue and predicted:
            confusion["fp"] += 1
        elif true_issue:
            confusion["fn"] += 1
        else:
            confusion["tn"] += 1

    if not total_errors:
        raise ValueError("No trusted held-out samples to evaluate")
    # Real runs must still match frozen bytes even if inputs were mutated
    # while the model was running. Re-parse on return, including all hashes.
    after = load_protocol(manifest_path, allow_fixture=test_fixture)
    for key in ("manifest_sha256", "profile_sha256", "model_xml_sha256", "model_bin_sha256"):
        if after[key] != protocol[key]:
            raise ValueError("Evaluation source changed after protocol freeze")
    mae = sum(total_errors) / len(total_errors)
    count_coverage = len(eligible_counts) / len(counts)
    case_coverage = decision_eligible / len(protocol["scenes"])
    cm = classification_metrics(**confusion)
    criteria = {
        "occupancy_mae": mae <= POLICY["max_occupancy_mae"],
        "count_coverage": count_coverage >= POLICY["min_count_coverage"],
        "each_scene_count_coverage": all(
            x >= POLICY["min_scene_count_coverage"] for x in scene_coverages
        ),
        "case_coverage": case_coverage >= POLICY["min_case_coverage"],
        "case_recall": cm["recall"] is not None and cm["recall"] >= POLICY["min_case_recall"],
        "case_false_positive_rate": (
            cm["false_positive_rate"] is not None and
            cm["false_positive_rate"] <= POLICY["max_case_false_positive_rate"]
        ),
        "detector_failures": failures <= POLICY["max_detector_failures"],
    }
    verified = all(criteria.values()) and not test_fixture
    return {
        "status": "heldout_qualified" if verified else (
            "synthetic_fixture_not_qualifying" if test_fixture else "heldout_blocked"),
        "qualified": verified, "criteria": criteria,
        "policy_id": POLICY["policy_id"],
        "provenance": {
            "manifest_sha256": protocol["manifest_sha256"],
            "profile_sha256": protocol["profile_sha256"],
            "model_xml_sha256": protocol["model_xml_sha256"],
            "model_bin_sha256": protocol["model_bin_sha256"],
            "independent_blinded_annotation": "manifest_attested_not_independently_authenticated",
            "prediction_origin": (
                "injected_synthetic_test_fn" if test_fixture else
                "local_openvino_temporal_pipeline_unsigned"
            ),
        },
        "support": {
            "recordings": len(protocol["scenes"]), "cameras": protocol["camera_count"],
            "sites": protocol["site_count"], "annotations": protocol["annotations"],
            "positive_cases": protocol["positive_cases"],
            "negative_cases": protocol["negative_cases"],
            "trusted_count_samples": len(total_errors),
        },
        "metrics": {
            "occupancy_mae": round(mae, 5),
            "count_coverage": round(count_coverage, 5),
            "minimum_scene_count_coverage": round(min(scene_coverages), 5),
            "case_coverage": round(case_coverage, 5),
            "case_decisions": cm,
            "detector_failures": failures,
            "max_count_error": max(total_errors),
            "per_camera_occupancy_mae": {
                camera: round(sum(vals) / len(vals), 5)
                for camera, vals in sorted(per_camera.items())
            },
        },
        "limitations": [
            "Accuracy is limited to pinned scenes, camera views and independently supplied annotations.",
            "Blinded review is attested in input metadata, not independently authenticated.",
            "Only attendance count and attendance compliance cases are qualified here.",
            "The evaluator does not certify practical activity, equipment, operability, camera tamper, identity or nationwide deployment.",
            "Unsigned local inference receipts are not cryptographically attested executions.",
            *problems,
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed held-out attendance qualification")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check-inputs", action="store_true",
                        help="Validate only; never claim accuracy without inference")
    args = parser.parse_args()
    try:
        if args.check_inputs:
            data = load_protocol(args.manifest)
            report = {
                "qualified": False, "status": "inputs_pinned_no_inference",
                "support": {k: data[k] for k in ("annotations", "camera_count",
                                                  "site_count", "positive_cases",
                                                  "negative_cases")},
                "manifest_sha256": data["manifest_sha256"],
            }
        else:
            report = qualify(args.manifest)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        report = {"qualified": False, "status": "heldout_blocked",
                  "reasons": [str(exc)]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    # A data validation check is not an accuracy pass.
    if report.get("status") == "inputs_pinned_no_inference":
        return
    if not report["qualified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
