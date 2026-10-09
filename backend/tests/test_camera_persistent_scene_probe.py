"""Synthetic, shadow-only temporal change-point tests."""
import csv
import sys

import cv2
import numpy as np

from app.services.camera_persistent_scene_probe import PersistentSceneProbe

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from diagnose_uhctd_persistent_change import run  # noqa: E402


def scene():
    image = np.full((90, 120, 3), 130, dtype=np.uint8)
    cv2.rectangle(image, (15, 12), (95, 70), (230, 210, 90), 3)
    cv2.line(image, (1, 85), (118, 35), (20, 20, 20), 2)
    return image


def test_persistent_structural_displacement_requires_confirmed_duration():
    baseline = scene()
    displaced = np.roll(baseline, 45, axis=1)
    probe = PersistentSceneProbe()
    for _ in range(30):
        status = probe.observe(baseline, 1/3)
    assert status["signal"] == "WARMUP"
    early = [probe.observe(displaced, 1/3) for _ in range(18)]
    assert not any(item["persistent_review"] for item in early)
    later = [probe.observe(displaced, 1/3) for _ in range(30)]
    assert later[-1]["persistent_review"]
    assert later[-1]["signal"] == "PERSISTENT_SCENE_CHANGE_REVIEW"


def test_brief_foreground_occlusion_clears_without_false_review():
    baseline = scene()
    pedestrian = baseline.copy()
    cv2.rectangle(pedestrian, (10, 10), (55, 85), (20, 20, 20), -1)
    probe = PersistentSceneProbe()
    for _ in range(30):
        probe.observe(baseline, 1/3)
    for _ in range(20):
        assert not probe.observe(pedestrian, 1/3)["persistent_review"]
    for _ in range(40):
        assert not probe.observe(baseline, 1/3)["persistent_review"]


def test_additive_lighting_change_preserves_structure():
    baseline = scene()
    bright = cv2.convertScaleAbs(baseline, alpha=1.0, beta=22)
    probe = PersistentSceneProbe()
    for _ in range(30):
        probe.observe(baseline, 1/3)
    for _ in range(55):
        assert not probe.observe(bright, 1/3)["persistent_review"]


def test_persistent_probe_only_produces_review_not_camera_integrity():
    probe = PersistentSceneProbe()
    info = probe.observe(scene(), 1/3)
    assert "persistent_review" in info
    assert "tamper_suspected" not in info


def test_shadow_survey_outputs_without_private_frames(tmp_path):
    avi = tmp_path / "source.avi"
    labels = tmp_path / "labels.csv"
    writer = cv2.VideoWriter(
        str(avi), cv2.VideoWriter_fourcc(*"MJPG"), 3, (120, 90)
    )
    assert writer.isOpened()
    base = scene()
    changed = np.roll(base, 40, axis=1)
    # Four moved episodes, each with preceding 80 seconds of clean context,
    # plus 12 normal runs long enough to select across the recording.
    segments = []
    for _ in range(12):
        segments.extend([(0, 270), (3, 150)])
    frame_no = 0
    with labels.open("w", newline="") as output:
        csv_writer = csv.writer(output)
        try:
            for kind, count in segments:
                for _ in range(count):
                    frame_no += 1
                    writer.write(changed if kind else base)
                    csv_writer.writerow([frame_no, kind, "0.25", "0.1", "0"])
        finally:
            writer.release()
    results = run(avi, labels, tmp_path / "results", events_per_class=4,
                  normal_windows=4, sample_seconds=1/3)
    assert results["moved_events"] == 4
    assert results["normal_controls"] == 4
    assert len(list((tmp_path / "results").iterdir())) == 2
