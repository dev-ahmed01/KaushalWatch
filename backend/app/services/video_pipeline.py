from __future__ import annotations
from collections import Counter
from pathlib import Path
import uuid

import cv2
import numpy as np

from app.models import AttendanceObservation, ComplianceCase, ProcessSummary
from app.services.camera_trust import assess_camera
from app.services.compliance_cases import build_camera_integrity_case
from app.services.person_detector import build_person_detector
from app.services.occupancy import OccupancySmoother, discrepancy_pct
from app.services.evidence import persist_evidence


class VideoCompliancePipeline:
    def __init__(self, evidence_root: Path, index_path: Path):
        self.detector = build_person_detector()
        self.evidence_root = evidence_root
        self.index_path = index_path

    def run(
        self,
        video_path: Path,
        reported_attendance: int,
        centre_id: str,
        batch_id: str,
        camera_id: str = "CAM-01",
        sample_every_seconds: float = 1.0,
        mismatch_threshold_pct: float = 15.0,
        persistence_threshold: float = 0.6,
        minimum_trusted_ratio: float = 0.5,
    ) -> ProcessSummary:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, int(round(fps * sample_every_seconds)))
        smoother = OccupancySmoother(window=5)

        observations: list[AttendanceObservation] = []
        mismatch_flags: list[bool] = []
        trust_flags: list[bool] = []
        trust_reason_counter: Counter[str] = Counter()

        prev_frame = None
        reference_frame = None
        best_evidence: tuple[float, np.ndarray, int] | None = None
        worst_camera_evidence: tuple[float, np.ndarray, list[str]] | None = None

        i = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if reference_frame is None:
                    reference_frame = frame.copy()
                if i % step != 0:
                    i += 1
                    continue

                sec = i / fps
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
                    worst_camera_evidence = (trust.score, frame.copy(), list(trust.reasons))

                count = len(self.detector.detect(frame)) if trust.trusted else 0
                smooth = smoother.update(count)
                d_pct = discrepancy_pct(reported_attendance, smooth)
                is_mismatch = trust.trusted and d_pct >= mismatch_threshold_pct

                observations.append(
                    AttendanceObservation(
                        second=round(sec, 2),
                        raw_count=count,
                        smoothed_count=smooth,
                        camera_trust=trust.score,
                    )
                )
                mismatch_flags.append(is_mismatch)

                if is_mismatch and (
                    best_evidence is None or d_pct > best_evidence[0]
                ):
                    best_evidence = (d_pct, frame.copy(), smooth)

                prev_frame = frame.copy()
                i += 1
        finally:
            cap.release()

        if not observations:
            raise ValueError("No usable frames were sampled from the video")

        trusted_ratio = sum(trust_flags) / len(trust_flags) if trust_flags else 0.0
        trusted_counts = [
            o.smoothed_count
            for o, is_trusted in zip(observations, trust_flags)
            if is_trusted
        ]
        estimated = int(np.median(trusted_counts)) if trusted_counts else 0
        overall_pct = discrepancy_pct(reported_attendance, estimated)
        persistence = sum(mismatch_flags) / len(mismatch_flags)

        case: ComplianceCase | None = None

        # Integrity takes precedence: do not issue attendance conclusions from a mostly-bad feed.
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
            overall_pct >= mismatch_threshold_pct
            and persistence >= persistence_threshold
            and best_evidence
        ):
            _, frame, evidence_count = best_evidence
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
                    f"visual occupancy estimated at {estimated}. Persistent mismatch "
                    f"across {persistence:.0%} of sampled observations."
                ),
                reported_attendance=reported_attendance,
                visual_occupancy=estimated,
                discrepancy_pct=round(overall_pct, 2),
                persistence_ratio=round(persistence, 3),
                details={
                    "camera_id": camera_id,
                    "trusted_sample_ratio": round(trusted_ratio, 3),
                },
                evidence=[evidence],
            )

        return ProcessSummary(
            centre_id=centre_id,
            batch_id=batch_id,
            reported_attendance=reported_attendance,
            estimated_occupancy=estimated,
            discrepancy_pct=round(overall_pct, 2),
            observations=observations,
            case=case,
        )
