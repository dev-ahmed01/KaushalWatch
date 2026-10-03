import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.evidence import persist_evidence
from app.services.video_pipeline import VideoCompliancePipeline


def _write_dark_video(path: Path, frames: int = 30) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10,
        (160, 120),
    )
    assert writer.isOpened()
    try:
        for _ in range(frames):
            writer.write(np.zeros((120, 160, 3), dtype=np.uint8))
    finally:
        writer.release()


def test_camera_integrity_case_preempts_attendance_on_bad_feed(tmp_path):
    video = tmp_path / "covered-camera.avi"
    _write_dark_video(video)

    pipeline = VideoCompliancePipeline(
        tmp_path / "evidence",
        tmp_path / "evidence-index.json",
    )
    result = pipeline.run(
        video_path=video,
        reported_attendance=12,
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-TAMPER",
        sample_every_seconds=0.5,
    )

    assert result.case is not None
    assert result.case.case_type == "camera_integrity"
    assert "suspended" in result.case.summary.lower()
    assert len(result.case.evidence) == 1
    assert result.case.evidence[0].metadata["case_type"] == "camera_integrity"


def test_identical_evidence_is_flagged_as_duplicate(tmp_path):
    evidence_dir = tmp_path / "evidence"
    index = tmp_path / "evidence-index.json"
    frame = np.zeros((100, 140, 3), dtype=np.uint8)
    cv2.rectangle(frame, (20, 20), (90, 80), (220, 140, 30), -1)

    first = persist_evidence(
        frame,
        evidence_dir,
        index,
        "EV-FIRST",
        {"case_type": "test"},
    )
    second = persist_evidence(
        frame.copy(),
        evidence_dir,
        index,
        "EV-SECOND",
        {"case_type": "test"},
    )

    assert first.duplicate_of is None
    assert second.duplicate_of == "EV-FIRST"
