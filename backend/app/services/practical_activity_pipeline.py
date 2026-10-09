from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import uuid

import cv2
import numpy as np

from app.models import PracticalActivitySummary, WorkCellActivity
from app.services.activity_evidence import TemporalActivityGate, worker_motion_fraction
from app.services.anonymous_tracker import AnonymousCentroidTracker
from app.services.camera_trust import CameraTrustState, assess_camera
from app.services.camera_reference import load_reviewed_reference
from app.services.compliance_cases import (
    build_camera_integrity_case,
    build_camera_visibility_case,
    build_practical_activity_case,
)
from app.services.evidence import persist_evidence
from app.services.person_detector import Detection, Detector, build_person_detector
from app.services.privacy import anonymize_person_regions, full_frame_privacy_blur
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


def scale_work_zones(
    zones: list[dict],
    reference_width: int,
    reference_height: int,
    width: int,
    height: int,
) -> list[dict]:
    """Scale scene-specific zones when the same camera view is resized.

    This does not make a profile transferable to another camera angle. It only
    preserves geometry for the same scene at another resolution.
    """
    if reference_width <= 0 or reference_height <= 0:
        raise ValueError("Zone reference dimensions must be positive")
    if width <= 0 or height <= 0:
        raise ValueError("Video dimensions must be positive")

    reference_ratio = reference_width / reference_height
    target_ratio = width / height
    aspect_delta = abs(target_ratio - reference_ratio) / reference_ratio
    if aspect_delta > 0.03:
        raise ValueError(
            "Bundled work-zone profile is calibrated for a different aspect ratio. "
            "Use footage from the same camera geometry or upload a custom work-zone JSON."
        )

    scale_x = width / reference_width
    scale_y = height / reference_height
    scaled: list[dict] = []

    for zone in zones:
        copy = dict(zone)
        copy["x"] = int(round(float(zone["x"]) * scale_x))
        copy["y"] = int(round(float(zone["y"]) * scale_y))
        copy["w"] = max(1, int(round(float(zone["w"]) * scale_x)))
        copy["h"] = max(1, int(round(float(zone["h"]) * scale_y)))
        scaled.append(copy)

    return scaled


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

    The practical-work path now uses the same privacy-safe person-detector
    abstraction as attendance instead of requiring Ultralytics tracking directly.
    Short-lived centroid IDs have no identity meaning outside the video stream.
    Authorization remains external; vision never infers a person's identity,
    qualification or permission from appearance.
    """

    def __init__(
        self,
        evidence_root: Path,
        index_path: Path,
        detector: Detector | None = None,
    ):
        self.evidence_root = evidence_root
        self.index_path = index_path
        self.detector = detector or build_person_detector()

    def run(
        self,
        video_path: Path,
        zones: list[dict],
        authorization: str,
        centre_id: str,
        batch_id: str,
        camera_id: str,
        *,
        confirmation_seconds: float = 1.0,
        registration_seconds: float = 2.0,
        grace_seconds: float = 0.8,
        sample_every_seconds: float = 0.2,
        activity_window_seconds: float = 1.0,
        activity_required_ratio: float = 0.60,
        motion_threshold: float = 0.02,
        motion_pixel_delta: int = 18,
        minimum_zone_overlap: float = 0.15,
        minimum_trusted_ratio: float = 0.50,
        zone_reference_size: tuple[int, int] | None = None,
        reviewed_reference_manifest: str | Path | None = None,
        reviewed_reference_mode: str | None = None,
    ) -> PracticalActivitySummary:
        authorization = authorization.strip().lower()
        if authorization not in {"valid", "absent", "unknown"}:
            raise ValueError("authorization must be valid, absent, or unknown")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if width <= 0 or height <= 0:
            cap.release()
            raise ValueError("Could not read practical-work video dimensions")

        camera_trust_state = (
            load_reviewed_reference(
                reviewed_reference_manifest,
                camera_id=camera_id,
                mode=reviewed_reference_mode or "",
            )
            if reviewed_reference_manifest is not None
            else CameraTrustState()
        )
        if reviewed_reference_mode is not None and reviewed_reference_manifest is None:
            raise ValueError("Reference mode requires an explicitly reviewed manifest")
        zone_scaled = False
        reference_width: int | None = None
        reference_height: int | None = None
        if zone_reference_size is not None:
            reference_width, reference_height = zone_reference_size
            if (reference_width, reference_height) != (width, height):
                zones = scale_work_zones(
                    zones,
                    reference_width,
                    reference_height,
                    width,
                    height,
                )
                zone_scaled = True

        validate_work_zones(zones, width, height)

        detector_info = self.detector.info
        step = max(1, int(round(fps * max(0.05, sample_every_seconds))))
        effective_grace_seconds = max(
            float(grace_seconds),
            float(sample_every_seconds) * 1.25,
        )
        tracker = AnonymousCentroidTracker(max_distance=140.0, max_missed=2)
        presence = TrackPresenceRegistry(
            confirmation_seconds=confirmation_seconds,
            registration_seconds=registration_seconds,
            grace_seconds=effective_grace_seconds,
        )

        activity_window_samples = max(
            1,
            int(round(activity_window_seconds / max(sample_every_seconds, 0.05))),
        )
        activity_gates = {
            _zone_name(zone, index): TemporalActivityGate(
                window_frames=activity_window_samples,
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
        tamper_flags: list[bool] = []
        trust_reason_counter: Counter[str] = Counter()
        worst_camera_evidence: tuple[float, np.ndarray, list[str]] | None = None

        peak_stable_workers = 0
        practical_activity_frames = 0
        first_activity_time: float | None = None
        first_exception_evidence: tuple[np.ndarray, list[Detection], list[str]] | None = None

        previous_frame: np.ndarray | None = None
        reference_frame: np.ndarray | None = None
        detector_failures = 0
        detector_failure_messages: list[str] = []
        frames_sampled = 0
        frame_index = 0

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if reference_frame is None:
                    reference_frame = frame.copy()

                if frame_index % step != 0:
                    frame_index += 1
                    continue

                timestamp = frame_index / fps
                frames_sampled += 1

                trust = assess_camera(
                    frame,
                    previous_frame=previous_frame,
                    reference_frame=reference_frame,
                    state=camera_trust_state,
                    sample_seconds=step / fps,
                )
                trust_flags.append(trust.trusted)
                tamper_flags.append(trust.tamper_suspected)
                trust_reason_counter.update(trust.reasons)

                if not trust.trusted and (
                    worst_camera_evidence is None
                    or trust.score < worst_camera_evidence[0]
                ):
                    worst_camera_evidence = (
                        trust.score,
                        frame.copy(),
                        list(trust.reasons),
                    )

                detections: list[Detection] = []
                if trust.trusted:
                    try:
                        detections = self.detector.detect(frame)
                    except Exception as exc:
                        detector_failures += 1
                        detector_failure_messages.append(f"{type(exc).__name__}: {exc}")

                current_ids: set[int] = set()
                observations: list[TrackObservation] = []
                current_detections: list[Detection] = []

                if trust.trusted and detector_failures == 0:
                    tracks = tracker.update(detections)
                    for track in tracks:
                        if track.missed != 0:
                            continue
                        box = (track.x1, track.y1, track.x2, track.y2)
                        zone_id = _assign_zone(box, zones, minimum_zone_overlap)
                        current_ids.add(track.track_id)
                        observations.append(
                            TrackObservation(
                                track_id=track.track_id,
                                x1=track.x1,
                                y1=track.y1,
                                x2=track.x2,
                                y2=track.y2,
                                zone_id=zone_id,
                            )
                        )

                    current_detections = detections

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
                    activity = activity_gates[name].update(worker_present, motion)

                    zone_motion_scores[name].append(motion)
                    if worker_present:
                        zone_presence_frames[name] += 1
                    if activity.active and trust.trusted:
                        zone_active_frames[name] += 1
                        active_zone_ids_seen.add(name)
                        active_now.append(name)
                        any_active = True

                if any_active:
                    practical_activity_frames += 1
                    if first_activity_time is None:
                        first_activity_time = timestamp

                    if (
                        authorization in {"absent", "unknown"}
                        and first_exception_evidence is None
                    ):
                        first_exception_evidence = (
                            frame.copy(),
                            current_detections,
                            list(active_now),
                        )

                previous_frame = frame.copy()
                frame_index += 1
        finally:
            cap.release()

        if frames_sampled == 0:
            raise ValueError("No frames were processed from the video")

        trusted_ratio = sum(trust_flags) / len(trust_flags) if trust_flags else 0.0
        practical_fraction = practical_activity_frames / frames_sampled

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
                        zone_presence_frames[name] / frames_sampled
                    ),
                    activity_fraction=zone_active_frames[name] / frames_sampled,
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
            # If most unusable samples have no tamper evidence, report a
            # visibility issue, never an allegation of camera sabotage.
            unusable_count = sum(not item for item in trust_flags)
            tamper_count = sum(tamper_flags)
            case_factory = (
                build_camera_integrity_case
                if tamper_count > unusable_count / 2
                else build_camera_visibility_case
            )
            case = case_factory(
                centre_id=centre_id,
                batch_id=batch_id,
                camera_id=camera_id,
                reasons=common_reasons,
                trust_score=round(score, 2),
            )
            evidence_id = f"EV-{uuid.uuid4().hex[:10].upper()}"
            private_frame = full_frame_privacy_blur(frame)
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
                        "trusted_frame_ratio": round(trusted_ratio, 4),
                        "privacy_transform": "full_frame_blur_due_untrusted_camera",
                    },
                )
            )
            decision = "camera_evidence_insufficient"

        elif not detector_info.authoritative or detector_failures:
            decision = "detector_unavailable"

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
            total_frames / fps
            if fps and total_frames > 0
            else frames_sampled * sample_every_seconds
        )
        failure_message = (
            detector_failure_messages[-1]
            if detector_failure_messages
            else detector_info.message
        )

        return PracticalActivitySummary(
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
            authorization=authorization,
            decision=decision,
            zone_scaled=zone_scaled,
            zone_reference_width=reference_width,
            zone_reference_height=reference_height,
            frames_processed=frames_sampled,
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
            detector_backend=detector_info.backend,
            detector_mode=detector_info.mode,
            detector_authoritative=bool(
                detector_info.authoritative and detector_failures == 0
            ),
            detector_message=failure_message,
            detector_failures=detector_failures,
            case=case,
        )
