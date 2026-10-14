"""Frozen camera evidence-usability qualification on independent complete recordings.

Labels: UHCTD five-column headerless CSV, frame (1-based), class (0 normal,
1 covered, 2 defocused, 3 moved), three additional ignored annotation columns.
The evaluator calls the CURRENT released assess_camera with the SAME
sampled-frame / first-frame-reference semantics as VideoCompliancePipeline.
This only qualifies whether evidence should be withheld, NOT tamper intent.

Synthetic test fixtures and partial/preflight runs are never qualifying.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.services.camera_trust import assess_camera
from app.services.vision_profile import active_profile_path
from evaluation.heldout_qualification import sha256_file

CLASSES = {0: "normal", 1: "covered", 2: "defocused", 3: "moved"}
SHA = re.compile(r"^[0-9a-f]{64}$")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,100}$")
POLICY = {
    "policy_id": "camera-evidence-usability-provisional-v1",
    "min_heldout_recordings": 2,
    "min_cameras": 2,
    "min_normal_seconds": 15.0,
    "min_events_per_class": 2,
    "min_pre_event_normal_seconds": 2.0,
    "sample_every_seconds": 0.2,
    "min_event_detection_recall": 0.85,
    "min_per_class_event_recall": 0.75,
    "max_normal_false_untrusted_rate": 0.05,
    "max_normal_false_alarm_episodes_per_hour": 2.0,
    "max_p95_detection_delay_seconds": 5.0,
}
# Day 3 + Day 4 Camera B have already influenced candidate development.
# Path/name checks are a warning barrier, NOT cryptographic proof of independence.
KNOWN_DEVELOPMENT_MARKERS = (
    "uhctd_day3", "uhctd_day4", "uhctd-day3", "uhctd-day4",
    "uhctd_day_3", "uhctd_day_4", "uhctd day 3", "uhctd day 4",
)
PROVENANCE = ("source_origin", "license_basis", "privacy_basis")


def _ref(manifest: Path, item: object, description: str) -> Path:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError(f"{description}: a pinned path and SHA-256 are required")
    name, expected = item["path"], item["sha256"]
    if not isinstance(name, str) or not name.strip() or not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise ValueError(f"{description}: bad path or SHA-256")
    path = (manifest.parent / name).resolve()
    if not path.is_file() or not path.stat().st_size:
        raise ValueError(f"{description}: missing or empty file")
    if sha256_file(path) != expected:
        raise ValueError(f"{description}: SHA-256 mismatch")
    return path


def _name(value: object, description: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError(f"{description}: invalid stable identifier")
    return value


def _metadata(video: Path) -> dict:
    import cv2
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Cannot decode the frozen camera recording")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or frames < 1:
            raise ValueError("Video has invalid FPS/frame count")
        ok, first = cap.read()
        if not ok or first is None:
            raise ValueError("Pinned recording lacks a decoded first frame")
        return {"fps": fps, "frames": frames, "duration": frames / fps}
    finally:
        cap.release()


def _labels(path: Path, frame_count: int, fps: float) -> dict:
    count = 0
    by_class = Counter()
    events = Counter()
    last = None
    current_normal = 0
    qualified_events = Counter()
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, strict=True)
        for line in reader:
            if len(line) < 5:
                raise ValueError("Expected a UHCTD annotation row of at least 5 columns")
            try:
                frame_no = int(line[0].strip())
                cls = int(line[1].strip())
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid UHCTD frame number/class") from exc
            count += 1
            if frame_no != count or cls not in CLASSES:
                raise ValueError("UHCTD annotations must cover each frame exactly in 1-based order")
            by_class[cls] += 1
            if cls != last:
                if cls != 0:
                    events[cls] += 1
                    if current_normal / fps >= POLICY["min_pre_event_normal_seconds"]:
                        qualified_events[cls] += 1
                current_normal = 0
            if cls == 0:
                current_normal += 1
            last = cls
    if count != frame_count:
        raise ValueError("UHCTD annotation rows must equal video frame count")
    return {
        "normal_seconds": by_class[0] / fps,
        "events": events,
        "qualified_events": qualified_events,
        "frames": count,
        "sampled_class_counts": dict(by_class),
    }


def load_protocol(path: Path, *, allow_fixture: bool = False) -> dict:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError("Camera evidence qualification manifest is missing")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Unsupported camera evidence manifest schema")
    if raw.get("status") != "frozen" or ".example." in path.name:
        raise ValueError("Only a frozen protocol can be evaluated")
    if raw.get("fixture_only") is not False and not allow_fixture:
        raise ValueError("Fixtures cannot establish real camera qualification")
    if type(raw.get("fixture_only")) is not bool or raw.get("policy") != POLICY:
        raise ValueError("Fixture marker missing or review-locked policy changed")
    _name(raw.get("protocol_id"), "protocol_id")
    profile = _ref(path, raw.get("vision_profile"), "vision_profile")
    if profile != active_profile_path().resolve():
        raise ValueError("Frozen runtime vision profile does not match the protocol")
    settings = json.loads(profile.read_text(encoding="utf-8"))
    if settings.get("status") != "frozen_sih_candidate" or not isinstance(settings.get("camera_trust"), dict):
        raise ValueError("Frozen current-release camera trust profile required")
    if settings["camera_trust"].get("trusted_score_threshold") != 65.0:
        raise ValueError("Vision profile camera trust threshold differs from released engine")
    if not isinstance(raw.get("calibration"), list) or not raw["calibration"]:
        raise ValueError("Independent calibration partition is missing")
    if not isinstance(raw.get("heldout"), list) or len(raw["heldout"]) < POLICY["min_heldout_recordings"]:
        raise ValueError("Insufficient independent held-out camera recordings")
    all_ids, all_videos, all_recordings = set(), set(), set()
    heldout = []
    cameras = set()
    event_totals = Counter()
    normal_seconds = 0.0
    file_digests = {}
    for kind in ("calibration", "heldout"):
        for scene in raw[kind]:
            if not isinstance(scene, dict):
                raise ValueError("Invalid camera recording descriptor")
            for field in PROVENANCE:
                value = scene.get(field)
                if not isinstance(value, str) or len(value.strip()) < 12:
                    raise ValueError(f"{field}: meaningful dataset provenance is required")
                if not allow_fixture and any(x in value.lower() for x in ("synthetic", "example", "unknown", "placeholder")):
                    raise ValueError(f"{field}: fixture or placeholder provenance is ineligible")
            recording = _name(scene.get("recording_id"), "recording_id")
            camera = _name(scene.get("camera_id"), "camera_id")
            site = _name(scene.get("site_id"), "site_id")
            scene_id = _name(scene.get("scene_id"), "scene_id")
            if recording in all_recordings or scene_id in all_ids:
                raise ValueError("Calibration/hold-out recording leakage or duplicate scene")
            all_recordings.add(recording)
            all_ids.add(scene_id)
            video = _ref(path, scene.get("video"), "video")
            digest = sha256_file(video)
            if digest in all_videos:
                raise ValueError("Calibration/hold-out source video leakage or duplicate media")
            all_videos.add(digest)
            file_digests[scene_id] = digest
            if kind == "calibration":
                continue
            annotations = _ref(path, scene.get("annotations"), "annotations")
            if annotations.resolve() == video.resolve():
                raise ValueError("Video and annotation file cannot be identical")
            if scene.get("blinded_review") is not True or not _name(scene.get("reviewer_id"), "reviewer_id"):
                raise ValueError("Independent blinded-review metadata missing")
            if scene.get("previously_inspected") is not False:
                raise ValueError("Held-out source was not attested untouched")
            if not allow_fixture:
                descriptors = " ".join((recording, scene_id, str(video.parent), video.name, str(annotations.parent)))
                if any(marker in descriptors.lower().replace(" ", "_") for marker in KNOWN_DEVELOPMENT_MARKERS):
                    raise ValueError("Previously inspected UHCTD Day 3/Day 4 cannot be held-out")
            video_info = _metadata(video)
            label_info = _labels(annotations, video_info["frames"], video_info["fps"])
            cameras.add((site, camera))
            normal_seconds += label_info["normal_seconds"]
            event_totals.update(label_info["qualified_events"])
            heldout.append({
                "id": scene_id, "video": video, "annotations": annotations,
                "site": site, "camera": camera,
                "metadata": video_info, "labels": label_info,
            })
    if (len(cameras) < POLICY["min_cameras"] or normal_seconds < POLICY["min_normal_seconds"]
            or any(event_totals[k] < POLICY["min_events_per_class"] for k in (1, 2, 3))):
        raise ValueError("Insufficient camera/normal-duration/independent-event support")
    return {
        "manifest_sha256": sha256_file(path),
        "profile_sha256": sha256_file(profile),
        "scene_digests": file_digests,
        "profile": settings,
        "heldout": heldout,
        "cameras": len(cameras),
        "normal_seconds": normal_seconds,
        "events": dict(event_totals),
        "fixture_only": raw["fixture_only"],
    }


def _run_camera_scene(item: dict, profile: dict) -> dict:
    """Sample the released trust gate at the exact video pipeline cadence."""
    import cv2
    meta = item["metadata"]
    fps, frames = meta["fps"], meta["frames"]
    step = max(1, int(round(fps * POLICY["sample_every_seconds"])))
    camera = profile["camera_trust"]
    args = {
        "blur_threshold": camera["blur_threshold"],
        "dark_threshold": camera["dark_threshold"],
        "frozen_similarity": camera["frozen_similarity"],
        "scene_shift_threshold": camera["scene_shift_threshold"],
    }
    cap = cv2.VideoCapture(str(item["video"]))
    if not cap.isOpened():
        raise ValueError("Cannot open a pinned held-out video")
    label_stream = item["annotations"].open(newline="", encoding="utf-8-sig")
    labels = csv.reader(label_stream, strict=True)
    normal_sample_count = normal_untrusted = false_episodes = 0
    by_class = Counter()
    event_count = Counter()
    fresh_detection = Counter()
    latencies = []
    sample_index = 0
    reference = previous = None
    previous_alert = False
    current_class = None
    segment_start = 0
    pre_normal_frames = 0
    eligible_onset = False
    onset_alerted = False
    try:
        for frame_index in range(frames):
            row = next(labels, None)
            if row is None or len(row) < 2:
                raise ValueError("Incomplete annotation stream while scoring")
            cls = int(row[1])
            if cls != current_class:
                if cls != 0:
                    eligible_onset = pre_normal_frames / fps >= POLICY["min_pre_event_normal_seconds"]
                    if eligible_onset:
                        event_count[cls] += 1
                else:
                    eligible_onset = False
                current_class = cls
                segment_start = frame_index
                onset_alerted = False
                pre_normal_frames = 0
            if cls == 0:
                pre_normal_frames += 1
            if not cap.grab():
                raise ValueError("Unexpected source video EOF")
            if frame_index % step:
                continue
            success, frame = cap.retrieve()
            if not success or frame is None:
                raise ValueError("Video could not decode selected frame")
            if reference is None:
                reference = frame.copy()
            trust = assess_camera(frame, previous_frame=previous, reference_frame=reference, **args)
            previous = frame
            sample_index += 1
            alert = not trust.trusted
            if cls == 0:
                normal_sample_count += 1
                if alert:
                    normal_untrusted += 1
                    if not previous_alert:
                        false_episodes += 1
            else:
                by_class[(cls, "total")] += 1
                if alert:
                    by_class[(cls, "untrusted")] += 1
                if (eligible_onset and alert and not previous_alert and not onset_alerted):
                    onset_alerted = True
                    fresh_detection[cls] += 1
                    latencies.append((frame_index - segment_start) / fps)
            previous_alert = alert
        extra = next(labels, None)
        if extra is not None:
            raise ValueError("Annotation file contains extra frames")
    finally:
        cap.release()
        label_stream.close()
    return {
        "normal_samples": normal_sample_count,
        "normal_untrusted": normal_untrusted,
        "false_alarm_episodes": false_episodes,
        "by_class": by_class,
        "events": event_count,
        "fresh_detected": fresh_detection,
        "delays": latencies,
        "sampled": sample_index,
        "interval_seconds": step / fps,
    }


def evaluate(path: Path, *, test_fixture: bool = False) -> dict:
    data = load_protocol(path, allow_fixture=test_fixture)
    raw = {
        "status": "camera_evidence_not_qualified",
        "qualified": False, "policy_id": POLICY["policy_id"],
        "provenance": {
            "manifest_sha256": data["manifest_sha256"],
            "vision_profile_sha256": data["profile_sha256"],
            "source_digests": data["scene_digests"],
            "prediction_source": "released_assess_camera_pipeline",
        },
    }
    count = Counter()
    event_count, found = Counter(), Counter()
    delays = []
    normal_seconds = 0.0
    for scene in data["heldout"]:
        result = _run_camera_scene(scene, data["profile"])
        count["normal_samples"] += result["normal_samples"]
        count["normal_untrusted"] += result["normal_untrusted"]
        count["false_alarm_episodes"] += result["false_alarm_episodes"]
        for key in (1, 2, 3):
            count[f"{CLASSES[key]}_samples"] += result["by_class"][(key, "total")]
            count[f"{CLASSES[key]}_untrusted"] += result["by_class"][(key, "untrusted")]
            event_count[key] += result["events"][key]
            found[key] += result["fresh_detected"][key]
        delays.extend(result["delays"])
        normal_seconds += result["normal_samples"] * result["interval_seconds"]
    if not count["normal_samples"] or not sum(event_count.values()):
        raise ValueError("No actual normal or event predictions available")
    # Verify all pinned inputs still match their frozen digests after inference.
    after = load_protocol(path, allow_fixture=test_fixture)
    if after["manifest_sha256"] != data["manifest_sha256"] or after["scene_digests"] != data["scene_digests"]:
        raise ValueError("Pinned video/annotations or manifest changed during evaluation")
    normal_rate = count["normal_untrusted"] / count["normal_samples"]
    false_episodes_per_hour = count["false_alarm_episodes"] / (normal_seconds / 3600)
    denom = sum(event_count.values())
    recall = sum(found.values()) / denom
    delays.sort()
    p95 = delays[min(len(delays)-1, math.ceil(len(delays)*.95)-1)] if delays else None
    criteria = {
        "normal_false_untrusted_rate": normal_rate <= POLICY["max_normal_false_untrusted_rate"],
        "normal_false_alarm_episodes_per_hour": false_episodes_per_hour <= POLICY["max_normal_false_alarm_episodes_per_hour"],
        "fresh_event_detection_recall": recall >= POLICY["min_event_detection_recall"],
        "each_event_class_recall": all(
            event_count[k] and found[k]/event_count[k] >= POLICY["min_per_class_event_recall"]
            for k in (1, 2, 3)
        ),
        "p95_delay_seconds": p95 is not None and p95 <= POLICY["max_p95_detection_delay_seconds"],
    }
    qualified = all(criteria.values()) and not test_fixture
    return {
        **raw,
        "status": ("camera_evidence_qualified" if qualified else
                   "synthetic_fixture_not_qualifying" if test_fixture else
                   "camera_evidence_not_qualified"),
        "qualified": qualified, "criteria": criteria,
        "support": {"recordings": len(data["heldout"]), "cameras": data["cameras"],
                    "normal_seconds": round(normal_seconds, 3),
                    "independent_events": denom, "detected_events": sum(found.values()),
                    "events_by_class": {CLASSES[k]: event_count[k] for k in (1, 2, 3)}},
        "metrics": {
            "normal_false_untrusted_rate": round(normal_rate, 5),
            "normal_false_alarm_episodes_per_hour": round(false_episodes_per_hour, 5),
            "fresh_event_detection_recall": round(recall, 5),
            "p95_detection_delay_seconds": round(p95, 5) if p95 is not None else None,
            "per_class_event_recall": {
                CLASSES[k]: round(found[k]/event_count[k], 5) if event_count[k] else None
                for k in (1, 2, 3)
            },
            "per_class_untrusted_sample_rate": {
                CLASSES[k]: round(count[f"{CLASSES[k]}_untrusted"]/count[f"{CLASSES[k]}_samples"], 5)
                if count[f"{CLASSES[k]}_samples"] else None for k in (1, 2, 3)
            },
        },
        "limitations": [
            "Flags evidence usability, NOT malicious camera tampering or stream freshness.",
            "No outside system proves independent review or that videos have never been inspected.",
            "The current release first-frame-reference gate is measured; PR #54 is NOT imported.",
            "These provisional engineering thresholds are not MSDE-approved requirements.",
            "Synthetic CI fixtures never establish real-camera qualification.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Independent held-out camera evidence-usability evaluator")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--check-inputs", action="store_true")
    args = p.parse_args()
    try:
        if args.check_inputs:
            found = load_protocol(args.manifest)
            report = {"qualified": False, "status": "inputs_pinned_no_inference",
                      "support": {"recordings": len(found["heldout"]), "cameras": found["cameras"]},
                      "manifest_sha256": found["manifest_sha256"]}
        else:
            report = evaluate(args.manifest)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        report = {"qualified": False, "status": "camera_evidence_blocked",
                  "reason": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] == "inputs_pinned_no_inference":
        return
    if not report["qualified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
