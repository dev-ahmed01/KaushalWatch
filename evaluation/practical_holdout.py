"""Frozen held-out evaluation of the ACTUAL practical-activity pipeline.

Only an independently blinded recording with intact hashes, review-attested
activity labels and externally supplied authorization can qualify. Injected
synthetic inference is NEVER eligible for a real accuracy claim. No face,
individual worker identity or raw image is written to a scorecard.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "backend"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from evaluation.heldout_qualification import sha256_file
from app.services.vision_profile import active_profile_path

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,100}$")
HEX = re.compile(r"^[a-f0-9]{64}$")
POLICY = {
    "policy_id": "practical-activity-heldout-provisional-v1",
    "min_heldout_scenes": 6,
    "min_sites": 2,
    "min_cameras": 2,
    "min_positive_scenes": 2,
    "min_negative_scenes": 2,
    "min_absent_authorization_scenes": 2,
    "min_unknown_authorization_scenes": 1,
    "min_decision_coverage": 0.9,
    "min_activity_recall": 0.85,
    "max_activity_false_positive_rate": 0.15,
    "max_unauthorized_false_positive_rate": 0.15,
    "max_detector_failures": 0,
}
DECISIONS = {
    "no_persistent_practical_activity", "authorized_practical_activity",
    "unauthorized_practical_activity", "authorization_review_required",
    "camera_evidence_insufficient", "detector_unavailable",
}


def ref(manifest: Path, item: object, label: str) -> Path:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError(f"{label} requires an immutable path and SHA-256")
    filename, digest = item["path"], item["sha256"]
    if not isinstance(filename, str) or not filename.strip() or not isinstance(digest, str) or not HEX.fullmatch(digest):
        raise ValueError(f"{label} has an invalid file path or SHA-256")
    file = (manifest.parent / filename).resolve()
    if not file.is_file() or file.stat().st_size == 0 or sha256_file(file) != digest:
        raise ValueError(f"{label} source missing, empty or SHA-256 mismatch")
    return file


def name(value: object, label: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"{label} requires a stable alphanumeric ID")
    return value


def load(manifest: Path, *, test_fixture: bool = False) -> dict:
    manifest = manifest.expanduser().resolve()
    if not manifest.is_file():
        raise ValueError("Frozen practical held-out manifest is missing")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("status") != "frozen":
        raise ValueError("A frozen practical held-out manifest is required")
    if data.get("policy") != POLICY or type(data.get("fixture_only")) is not bool:
        raise ValueError("Reviewed policy or explicit fixture declaration missing")
    if data["fixture_only"] and not test_fixture:
        raise ValueError("Synthetic practical fixtures cannot qualify as real evidence")
    name(data.get("protocol_id"), "protocol_id")
    profile = ref(manifest, data.get("vision_profile"), "vision_profile")
    if profile != active_profile_path().resolve():
        raise ValueError("Selected runtime profile is not the frozen profile")
    settings = json.loads(profile.read_text(encoding="utf-8"))
    if settings.get("status") != "frozen_sih_candidate" or settings.get("person_detection", {}).get("backend") != "openvino":
        raise ValueError("Qualifying practical profile requires frozen OpenVINO")
    xml = ref(manifest, data.get("model_artifacts", {}).get("xml"), "model_xml")
    binary = ref(manifest, data.get("model_artifacts", {}).get("bin"), "model_bin")
    if xml.suffix != ".xml" or binary != xml.with_suffix(".bin"):
        raise ValueError("OpenVINO XML/BIN pair is inconsistent")
    if not isinstance(data.get("calibration"), list) or not data["calibration"]:
        raise ValueError("Calibration partition is required")
    if not isinstance(data.get("heldout"), list) or len(data["heldout"]) < POLICY["min_heldout_scenes"]:
        raise ValueError("Too few held-out practical scenes")

    used_recordings: set[str] = set()
    used_digests: set[str] = set()
    used_ids: set[str] = set()
    sites, cameras = set(), set()
    scenes = []
    for split in ("calibration", "heldout"):
        for row in data[split]:
            if not isinstance(row, dict):
                raise ValueError("Invalid practical scene record")
            rid, sid = name(row.get("recording_id"), "recording_id"), name(row.get("scene_id"), "scene_id")
            site, camera = name(row.get("site_id"), "site_id"), name(row.get("camera_id"), "camera_id")
            if rid in used_recordings or sid in used_ids:
                raise ValueError("Calibration/held-out recording leakage or duplicated IDs")
            used_recordings.add(rid)
            used_ids.add(sid)
            video = ref(manifest, row.get("video"), "scene video")
            digest = sha256_file(video)
            if digest in used_digests:
                raise ValueError("Calibration/held-out footage duplicate or leakage")
            used_digests.add(digest)
            for key in ("source_origin", "license_basis", "privacy_basis"):
                val = row.get(key)
                if not isinstance(val, str) or len(val.strip()) < 12:
                    raise ValueError(f"{key}: full lawful data provenance is mandatory")
                if not test_fixture and any(word in val.lower() for word in ("synthetic", "placeholder", "example", "tbd")):
                    raise ValueError(f"{key}: test provenance is not qualifying")
            if split == "calibration":
                continue
            if row.get("blinded_review") is not True or not name(row.get("reviewer_id"), "reviewer_id"):
                raise ValueError("Independently blinded annotator attestation is required")
            if row.get("previously_inspected") is not False:
                raise ValueError("Held-out practical video was not attested untouched")
            if type(row.get("true_activity")) is not bool:
                raise ValueError("Independent visual activity truth label must be boolean")
            if row.get("authorization") not in {"valid", "absent", "unknown"}:
                raise ValueError("External authorization must be valid/absent/unknown")
            if not isinstance(row.get("external_record_reference"), str) or len(row["external_record_reference"].strip()) < 12:
                raise ValueError("Independent external work schedule/reference is required")
            zones_file = ref(manifest, row.get("work_zones"), "work zone geometry")
            zones = json.loads(zones_file.read_text(encoding="utf-8"))
            if not isinstance(zones, dict) or set(zones) != {"zones", "reference_size"}:
                raise ValueError("Reviewed per-camera zone file needs zones and reference_size")
            size = zones["reference_size"]
            if not isinstance(size, list) or len(size) != 2 or any(type(n) is not int or n < 1 for n in size):
                raise ValueError("Work-zone reference dimensions are invalid")
            if not isinstance(zones["zones"], list) or not zones["zones"]:
                raise ValueError("No reviewed camera work zones")
            from app.services.practical_activity_pipeline import validate_work_zones
            validate_work_zones(zones["zones"], size[0], size[1])
            sites.add(site)
            cameras.add((site, camera))
            scenes.append({
                "video": video, "zones": zones["zones"], "size": tuple(size),
                "camera": camera, "site": site, "truth": row["true_activity"],
                "authorization": row["authorization"], "scene_id": sid,
            })
    positive = sum(x["truth"] for x in scenes)
    negative = len(scenes) - positive
    if (len(cameras) < POLICY["min_cameras"] or len(sites) < POLICY["min_sites"]
        or positive < POLICY["min_positive_scenes"] or negative < POLICY["min_negative_scenes"]
        or sum(x["authorization"] == "absent" for x in scenes) < POLICY["min_absent_authorization_scenes"]
        or sum(x["authorization"] == "unknown" for x in scenes) < POLICY["min_unknown_authorization_scenes"]):
        raise ValueError("Insufficient held-out independent sites, cameras, outcomes or authorization coverage")
    return {
        "scenes": scenes, "positive": positive, "negative": negative,
        "cameras": len(cameras), "sites": len(sites),
        "xml": xml, "settings": settings,
        "manifest_sha256": sha256_file(manifest),
        "profile_sha256": sha256_file(profile),
        "model_xml_sha256": sha256_file(xml),
        "model_bin_sha256": sha256_file(binary),
    }


def infer(scene: dict, protocol: dict) -> dict:
    """No truth label is supplied to the engine — only observed video and external authorization."""
    from app.services.person_detector import build_person_detector, _resolve_openvino_xml
    from app.services.practical_activity_pipeline import PracticalActivityPipeline
    if os.getenv("KAUSHALWATCH_PERSON_DETECTOR") != "openvino" or _resolve_openvino_xml().resolve() != protocol["xml"]:
        raise ValueError("Runtime detector must match frozen OpenVINO model")
    detector = build_person_detector()
    if detector.info.backend != "openvino" or not detector.info.authoritative:
        raise ValueError("Fallback detector cannot establish practical-work qualification")
    profile = protocol["settings"]
    detector_config = profile["person_detection"]
    if (abs(detector.confidence - detector_config["confidence"]) > 1e-9
        or detector.tiled is not detector_config["tiled"]
        or abs(detector.tile_overlap - detector_config["tile_overlap"]) > 1e-9
        or abs(detector.tile_nms_iou - detector_config["tile_nms_iou"]) > 1e-9):
        raise ValueError("Runtime practical OpenVINO settings drifted")
    p, a = profile["practical_activity"], profile["attendance"]
    kwargs = {
        "confirmation_seconds": a["track_confirmation_seconds"],
        "registration_seconds": a["registration_warmup_seconds"],
        "grace_seconds": a["track_grace_seconds"],
        "sample_every_seconds": p["sample_every_seconds"],
        "activity_window_seconds": p["activity_window_seconds"],
        "activity_required_ratio": p["activity_required_ratio"],
        "motion_threshold": p["motion_threshold"],
        "motion_pixel_delta": p["motion_pixel_delta"],
        "minimum_zone_overlap": p["minimum_zone_overlap"],
        "minimum_trusted_ratio": p["minimum_trusted_ratio"],
    }
    with tempfile.TemporaryDirectory(prefix="kw-practical-heldout-") as tmp:
        engine = PracticalActivityPipeline(Path(tmp)/"evidence", Path(tmp)/"index.json", detector=detector)
        summary = engine.run(
            video_path=scene["video"], zones=scene["zones"],
            zone_reference_size=scene["size"], authorization=scene["authorization"],
            centre_id="EVAL-HELDOUT", batch_id="EVAL-HELDOUT",
            camera_id=scene["camera"], **kwargs,
        )
    return {
        "backend": summary.detector_backend,
        "authoritative": summary.detector_authoritative,
        "failures": summary.detector_failures,
        "decision": summary.decision,
    }


def qualify(manifest: Path, *, inference: Callable | None = None, test_fixture: bool = False) -> dict:
    if (inference is None) == test_fixture:
        raise ValueError("Injected inference is allowed only for nonqualifying synthetic fixtures")
    frozen = load(manifest, test_fixture=test_fixture)
    classify = inference or infer
    confusion = Counter()
    activity_evaluable = 0
    definitive_opportunities = 0
    invalid_definitive = 0
    abstentions = 0
    failures = 0
    for scene in frozen["scenes"]:
        # Never provide label "truth" to detector/inference.
        inference_input = {k: v for k, v in scene.items() if k != "truth"}
        out = classify(inference_input, frozen)
        if (not isinstance(out, dict) or out.get("backend") != "openvino"
            or out.get("authoritative") is not True or type(out.get("failures")) is not int
            or out["failures"] < 0 or out.get("decision") not in DECISIONS):
            raise ValueError("Non-authoritative, malformed or unknown practical inference")
        failures += out["failures"]
        decision = out["decision"]
        if decision in {"camera_evidence_insufficient", "detector_unavailable"} or out["failures"]:
            abstentions += 1
            continue
        activity_evaluable += 1
        pred_active = decision != "no_persistent_practical_activity"
        confusion["tp" if scene["truth"] and pred_active else
                  "fp" if pred_active else
                  "fn" if scene["truth"] else "tn"] += 1
        if scene["authorization"] == "valid" and decision not in {
            "authorized_practical_activity", "no_persistent_practical_activity"
        }:
            invalid_definitive += 1
        if scene["authorization"] == "unknown" and decision not in {
            "authorization_review_required", "no_persistent_practical_activity"
        }:
            invalid_definitive += 1
        if scene["authorization"] == "absent":
            definitive_opportunities += 1
            expected_violation = scene["truth"]
            predicted_violation = decision == "unauthorized_practical_activity"
            if predicted_violation and not expected_violation:
                confusion["unauthorized_fp"] += 1
            if decision not in {"unauthorized_practical_activity", "no_persistent_practical_activity"}:
                invalid_definitive += 1
    after = load(manifest, test_fixture=test_fixture)
    for key in ("manifest_sha256", "profile_sha256", "model_xml_sha256", "model_bin_sha256"):
        if frozen[key] != after[key]:
            raise ValueError("Frozen practical source changed during inference")
    tp, fp, fn, tn = (confusion[k] for k in ("tp", "fp", "fn", "tn"))
    recall = tp/(tp+fn) if tp+fn else None
    fpr = fp/(fp+tn) if fp+tn else None
    coverage = activity_evaluable/len(frozen["scenes"])
    absent_normals = sum(not x["truth"] and x["authorization"] == "absent" for x in frozen["scenes"])
    unauthorized_fpr = confusion["unauthorized_fp"]/absent_normals if absent_normals else None
    criteria = {
        "decision_coverage": coverage >= POLICY["min_decision_coverage"],
        "activity_recall": recall is not None and recall >= POLICY["min_activity_recall"],
        "activity_false_positive_rate": fpr is not None and fpr <= POLICY["max_activity_false_positive_rate"],
        "unauthorized_false_positive_rate": unauthorized_fpr is not None and unauthorized_fpr <= POLICY["max_unauthorized_false_positive_rate"],
        "authorization_decision_consistency": invalid_definitive == 0,
        "detector_failures": failures <= POLICY["max_detector_failures"],
    }
    qualified = all(criteria.values()) and not test_fixture
    return {
        "qualified": qualified,
        "status": "practical_qualified" if qualified else (
            "synthetic_fixture_not_qualifying" if test_fixture else "practical_blocked"
        ), "policy_id": POLICY["policy_id"],
        "criteria": criteria,
        "support": {
            "scenes": len(frozen["scenes"]), "cameras": frozen["cameras"],
            "sites": frozen["sites"], "truth_positive": frozen["positive"],
            "truth_negative": frozen["negative"], "abstentions": abstentions,
            "definitive_absent_authorization_opportunities": definitive_opportunities,
        },
        "metrics": {
            "activity_recall": recall, "activity_false_positive_rate": fpr,
            "unauthorized_false_positive_rate": unauthorized_fpr,
            "decision_coverage": coverage, "detector_failures": failures,
            "inconsistent_authorization_decisions": invalid_definitive,
            "confusion": {k: confusion[k] for k in ("tp", "fp", "fn", "tn")},
        },
        "provenance": {
            "manifest_sha256": frozen["manifest_sha256"],
            "profile_sha256": frozen["profile_sha256"],
            "model_xml_sha256": frozen["model_xml_sha256"],
            "model_bin_sha256": frozen["model_bin_sha256"],
            "prediction_origin": "injected_synthetic_nonqualifying" if test_fixture else "actual_openvino_practical_pipeline_unsigned",
        },
        "limitations": [
            "Practical activity is visible worker-local motion, not worker competency or quality.",
            "Authorization remains an external, independently supplied schedule assertion.",
            "Blinding is an operator attestation, not cryptographically proven.",
            "CI synthetic scenes never qualify a real government training centre.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent frozen practical-work model qualification")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check-inputs", action="store_true")
    args = parser.parse_args()
    try:
        protocol = load(args.manifest) if args.check_inputs else None
        report = ({
            "qualified": False, "status": "inputs_pinned_no_inference",
            "manifest_sha256": protocol["manifest_sha256"],
        } if protocol else qualify(args.manifest))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        report = {"qualified": False, "status": "practical_blocked", "reason": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if report["status"] != "inputs_pinned_no_inference" and not report["qualified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
