from __future__ import annotations

from pathlib import Path
import uuid

import cv2

from app.models import ComplianceCase
from app.services.compliance_cases import build_infrastructure_case
from app.services.evidence import persist_evidence
from app.services.infrastructure import aggregate_cached_observations, compare_manifest
from app.services.operability import apparent_motion_state
from app.services.privacy import anonymize_person_regions


class InfrastructureCompliancePipeline:
    """Build one evidence-backed infrastructure case from video + detector observations.

    Detector observations may come from a live detector or a precomputed cache. The core
    case/evidence workflow does not care which adapter produced them.
    """

    def __init__(self, evidence_root: Path, index_path: Path, privacy_detector=None):
        self.evidence_root = evidence_root
        self.index_path = index_path
        self.privacy_detector = privacy_detector

    def run(
        self,
        video_path: Path,
        manifest: dict,
        detection_rows: list[dict],
        centre_id: str,
        batch_id: str,
        camera_id: str,
        operability_item_id: str | None = None,
        operability_roi: tuple[int, int, int, int] | None = None,
        operability_threshold: float = 0.8,
        max_operability_frames: int = 30,
    ) -> ComplianceCase | None:
        observed = aggregate_cached_observations(detection_rows)
        results = compare_manifest(manifest, observed)
        case = build_infrastructure_case(
            centre_id=centre_id,
            batch_id=batch_id,
            job_role=manifest.get("job_role", "Unknown job role"),
            results=results,
        )
        if not case:
            return None

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_seconds = frame_count / fps if frame_count > 0 else 0.0
        sample_seconds = sorted(float(row.get("second", 0.0)) for row in detection_rows)
        valid_sample_seconds = [
            second for second in sample_seconds
            if duration_seconds <= 0 or second < duration_seconds
        ]
        if valid_sample_seconds:
            evidence_second = valid_sample_seconds[len(valid_sample_seconds) // 2]
        else:
            evidence_second = 0.0

        cap.set(cv2.CAP_PROP_POS_MSEC, evidence_second * 1000.0)
        ok, evidence_frame = cap.read()
        if not ok:
            cap.release()
            raise ValueError("Could not read evidence frame from infrastructure video")

        operability = None
        if operability_item_id and operability_roi:
            frames = []
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            step = max(1, int(fps / 2))
            i = 0
            while len(frames) < max_operability_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                if i % step == 0:
                    frames.append(frame)
                i += 1
            state, activity_score = apparent_motion_state(
                frames,
                operability_roi,
                threshold=operability_threshold,
            )
            operability = {
                "item_id": operability_item_id,
                "state": state,
                "activity_score": round(activity_score, 4),
                "method": "roi_motion_proxy",
                "interpretation": (
                    "Visual activity proxy only; not a mechanical/electrical health diagnosis."
                ),
            }

        cap.release()

        privacy_transform = "not_applied"
        if self.privacy_detector is not None:
            person_detections = self.privacy_detector.detect(evidence_frame)
            if person_detections:
                evidence_frame = anonymize_person_regions(evidence_frame, person_detections)
                privacy_transform = "person_regions_blurred_before_central_retention"
            else:
                privacy_transform = "no_person_regions_detected"

        evidence_id = f"EV-{uuid.uuid4().hex[:10].upper()}"
        evidence = persist_evidence(
            evidence_frame,
            self.evidence_root,
            self.index_path,
            evidence_id,
            {
                "centre_id": centre_id,
                "batch_id": batch_id,
                "camera_id": camera_id,
                "case_type": "infrastructure_compliance",
                "job_role": manifest.get("job_role"),
                "evidence_second": evidence_second,
                "observation_source": "cached_or_live_detector_adapter",
                "privacy_transform": privacy_transform,
            },
        )

        case.evidence.append(evidence)
        case.details["camera_id"] = camera_id
        case.details["observation_source"] = "detector_adapter"
        case.details["evidence_second"] = evidence_second
        if operability is not None:
            case.details["apparent_operability"] = operability

        if evidence.duplicate_of:
            case.details["evidence_integrity"] = {
                "possible_duplicate": True,
                "duplicate_of": evidence.duplicate_of,
            }
        else:
            case.details["evidence_integrity"] = {"possible_duplicate": False}

        return case
