import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.compliance_cases import build_practical_activity_case
from app.services.person_detector import Detection, DetectorInfo
from app.services.practical_activity_pipeline import PracticalActivityPipeline, validate_work_zones, scale_work_zones


def test_validate_work_zones_accepts_in_bounds_cells():
    validate_work_zones(
        [
            {"zone_id": "work_zone_1", "x": 10, "y": 20, "w": 100, "h": 120},
            {"zone_id": "work_zone_2", "x": 200, "y": 30, "w": 80, "h": 90},
        ],
        width=640,
        height=480,
    )


def test_validate_work_zones_rejects_out_of_bounds_cell():
    with pytest.raises(ValueError, match="outside video bounds"):
        validate_work_zones(
            [{"zone_id": "work_zone_1", "x": 600, "y": 20, "w": 100, "h": 120}],
            width=640,
            height=480,
        )


def test_scale_work_zones_preserves_geometry_for_resized_same_scene():
    zones = [
        {"zone_id": "work_zone_1", "x": 100, "y": 200, "w": 400, "h": 300},
    ]
    scaled = scale_work_zones(
        zones,
        reference_width=1920,
        reference_height=1080,
        width=960,
        height=540,
    )

    assert scaled == [
        {"zone_id": "work_zone_1", "x": 50, "y": 100, "w": 200, "h": 150},
    ]
    assert zones[0]["x"] == 100


def test_scale_work_zones_rejects_different_camera_aspect_ratio():
    zones = [
        {"zone_id": "work_zone_1", "x": 100, "y": 200, "w": 400, "h": 300},
    ]

    with pytest.raises(ValueError, match="different aspect ratio"):
        scale_work_zones(
            zones,
            reference_width=1920,
            reference_height=1080,
            width=640,
            height=480,
        )


def test_practical_activity_case_created_when_authorization_absent():
    case = build_practical_activity_case(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-03",
        authorization="absent",
        practical_activity_fraction=0.77,
        active_work_cells=2,
    )

    assert case is not None
    assert case.case_type == "practical_activity_authorization"
    assert case.severity == "high"
    assert case.details["authorization"] == "absent"
    assert case.details["active_work_cells"] == 2
    assert case.details["individual_identification"] is False


def test_practical_activity_case_not_created_for_valid_authorization():
    case = build_practical_activity_case(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-03",
        authorization="valid",
        practical_activity_fraction=0.44,
        active_work_cells=1,
    )

    assert case is None


def test_unknown_authorization_requires_review_case():
    case = build_practical_activity_case(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-03",
        authorization="unknown",
        practical_activity_fraction=0.44,
        active_work_cells=1,
    )

    assert case is not None
    assert case.case_type == "practical_activity_authorization_review"
    assert case.severity == "medium"



class _AuthoritativeFakeDetector:
    info = DetectorInfo(
        backend="test_detector",
        mode="primary",
        authoritative=True,
        message="Authoritative test detector active.",
    )

    def detect(self, frame):
        return [Detection(x1=48, y1=28, x2=230, y2=172, confidence=0.99)]


def _write_practical_test_video(path: Path) -> None:
    width, height = 320, 180
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10.0,
        (width, height),
    )
    assert writer.isOpened()
    for index in range(30):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # High-frequency background avoids a false blur warning.
        for x in range(0, width, 20):
            cv2.line(frame, (x, 0), (x, height - 1), (55, 55, 55), 1)
        for y in range(0, height, 20):
            cv2.line(frame, (0, y), (width - 1, y), (55, 55, 55), 1)
        offset = (index * 5) % 80
        cv2.rectangle(frame, (80 + offset, 75), (115 + offset, 135), (235, 235, 235), -1)
        writer.write(frame)
    writer.release()


def test_practical_pipeline_uses_detector_abstraction_without_ultralytics(tmp_path):
    video = tmp_path / "practical.avi"
    _write_practical_test_video(video)
    pipeline = PracticalActivityPipeline(
        tmp_path / "evidence",
        tmp_path / "index.json",
        detector=_AuthoritativeFakeDetector(),
    )

    result = pipeline.run(
        video_path=video,
        zones=[{"zone_id": "work_zone_1", "x": 20, "y": 10, "w": 280, "h": 165}],
        authorization="valid",
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        camera_id="LAB-CAM-03",
        confirmation_seconds=0.0,
        registration_seconds=0.0,
        sample_every_seconds=0.1,
        activity_window_seconds=0.2,
        activity_required_ratio=0.25,
        motion_threshold=0.001,
    )

    assert result.detector_backend == "test_detector"
    assert result.detector_authoritative is True
    assert result.detector_failures == 0
    assert result.frames_processed > 0
    assert result.decision != "detector_unavailable"
