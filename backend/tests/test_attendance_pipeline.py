import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.person_detector import Detection, DetectorInfo
from app.services.video_pipeline import VideoCompliancePipeline


class ScriptedThreePersonDetector:
    info = DetectorInfo(
        backend="scripted-test",
        mode="primary",
        authoritative=True,
        message="Deterministic three-person regression detector",
    )

    def detect(self, frame):
        return [
            Detection(70, 80, 130, 250, 0.95),
            Detection(250, 70, 315, 250, 0.93),
            Detection(430, 85, 500, 255, 0.91),
        ]


class FallbackThreePersonDetector(ScriptedThreePersonDetector):
    info = DetectorInfo(
        backend="fallback-test",
        mode="fallback",
        authoritative=False,
        message="Synthetic fallback detector",
    )


def _write_trustworthy_video(path: Path, frames: int = 120, fps: int = 10) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (640, 360),
    )
    assert writer.isOpened()
    try:
        for i in range(frames):
            frame = np.full((360, 640, 3), 155, dtype=np.uint8)
            for x in range(0, 640, 32):
                cv2.line(frame, (x, 0), (x, 360), (120, 120, 120), 1)
            for y in range(0, 360, 32):
                cv2.line(frame, (0, y), (640, y), (185, 185, 185), 1)
            shift = (i * 3) % 70
            cv2.rectangle(frame, (20 + shift, 20), (80 + shift, 55), (40, 120, 220), -1)
            writer.write(frame)
    finally:
        writer.release()


def test_full_attendance_pipeline_returns_known_nonzero_occupancy(tmp_path):
    video = tmp_path / "known-three-persons.avi"
    _write_trustworthy_video(video)

    pipeline = VideoCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "index.json",
        detector=ScriptedThreePersonDetector(),
    )
    result = pipeline.run(
        video_path=video,
        reported_attendance=3,
        centre_id="TEST-CENTRE",
        batch_id="TEST-BATCH",
        sample_every_seconds=0.2,
    )

    assert result.detector_authoritative is True
    assert result.detector_failures == 0
    assert result.frames_sampled >= 20
    assert result.estimated_occupancy == 3
    assert result.discrepancy_pct == 0
    assert result.case is None
    assert max(o.raw_count for o in result.observations) == 3


def test_fallback_detector_never_presents_zero_or_nonzero_as_attendance_truth(tmp_path):
    video = tmp_path / "known-three-persons.avi"
    _write_trustworthy_video(video)

    pipeline = VideoCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "index.json",
        detector=FallbackThreePersonDetector(),
    )
    result = pipeline.run(
        video_path=video,
        reported_attendance=3,
        centre_id="TEST-CENTRE",
        batch_id="TEST-BATCH",
        sample_every_seconds=0.2,
    )

    assert result.detector_authoritative is False
    assert result.detector_mode == "fallback"
    assert result.estimated_occupancy is None
    assert result.discrepancy_pct is None
    assert result.case is None
    assert "fallback" in result.detector_message.lower()


@pytest.mark.real_video
def test_real_attendance_clip_if_configured(tmp_path):
    """Local launch gate for the real demo clip.

    Run with:
      KAUSHALWATCH_REAL_ATTENDANCE_CLIP=<path>
      KAUSHALWATCH_REAL_ATTENDANCE_MIN=2
      KAUSHALWATCH_REAL_ATTENDANCE_MAX=4
      pytest -q backend/tests/test_attendance_pipeline.py -m real_video
    """

    clip = os.getenv("KAUSHALWATCH_REAL_ATTENDANCE_CLIP")
    if not clip:
        pytest.skip("KAUSHALWATCH_REAL_ATTENDANCE_CLIP not configured")

    path = Path(clip)
    if not path.exists():
        pytest.fail(f"Configured real attendance clip does not exist: {path}")

    expected_min = int(os.getenv("KAUSHALWATCH_REAL_ATTENDANCE_MIN", "2"))
    expected_max = int(os.getenv("KAUSHALWATCH_REAL_ATTENDANCE_MAX", "4"))

    pipeline = VideoCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "index.json",
    )
    result = pipeline.run(
        video_path=path,
        reported_attendance=expected_max,
        centre_id="REAL-DEMO",
        batch_id="REAL-DEMO",
        sample_every_seconds=0.2,
    )

    assert result.detector_authoritative, result.detector_message
    assert result.detector_failures == 0, result.detector_message
    assert result.estimated_occupancy is not None
    assert expected_min <= result.estimated_occupancy <= expected_max, (
        f"Real-video occupancy {result.estimated_occupancy} outside "
        f"expected range {expected_min}..{expected_max}; "
        f"detector={result.detector_backend} sampled={result.frames_sampled}"
    )
