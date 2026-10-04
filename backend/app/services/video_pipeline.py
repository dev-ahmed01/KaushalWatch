from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path
import uuid

import cv2
import numpy as np

from app.models import AttendanceObservation, ComplianceCase, ProcessSummary
from app.services.anonymous_tracker import AnonymousCentroidTracker
from app.services.camera_trust import assess_camera
from app.services.compliance_cases import build_camera_integrity_case
from app.services.evidence import persist_evidence
from app.services.occupancy import OccupancySmoother, discrepancy_pct
from app.services.person_detector import Detector, build_person_detector
from app.services.privacy import anonymize_person_regions
from app.services.track_presence import TrackObservation, TrackPresenceRegistry

LOGGER = logging.getLogger(__name__)


class VideoCompliancePipeline:
    def __init__(
        self,
        evidence_root: Path,
        index_path: Path,
        detector: Detector | None = None,
    ):
        self.detector = detector or build_person_detector()
        self.evidence_root = evidence_root
        self.index_path = index_path

    def run(
        self,
        video_path: Path,
        reported_attendance: int,
        centre_id: str,
        batch_id: str,
        camera_id: str = "CAM-01",
        sample_every_seconds: float = 0.2,
        mismatch_threshold_pct: float = 15.0,
        persistence_threshold: float = 0.6,
        minimum_trusted_ratio: float = 0.5,
        track_confirmation_seconds: float = 1.0,
        attendance_registration_seconds: float = 2.0,
        track_grace_seconds: float = 0.8,
    ) -> ProcessSummary:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        detector_info = self.detector.info
        LOGGER.info(
            "Attendance run detector=%s mode=%s authoritative=%s video=%s",
            detector_info.backend,
            detector_info.mode,
            detector_info.authoritative,
            video_path,
        )

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, int(round(fps * sample_every_seconds)))
        smoother = OccupancySmoother(window=5)
        tracker = AnonymousCentroidTracker(max_distance=140.0, max_missed=2)

        effective_grace_seconds = max(
            float(track_grace_seconds),
            float(sample_every_seconds) * 1.25,
        )
        presence = TrackPresenceRegistry(
            confirmation_seconds=track_confirmation_seconds,
            registration_seconds=attendance_registration_seconds,
            grace_seconds=effective_grace_seconds,
        )

        observations: list[AttendanceObservation] = []
        mismatch_flags: list[bool] = []
        trust_flags: list[bool] = []
        trust_reason_counter: Counter[str] = Counter()

        prev_frame = None
        reference_frame = None
        best_evidence: tuple[float, np.ndarray, int, list] | None = None
        worst_camera_evidence: tuple[float, np.ndarray, list[str]] | None = None

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

                frames_sampled += 1
                sec = frame_index / fps
                trust = assess_camera(
                    frame,
                    previous_frame=prev_frame,
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

                detections = []
                if trust.trusted:
                    try:
                        detections = self.detector.detect(frame)
                    except Exception as exc:
                        detector_failures += 1
                        message = f"{type(exc).__name__}: {exc}"
                        detector_failure_messages.append(message)
                        LOGGER.exception(
                            "Person detector failed at frame=%s second=%.3f",
                            frame_index,
                            sec,
                        )

                raw_count = len(detections)
                confidences = [round(float(det.confidence), 4) for det in detections]
                LOGGER.debug(
                    "Attendance sample frame=%s second=%.3f trusted=%s raw_count=%s confidences=%s",
                    frame_index,
                    sec,
                    trust.trusted,
                    raw_count,
                    confidences,
                )

                presence_observations: list[TrackObservation] = []
                if trust.trusted and detector_failures == 0:
                    tracks = tracker.update(detections)
                    tracker_count = sum(track.missed <= 1 for track in tracks)
                    for track in tracks:
                        if track.missed != 0:
                            continue
                        presence_observations.append(
                            TrackObservation(
                                track_id=track.track_id,
                                x1=track.x1,
                                y1=track.y1,
                                x2=track.x2,
                                y2=track.y2,
                            )
                        )
                else:
                    tracker_count = 0

                presence.update(sec, presence_observations)
                candidate_count = presence.candidate_count
                confirmed_count = presence.confirmed_count
                registered_count = presence.registered_count

                warmup_complete = sec >= attendance_registration_seconds
                # Do not seed the decision smoother with intentional pre-registration
                # zeros. Otherwise a stable track can become registered correctly at
                # 2s while the median window still reports a false mismatch from the
                # maturity period.
                smooth = (
                    smoother.update(registered_count)
                    if warmup_complete
                    else registered_count
                )
                d_pct = discrepancy_pct(reported_attendance, smooth)

                is_mismatch = (
                    detector_info.authoritative
                    and detector_failures == 0
                    and trust.trusted
                    and warmup_complete
                    and d_pct >= mismatch_threshold_pct
                )

                observations.append(
                    AttendanceObservation(
                        second=round(sec, 2),
                        raw_count=raw_count,
                        tracker_count=tracker_count,
                        candidate_count=candidate_count,
                        confirmed_count=confirmed_count,
                        registered_count=registered_count,
                        smoothed_count=smooth,
                        camera_trust=trust.score,
                    )
                )
                mismatch_flags.append(is_mismatch)

                if is_mismatch and (
                    best_evidence is None or d_pct > best_evidence[0]
                ):
                    best_evidence = (d_pct, frame.copy(), smooth, detections)

                prev_frame = frame.copy()
                frame_index += 1
        finally:
            cap.release()

        if not observations:
            raise ValueError("No usable frames were sampled from the video")

        trusted_ratio = sum(trust_flags) / len(trust_flags) if trust_flags else 0.0
        trusted_counts = [
            observation.smoothed_count
            for observation, is_trusted in zip(observations, trust_flags)
            if is_trusted and observation.second >= attendance_registration_seconds
        ]

        runtime_authoritative = (
            detector_info.authoritative and detector_failures == 0
        )

        estimated_internal = int(np.median(trusted_counts)) if trusted_counts else 0
        estimated: int | None = estimated_internal if runtime_authoritative else None
        overall_pct: float | None = (
            discrepancy_pct(reported_attendance, estimated_internal)
            if runtime_authoritative
            else None
        )

        eligible_mismatch_flags = [
            flag
            for observation, flag in zip(observations, mismatch_flags)
            if observation.second >= attendance_registration_seconds
        ]
        persistence = (
            sum(eligible_mismatch_flags) / len(eligible_mismatch_flags)
            if eligible_mismatch_flags
            else 0.0
        )

        detector_mode = detector_info.mode
        detector_message = detector_info.message
        if detector_failures:
            detector_mode = "unavailable"
            unique_failures = list(dict.fromkeys(detector_failure_messages))
            detector_message = (
                "Detector unavailable during analysis. Attendance conclusions are "
                "suspended. " + "; ".join(unique_failures[:3])
            )
        elif not detector_info.authoritative:
            detector_message = (
                detector_info.message
                + f" Diagnostic fallback sampled {frames_sampled} frame(s); "
                "its counts are not shown as attendance truth."
            )

        case: ComplianceCase | None = None

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
                        "trusted_sample_ratio": round(trusted_ratio, 3),
                    },
                )
            )

        elif (
            runtime_authoritative
            and overall_pct is not None
            and overall_pct >= mismatch_threshold_pct
            and persistence >= persistence_threshold
            and best_evidence
        ):
            _, frame, evidence_count, evidence_detections = best_evidence
            frame = anonymize_person_regions(frame, evidence_detections)
            case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
            evidence_id = f"EV-{uuid.uuid4().hex[:10].upper()}"
            evidence = persist_evidence(
                frame,
                self.evidence_root,
                self.index_path,
                evidence_id,
                {
                    "centre_id": centre_id,
                    "batch_id": batch_id,
                    "camera_id": camera_id,
                    "reported_attendance": reported_attendance,
                    "visual_occupancy": evidence_count,
                    "privacy_transform": "person_regions_blurred_before_central_retention",
                    "track_registration_seconds": attendance_registration_seconds,
                    "detector_backend": detector_info.backend,
                },
            )
            case = ComplianceCase(
                case_id=case_id,
                centre_id=centre_id,
                batch_id=batch_id,
                case_type="attendance_discrepancy",
                severity="high" if overall_pct >= 25 else "medium",
                summary=(
                    f"Reported attendance {reported_attendance}; privacy-preserving "
                    f"stable visual occupancy estimated at {estimated_internal}. Persistent "
                    f"mismatch across {persistence:.0%} of eligible observations."
                ),
                reported_attendance=reported_attendance,
                visual_occupancy=estimated_internal,
                discrepancy_pct=round(overall_pct, 2),
                persistence_ratio=round(persistence, 3),
                details={
                    "camera_id": camera_id,
                    "trusted_sample_ratio": round(trusted_ratio, 3),
                    "track_confirmation_seconds": track_confirmation_seconds,
                    "attendance_registration_seconds": attendance_registration_seconds,
                    "track_grace_seconds": effective_grace_seconds,
                    "detector_backend": detector_info.backend,
                    "individual_identification": False,
                },
                evidence=[evidence],
            )

        if case is not None and case.case_type == "camera_integrity":
            decision = "camera_integrity_exception"
        elif not runtime_authoritative:
            decision = "detector_unavailable"
        elif case is not None and case.case_type == "attendance_discrepancy":
            decision = "attendance_exception"
        else:
            decision = "compliant"

        LOGGER.info(
            "Attendance completed sampled=%s detector=%s mode=%s failures=%s "
            "authoritative=%s estimated=%s trusted_ratio=%.3f decision=%s",
            frames_sampled,
            detector_info.backend,
            detector_mode,
            detector_failures,
            runtime_authoritative,
            estimated,
            trusted_ratio,
            decision,
        )

        return ProcessSummary(
            centre_id=centre_id,
            batch_id=batch_id,
            reported_attendance=reported_attendance,
            estimated_occupancy=estimated,
            discrepancy_pct=round(overall_pct, 2) if overall_pct is not None else None,
            decision=decision,
            trusted_sample_ratio=round(trusted_ratio, 4),
            mismatch_persistence_ratio=round(persistence, 4),
            sample_every_seconds=float(sample_every_seconds),
            observations=observations,
            detector_backend=detector_info.backend,
            detector_mode=detector_mode,
            detector_authoritative=runtime_authoritative,
            detector_message=detector_message,
            frames_sampled=frames_sampled,
            detector_failures=detector_failures,
            case=case,
        )
