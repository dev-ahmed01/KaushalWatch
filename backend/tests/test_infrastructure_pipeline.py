import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.infrastructure_pipeline import InfrastructureCompliancePipeline
from app.services.person_detector import DetectorInfo


class NonAuthoritativePrivacyDetector:
    info = DetectorInfo(
        backend="test-fallback",
        mode="fallback",
        authoritative=False,
        message="test fallback",
    )

    def detect(self, frame):
        raise AssertionError("Non-authoritative privacy detector should not be trusted")


def _write_video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10,
        (160, 120),
    )
    for i in range(40):
        frame = np.full((120, 160, 3), 80, dtype=np.uint8)
        x = 20 + (i % 20)
        frame[40:70, x:x+25] = 220
        writer.write(frame)
    writer.release()


def _write_cut_video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10,
        (160, 120),
    )
    for i in range(60):
        frame = np.full((120, 160, 3), 80, dtype=np.uint8)
        if i < 30:
            level = 220 if (i // 5) % 2 == 0 else 30
            frame[20:100, 0:100] = level
        else:
            frame[20:100, 0:100] = 120
        writer.write(frame)
    writer.release()


def test_pipeline_persists_case_evidence_and_operability(tmp_path):
    video = tmp_path / "demo.avi"
    _write_video(video)
    manifest = {
        "job_role": "Construction Electrician",
        "items": [
            {
                "id": "training_panel",
                "label": "Training Panel",
                "required": 4,
                "verification_tier": "camera_verifiable",
            },
            {
                "id": "drill_machine",
                "label": "Drill Machine",
                "required": 1,
                "verification_tier": "camera_partially_verifiable",
            },
        ],
    }
    detections = [
        {
            "second": 0,
            "detections": [
                {"label": "training_panel", "count": 3, "confidence": 0.9},
                {"label": "drill_machine", "count": 1, "confidence": 0.9},
            ],
        },
        {
            "second": 2,
            "detections": [
                {"label": "training_panel", "count": 3, "confidence": 0.9},
                {"label": "drill_machine", "count": 1, "confidence": 0.9},
            ],
        },
    ]

    pipeline = InfrastructureCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "evidence-index.json",
    )
    case = pipeline.run(
        video_path=video,
        manifest=manifest,
        detection_rows=detections,
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-02",
        operability_item_id="drill_machine",
        operability_roi=(0, 20, 100, 100),
        operability_threshold=0.1,
    )

    assert case is not None
    assert case.case_type == "infrastructure_compliance"
    assert len(case.evidence) == 1
    assert Path(case.evidence[0].frame_path).exists()
    assert case.details["apparent_operability"]["item_id"] == "drill_machine"
    assert case.details["apparent_operability"]["state"] in {
        "APPARENTLY_ACTIVE",
        "APPARENTLY_INACTIVE",
        "UNCERTAIN",
    }
    assert case.details["evidence_integrity"]["possible_duplicate"] is False


def test_pipeline_limits_operability_motion_to_configured_window(tmp_path):
    video = tmp_path / "cut-demo.avi"
    _write_cut_video(video)
    manifest = {
        "job_role": "Construction Electrician",
        "items": [
            {
                "id": "training_panel",
                "label": "Training Panel",
                "required": 4,
                "verification_tier": "camera_verifiable",
            }
        ],
    }
    detections = [
        {
            "second": 1,
            "detections": [
                {"label": "training_panel", "count": 3, "confidence": 0.9},
            ],
        },
        {
            "second": 4,
            "detections": [
                {"label": "training_panel", "count": 3, "confidence": 0.9},
            ],
        },
    ]

    pipeline = InfrastructureCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "evidence-index.json",
    )
    case = pipeline.run(
        video_path=video,
        manifest=manifest,
        detection_rows=detections,
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-02",
        operability_item_id="training_panel",
        operability_roi=(0, 20, 100, 100),
        operability_threshold=0.1,
        operability_window=(3.0, 5.8),
    )

    assert case is not None
    operability = case.details["apparent_operability"]
    assert operability["state"] == "APPARENTLY_INACTIVE"
    assert operability["analysis_window"] == {
        "start_sec": 3.0,
        "end_sec": 5.8,
    }
    assert 3 <= operability["frames_sampled"] <= 30


def test_pipeline_clamps_evidence_to_available_video(tmp_path):
    video = tmp_path / "short.avi"
    _write_video(video)
    manifest = {
        "job_role": "Construction Electrician - LV",
        "items": [
            {
                "id": "training_panel",
                "label": "Training Panel",
                "required": 4,
                "verification_tier": "camera_verifiable",
            }
        ],
    }
    detections = [
        {
            "second": 10,
            "detections": [
                {"label": "training_panel", "count": 3, "confidence": 0.9},
            ],
        },
        {
            "second": 20,
            "detections": [
                {"label": "training_panel", "count": 3, "confidence": 0.9},
            ],
        },
    ]

    pipeline = InfrastructureCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "evidence-index.json",
    )
    case = pipeline.run(
        video_path=video,
        manifest=manifest,
        detection_rows=detections,
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-02",
    )
    assert case is not None
    assert case.details["evidence_second"] == 0.0
    assert len(case.evidence) == 1



def test_infrastructure_evidence_uses_full_frame_privacy_fallback(tmp_path):
    video = tmp_path / "privacy-demo.avi"
    _write_video(video)
    manifest = {
        "job_role": "Construction Electrician",
        "items": [
            {
                "id": "training_panel",
                "label": "Training Panel",
                "required": 4,
                "verification_tier": "camera_verifiable",
            }
        ],
    }
    detections = [
        {
            "second": 0,
            "detections": [
                {"label": "training_panel", "count": 2, "confidence": 0.9},
            ],
        }
    ]

    pipeline = InfrastructureCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "evidence-index.json",
        privacy_detector=NonAuthoritativePrivacyDetector(),
    )
    case = pipeline.run(
        video_path=video,
        manifest=manifest,
        detection_rows=detections,
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-02",
    )

    assert case is not None
    assert (
        case.evidence[0].metadata["privacy_transform"]
        == "full_frame_blur_non_authoritative_privacy_detector"
    )
