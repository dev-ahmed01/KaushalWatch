"""Exercise actual attendance/camera/practical pipelines on short public EPFL video.

No annotations proving authorised training, skills or practical work exist for
this source. Report only pipeline execution, abstention, and detector provenance.
Raw video and anonymised temporary case images stay in a disposable directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.person_detector import build_person_detector
from app.services.practical_activity_pipeline import PracticalActivityPipeline
from app.services.video_pipeline import VideoCompliancePipeline


def checksum(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def public_excerpt(source: Path, target: Path, seconds: float):
    import cv2
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise ValueError("EPFL source video unavailable")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not 1 <= fps <= 120 or width < 80 or height < 80:
        raise ValueError("Invalid EPFL source fps/dimensions")
    frame_limit = int(round(fps * seconds))
    writer = cv2.VideoWriter(
        str(target), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Cannot create temporary EPFL excerpt")
    written = 0
    try:
        while written < frame_limit:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(frame)
            written += 1
    finally:
        cap.release()
        writer.release()
    if written < min(frame_limit, 40):
        raise ValueError("EPFL excerpt has too few decoded frames")
    return {"fps": fps, "width": width, "height": height, "frames": written}



def temporal_diagnostic(rows: list[dict]) -> dict:
    """Explain sampled detector -> confirmed-track -> occupancy transitions.

    Trace is from the *same* real pipeline pass. Restrict numerical comparisons
    to post-warmup eligible samples; withheld/untrusted counts remain unknown.
    No frames, position tracks, persons or frame hashes leave the runner.
    """
    eligible = [row for row in rows if row["detector_eligible"]]
    def positive_count(field: str) -> int:
        return sum(int(row[field] > 0) for row in eligible)

    if not eligible:
        explanation = "no_eligible_post_warmup_samples"
    elif not positive_count("raw_count"):
        explanation = "no_raw_detections_in_eligible_samples"
    elif not positive_count("confirmed_count"):
        explanation = "raw_detections_without_confirmed_tracks"
    elif not positive_count("smoothed_count"):
        explanation = "confirmed_tracks_without_positive_smoothed_occupancy"
    else:
        explanation = "positive_smoothed_occupancy_observed"

    return {
        "classification": explanation,
        "all_sampled_frames": len(rows),
        "eligible_post_warmup_samples": len(eligible),
        "camera_trusted_samples": sum(bool(row["camera_trusted"]) for row in rows),
        "pre_warmup_samples": sum(not row["warmup_complete"] for row in rows),
        "post_warmup_raw_positive_samples": positive_count("raw_count"),
        "post_warmup_confirmed_positive_samples": positive_count("confirmed_count"),
        "post_warmup_registered_positive_samples": positive_count("registered_count"),
        "post_warmup_smoothed_positive_samples": positive_count("smoothed_count"),
        "peak_raw_count": max((row["raw_count"] for row in eligible), default=None),
        "peak_confirmed_count": max((row["confirmed_count"] for row in eligible), default=None),
        "peak_smoothed_count": max((row["smoothed_count"] for row in eligible), default=None),
        "first_post_warmup_raw_detection_sec": next(
            (row["second"] for row in eligible if row["raw_count"] > 0), None),
        "first_post_warmup_confirmed_sec": next(
            (row["second"] for row in eligible if row["confirmed_count"] > 0), None),
        "sampling_trace": [
            {
                "frame_index": row["frame_index"], "second": row["second"],
                "camera_trusted": row["camera_trusted"],
                "warmup_complete": row["warmup_complete"],
                "detector_eligible": row["detector_eligible"],
                "raw_count": row["raw_count"],
                "candidate_count": row["candidate_count"],
                "confirmed_count": row["confirmed_count"],
                "registered_count": row["registered_count"],
                "smoothed_count": row["smoothed_count"],
            }
            for row in rows
        ],
        "limitations": (
            "This is a development-only public-source trace. Pre-warmup and "
            "untrusted measurements are withheld; counts alone do not establish "
            "independent ground-truth accuracy."
        ),
    }


def public_annotation_diagnostic(path: Path, rows: list[dict]) -> dict:
    """Describe EPFL benchmark annotation overlap, never qualify attendance."""
    from evaluation.benchmark_epfl_detection import parse_epfl_gt

    boxes_by_frame = parse_epfl_gt(path)
    if not boxes_by_frame:
        raise ValueError("EPFL public annotation file contains no person boxes")
    first_frame, last_frame = min(boxes_by_frame), max(boxes_by_frame)
    overlap = [row for row in rows if first_frame <= row["frame_index"] <= last_frame]
    positives = [
        row for row in overlap
        if boxes_by_frame.get(row["frame_index"], [])
    ]
    return {
        "annotation_sha256": checksum(path),
        "first_annotated_person_frame": first_frame,
        "last_annotated_person_frame": last_frame,
        "sampled_frames_in_annotated_person_range": len(overlap),
        "sampled_frames_with_person_boxes": len(positives),
        "first_sampled_frame_with_person_boxes": (
            positives[0]["frame_index"] if positives else None
        ),
        "post_warmup_samples_with_person_boxes": sum(
            row["detector_eligible"] for row in positives
        ),
        "interpretation": (
            "Development benchmark labels from an already-inspected source; "
            "the span before the first labelled person is not assumed to be "
            "independently verified empty. Benchmark and tiled operational "
            "detector settings are distinct."
        ),
    }


def execute(source: Path, out: Path, *, excerpt_seconds: float = 6.0,
            ground_truth: Path | None = None):
    if os.getenv("KAUSHALWATCH_PERSON_DETECTOR") != "openvino":
        raise RuntimeError("Smoke requires explicit real OpenVINO, not fallback")
    model_xml_raw = os.getenv("KAUSHALWATCH_OPENVINO_MODEL_XML")
    if not model_xml_raw:
        raise RuntimeError("Pinned OpenVINO model path must be provided")
    model_xml = Path(model_xml_raw).expanduser().resolve()
    model_bin = model_xml.with_suffix(".bin")
    if not model_xml.is_file() or not model_bin.is_file():
        raise ValueError("OpenVINO model weights not downloaded")
    profile_path = ROOT / "configs/vision_profiles/kaushalwatch-fixed-camera-v1.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    a, p = profile["attendance"], profile["practical_activity"]
    d = profile["person_detection"]
    if d["backend"] != "openvino":
        raise RuntimeError("Frozen demo profile does not select OpenVINO")
    if (os.getenv("KAUSHALWATCH_OPENVINO_TILED", "").lower()
        not in {"true", "1", "yes"}):
        raise RuntimeError("Frozen tiled OpenVINO inference must be enabled")
    detector = build_person_detector()
    if detector.info.backend != "openvino" or not detector.info.authoritative:
        raise RuntimeError("Detector fell back to an unqualified model")
    if (detector.confidence != d["confidence"] or detector.tiled != d["tiled"]
        or detector.tile_overlap != d["tile_overlap"]
        or detector.tile_nms_iou != d["tile_nms_iou"]):
        raise RuntimeError("OpenVINO settings do not match frozen profile")
    with tempfile.TemporaryDirectory(prefix="kw-real-video-smoke-") as workspace:
        temp = Path(workspace)
        video = temp / "epfl-excerpt.avi"
        meta = public_excerpt(source, video, excerpt_seconds)
        attendance_trace: list[dict] = []
        attendance = VideoCompliancePipeline(
            temp/"attendance-evidence", temp/"attendance-index.json",
            detector=detector,
        ).run(
            video_path=video,
            reported_attendance=3,  # Deliberately artificial, not an official register
            centre_id="EPFL-PUBLIC-LAB",
            batch_id="PUBLIC-DIAGNOSTIC-NO-REAL-REGISTER",
            camera_id="EPFL-CAM-0",
            sample_every_seconds=a["sample_every_seconds"],
            mismatch_threshold_pct=a["mismatch_threshold_pct"],
            persistence_threshold=a["persistence_threshold"],
            minimum_trusted_ratio=a["minimum_trusted_ratio"],
            track_confirmation_seconds=a["track_confirmation_seconds"],
            attendance_registration_seconds=a["registration_warmup_seconds"],
            track_grace_seconds=a["track_grace_seconds"],
            occupancy_count_source=a["count_source"],
            occupancy_smoother_window=a["smoother_window"],
            observation_sink=attendance_trace.append,
        )
        practical = PracticalActivityPipeline(
            temp/"practical-evidence", temp/"practical-index.json",
            detector=detector,
        ).run(
            video_path=video,
            zones=[{"zone_id":"PUBLIC-LAB-ROI","x":0,"y":0,
                    "w":meta["width"],"h":meta["height"]}],
            authorization="unknown", # Real training authorisation is unavailable
            centre_id="EPFL-PUBLIC-LAB",
            batch_id="PUBLIC-DIAGNOSTIC-NO-REAL-AUTHORIZATION",
            camera_id="EPFL-CAM-0",
            confirmation_seconds=a["track_confirmation_seconds"],
            registration_seconds=a["registration_warmup_seconds"],
            grace_seconds=a["track_grace_seconds"],
            sample_every_seconds=p["sample_every_seconds"],
            activity_window_seconds=p["activity_window_seconds"],
            activity_required_ratio=p["activity_required_ratio"],
            motion_threshold=p["motion_threshold"],
            motion_pixel_delta=p["motion_pixel_delta"],
            minimum_zone_overlap=p["minimum_zone_overlap"],
            minimum_trusted_ratio=p["minimum_trusted_ratio"],
        )
        if (attendance.detector_backend != "openvino"
            or practical.detector_backend != "openvino"
            or not attendance.detector_authoritative
            or not practical.detector_authoritative
            or attendance.detector_failures
            or practical.detector_failures):
            raise RuntimeError("Model execution failed or silently fell back")
        if not attendance.frames_sampled or not practical.frames_processed:
            raise RuntimeError("No real OpenVINO pipeline observations produced")
        if practical.decision == "unauthorized_practical_activity":
            raise RuntimeError("Unknown authorization incorrectly triggered violation")
        report = {
            "status": "real_openvino_attendance_practical_camera_paths_executed",
            "qualified": False,
            "source": "EPFL Laboratory six-person Camera 0 public research video",
            "source_video_sha256": checksum(source),
            "excerpt_sha256": checksum(video),
            "excerpt": meta,
            "vision_profile_sha256": checksum(profile_path),
            "openvino_xml_sha256": checksum(model_xml),
            "openvino_bin_sha256": checksum(model_bin),
            "temporal_diagnostic": temporal_diagnostic(attendance_trace),
            "public_annotation_diagnostic": (
                public_annotation_diagnostic(ground_truth, attendance_trace)
                if ground_truth is not None else None
            ),
            "attendance": {
                "detector_backend": attendance.detector_backend,
                "detector_authoritative": attendance.detector_authoritative,
                "frames_sampled": attendance.frames_sampled,
                "estimated_occupancy": attendance.estimated_occupancy,
                "trusted_sample_ratio": attendance.trusted_sample_ratio,
                "detector_failures": attendance.detector_failures,
                "decision": attendance.decision,
                "attendance_evidence_reason": attendance.attendance_evidence_reason,
                "post_warmup_trusted_ratio": attendance.post_warmup_trusted_ratio,
                "post_warmup_trusted_samples": attendance.post_warmup_trusted_samples,
                "synthetic_reported_attendance": 3
            },
            "practical": {
                "detector_backend": practical.detector_backend,
                "detector_authoritative": practical.detector_authoritative,
                "frames_processed": practical.frames_processed,
                "trusted_frame_ratio": practical.trusted_frame_ratio,
                "detector_failures": practical.detector_failures,
                "decision": practical.decision,
                "authorization": "unknown",
                "activity_fraction": practical.practical_activity_fraction,
                "active_work_cells": practical.active_work_cells,
            },
            "limitations": [
                "Public laboratory movement is not training-centre practical work",
                "Synthetic reported attendance and unknown authorization cannot validate compliance",
                "Any detected case is an unreviewed diagnostic and never stored centrally",
                "Camera trust is exercised within the pipelines but real tamper accuracy is unverified",
                "Fresh independent multi-camera and external attendance labels are still required"
            ]
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({
            "status": report["status"], "qualified": False,
            "attendance": report["attendance"],
            "practical": report["practical"],
        }))
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--ground-truth", type=Path,
                        help="Optional EPFL public benchmark annotations; diagnostics only")
    args = parser.parse_args()
    if not 3 <= args.seconds <= 15:
        parser.error("Public diagnostic excerpt must be between 3 and 15 seconds")
    execute(args.video.resolve(), args.out, excerpt_seconds=args.seconds,
            ground_truth=args.ground_truth.resolve() if args.ground_truth else None)


if __name__ == "__main__":
    main()
