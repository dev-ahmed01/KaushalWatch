from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import uuid

import cv2
import numpy as np

from app.models import PracticalActivitySummary, WorkCellActivity
from app.services.activity_evidence import TemporalActivityGate, worker_motion_fraction
from app.services.camera_trust import assess_camera
from app.services.compliance_cases import (
    build_camera_integrity_case,
    build_practical_activity_case,
)
from app.services.evidence import persist_evidence
from app.services.person_detector import Detection
from app.services.privacy import anonymize_person_regions
from app.services.track_presence import TrackObservation, TrackPresenceRegistry


def _zone_name(zone: dict, index: int) -> str:
    return str(zone.get("zone_id") or f"work_zone_{index + 1}")


def _zone_rect(zone: dict) -> tuple[int, int, int, int]:
    x1 = int(zone["x"])
    y1 = int(zone["y"])
    return x1, y1, x1 + int(zone["w"]), y1 + int(zone["h"])


def _intersection_ratio(
    box: tuple[int, int, int, int],
    zone: dict,
) -> float:
    x1, y1, x2, y2 = box
    zx1, zy1, zx2, zy2 = _zone_rect(zone)
    ix1, iy1 = max(x1, zx1), max(y1, zy1)
    ix2, iy2 = min(x2, zx2), min(y2, zy2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    intersection = iw * ih
    person_area = max(1, (x2 - x1) * (y2 - y1))
    return intersection / person_area


def _assign_zone(
    box: tuple[int, int, int, int],
    zones: list[dict],
    minimum_overlap: float,
) -> str | None:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0

    best_zone: str | None = None
    best_score = 0.0

    for index, zone in enumerate(zones):
        zx1, zy1, zx2, zy2 = _zone_rect(zone)
        overlap = _intersection_ratio(box, zone)
        centre_inside = zx1 <= cx <= zx2 and zy1 <= cy <= zy2
        score = 1.0 + overlap if centre_inside else overlap
        if score >= minimum_overlap and score > best_score:
            best_score = score
            best_zone = _zone_name(zone, index)

    return best_zone


def validate_work_zones(
    zones: list[dict],
    width: int,
    height: int,
) -> None:
    if not zones:
        raise ValueError("At least one work zone is required")

    seen: set[str] = set()

    for index, zone in enumerate(zones):
        required = {"x", "y", "w", "h"}
        if not required.issubset(zone):
            missing = ", ".join(sorted(required - set(zone)))
            raise ValueError(f"Work zone {index + 1} missing: {missing}")

        name = _zone_name(zone, index)
        if name in seen:
            raise ValueError(f"Duplicate work zone id: {name}")
        seen.add(name)

        x = int(zone["x"])
        y = int(zone["y"])
        w = int(zone["w"])
        h = int(zone["h"])

        if w <= 0 or h <= 0:
            raise ValueError(f"Work zone {name} must have positive width/height")
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(
                f"Work zone {name} is outside video bounds {width}x{height}"
            )


class PracticalActivityPipeline:
    """Worker-centric practical activity pipeline for fixed-camera CCTV.

    Vision establishes anonymous stable presence and visual motion inside configured
    work cells. Authorization is supplied externally and is never inferred from a
    person's appearance.
    """

    def __init__(self, evidence_root: Path, index_path: Path):
        self.evidence_root = evidence_root
        self.index_path = index_path

    def run(
        self,
        video_path: Path,
        zones: list[dict],
        authorization: str,
        centre_id: str,
        batch_id: str,
        camera_id: str,
        *,
        model_name: str = "yolo11n.pt",
        imgsz: int = 640,
        confidence: float = 0.35,
        nms_iou: float = 0.50,
        tracker_name: str = "bytetrack.yaml",
        confirmation_seconds: float = 1.0,
        registration_seconds: float = 2.0,
        grace_seconds: float = 0.8,
        activity_window_seconds: float = 1.0,
        activity_required_ratio: float = 0.60,
        motion_threshold: float = 0.02,
        motion_pixel_delta: int = 18,
        minimum_zone_overlap: float = 0.15,
        minimum_trusted_ratio: float = 0.50,
    ) -> PracticalActivitySummary:
        authorization = authorization.strip().lower()
        if authorization not in {"valid", "absent", "unknown"}:
            raise ValueError("authorization must be valid, absent, or unknown")

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Practical-work video analysis requires optional YOLO dependencies. "
                "Install backend/requirements-yolo-demo.txt."
            ) from exc

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        validate_work_zones(zones, width, height)

        model = YOLO(model_name)
        presence = TrackPresenceRegistry(
            confirmation_seconds=confirmation_seconds,
            registration_seconds=registration_seconds,
            grace_seconds=grace_seconds,
        )

        activity_window_frames = max(
            1,
            int(round(activity_window_seconds * fps)),
        )
        activity_gates = {
            _zone_name(zone, index): TemporalActivityGate(
                window_frames=activity_window_frames,
                motion_fraction_threshold=motion_threshold,
                required_positive_ratio=activity_required_ratio,
            )
            for index, zone in enumerate(zones)
        }

        zone_motion_scores: dict[str, list[float]] = defaultdict(list)
        zone_presence_frames: dict[str, int] = defaultdict(int)
        zone_active_frames: dict[str, int] = defaultdict(int)
        active_zone_ids_seen: set[str] = set()

        trust_flags: list[bool] = []
        trust_reason_counter: Counter[str] = Counter()
        worst_camera_evidence: tuple[float, np.ndarray, list[str]] | None = None

        peak_stable_workers = 0
        practical_activity_frames = 0
        first_activity_time: float | None = None
        first_exception_evidence: tuple[np.ndarray, list[Detection], list[str]] | None = None

        previous_frame: np.ndarray | None = None
        reference_frame: np.ndarray | None = None
        frame_no = 0

        stream = model.track(
            source=str(video_path),
            stream=True,
            persist=True,
            tracker=tracker_name,
            classes=[0],
            conf=confidence,
            iou=nms_iou,
            imgsz=imgsz,
            verbose=False,
        )

        for result in stream:
            frame = result.orig_img.copy()
            timestamp = frame_no / fps

            if reference_frame is None:
                reference_frame = frame.copy()

            trust = assess_camera(
                frame,
                previous_frame=previous_frame,
                reference_frame=reference_frame,
            )
            trust_flags.append(trust.trusted)
            trust_reason_counter.update(trust.reasons)

            if not trust.trusted and (
                worst_camera_evidence is None or trust.score < worst_camera_evidence[0]
            ):
                worst_camera_evidence = (
                    trust.score,
                    frame.copy(),
                    list(trust.reasons),
                )

            boxes: list[list[float]] = []
            confidences: list[float] = []
            track_ids: list[int | None] = []

            if trust.trusted and len(result.boxes):
                boxes = result.boxes.xyxy.cpu().numpy().tolist()
                confidences = result.boxes.conf.cpu().numpy().tolist()
                track_ids = (
                    result.boxes.id.int().cpu().tolist()
                    if result.boxes.id is not None
                    else [None] * len(boxes)
                )

            current_ids: set[int] = set()
            observations: list[TrackObservation] = []
            current_detections: list[Detection] = []

            for index, raw_box in enumerate(boxes):
                track_id = track_ids[index] if index < len(track_ids) else None
                if track_id is None:
                    continue

                x1, y1, x2, y2 = [int(round(value)) for value in raw_box]
                confidence_value = float(confidences[index])
                box = (x1, y1, x2, y2)
                zone_id = _assign_zone(box, zones, minimum_zone_overlap)

                current_ids.add(int(track_id))
                observations.append(
                    TrackObservation(
                        track_id=int(track_id),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=confidence_value,
                        zone_id=zone_id,
                    )
                )
                current_detections.append(
                    Detection(
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=confidence_value,
                    )
                )

            presence.update(timestamp, observations)
            peak_stable_workers = max(
                peak_stable_workers,
                presence.registered_count,
            )

            registered_by_zone: dict[str, list] = defaultdict(list)
            for track in presence.registered_tracks:
                if track.track_id in current_ids and track.zone_id:
                    registered_by_zone[track.zone_id].append(track)

            any_active = False
            active_now: list[str] = []

            for index, zone in enumerate(zones):
                name = _zone_name(zone, index)
                worker_boxes = [
                    track.bbox
                    for track in registered_by_zone.get(name, [])
                ]
                motion = worker_motion_fraction(
                    previous_frame,
                    frame,
                    worker_boxes,
                    pixel_delta_threshold=motion_pixel_delta,
                )
                worker_present = bool(worker_boxes) and trust.trusted
                decision = activity_gates[name].update(worker_present, motion)

                zone_motion_scores[name].append(motion)
                if worker_present:
                    zone_presence_frames[name] += 1
                if decision.active and trust.trusted:
                    zone_active_frames[name] += 1
                    active_zone_ids_seen.add(name)
                    active_now.append(name)
                    any_active = True

            if any_active:
                practical_activity_frames += 1
                if first_activity_time is None:
                    first_activity_time = timestamp

                if authorization in {"absent", "unknown"} and first_exception_evidence is None:
                    first_exception_evidence = (
                        frame.copy(),
                        current_detections,
                        list(active_now),
                    )

            previous_frame = frame
            frame_no += 1

        if frame_no == 0:
            raise ValueError("No frames were processed from the video")

        trusted_ratio = (
            sum(trust_flags) / len(trust_flags)
            if trust_flags
            else 0.0
        )
        practical_fraction = practical_activity_frames / frame_no

        work_cells: list[WorkCellActivity] = []
        for index, zone in enumerate(zones):
            name = _zone_name(zone, index)
            scores = np.asarray(zone_motion_scores[name], dtype=float)
            if scores.size == 0:
                scores = np.asarray([0.0], dtype=float)

            work_cells.append(
                WorkCellActivity(
                    zone_id=name,
                    registered_worker_presence_fraction=(
                        zone_presence_frames[name] / frame_no
                    ),
                    activity_fraction=zone_active_frames[name] / frame_no,
                    worker_motion_fraction_p50=float(np.percentile(scores, 50)),
                    worker_motion_fraction_p90=float(np.percentile(scores, 90)),
                    worker_motion_fraction_p95=float(np.percentile(scores, 95)),
                )
            )

        case = None
        decision = "no_persistent_practical_activity"

        if trusted_ratio < minimum_trusted_ratio and worst_camera_evidence is not None:
            score, frame, reasons = worst_camera_evidence
            common_reasons = [
                reason for reason, _ in trust_reason_counter.most_common(3)
            ] or reasons
            case = build_camera_integrity_case(
                centre_id=centre_id,
                batch_id=batch_id,
                camera_id=camera_id,
                reasons=common_reasons,
                trust_score=round(score, 2),
            )
            evidence_id = f"EV-{uuid.uuid4().hex[:10].upper()}"
            case.evidence.append(
                persist_evidence(
                    frame,
                    self.evidence_root,
                    self.index_path,
                    evidence_id,
                    {
                        "centre_id": centre_id,
                        "batch_id": batch_id,
                        "camera_id": camera_id,
                        "case_type": "camera_integrity",
                        "trusted_frame_ratio": round(trusted_ratio, 4),
                    },
                )
            )
            decision = "camera_evidence_insufficient"

        elif practical_fraction > 0:
            if authorization == "valid":
                decision = "authorized_practical_activity"
            elif authorization == "absent":
                decision = "unauthorized_practical_activity"
            else:
                decision = "authorization_review_required"

            case = build_practical_activity_case(
                centre_id=centre_id,
                batch_id=batch_id,
                camera_id=camera_id,
                authorization=authorization,
                practical_activity_fraction=practical_fraction,
                active_work_cells=len(active_zone_ids_seen),
            )

            if case is not None and first_exception_evidence is not None:
                frame, detections, active_zones = first_exception_evidence
                private_frame = anonymize_person_regions(frame, detections)
                evidence_id = f"EV-{uuid.uuid4().hex[:10].upper()}"
                case.evidence.append(
                    persist_evidence(
                        private_frame,
                        self.evidence_root,
                        self.index_path,
                        evidence_id,
                        {
                            "centre_id": centre_id,
                            "batch_id": batch_id,
                            "camera_id": camera_id,
                            "case_type": case.case_type,
                            "authorization": authorization,
                            "active_work_cells": active_zones,
                            "practical_activity_fraction": round(
                                practical_fraction,
                                4,
                            ),
                            "privacy_transform": (
                                "person_regions_blurred_before_central_retention"
                            ),
                            "individual_identification": False,
                        },
                    )
                )

        duration_sec = (
            frame_no / fps
            if fps
            else (total_frames / 25.0 if total_frames else 0.0)
        )

        return PracticalActivitySummary(
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
            authorization=authorization,
            decision=decision,
            frames_processed=frame_no,
            duration_sec=round(duration_sec, 3),
            trusted_frame_ratio=round(trusted_ratio, 4),
            peak_stable_workers=peak_stable_workers,
            practical_activity_fraction=round(practical_fraction, 4),
            first_practical_activity_time_sec=(
                round(first_activity_time, 3)
                if first_activity_time is not None
                else None
            ),
            active_work_cells=len(active_zone_ids_seen),
            work_cells=work_cells,
            case=case,
        )
