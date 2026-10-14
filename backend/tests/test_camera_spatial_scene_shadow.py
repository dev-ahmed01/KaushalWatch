"""Shadow-only spatial background tests; no restricted video is used."""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

from app.services.camera_spatial_scene_shadow import (
    SpatialSceneShadow, spatial_metrics,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from diagnose_uhctd_spatial_scene import run  # noqa: E402


def scene():
    rng = np.random.default_rng(20261009)
    return rng.integers(70, 180, (180, 240, 3), dtype=np.uint8)


def test_global_viewpoint_translation_spreads_over_image():
    base = scene()
    moved = cv2.warpAffine(
        base, np.float32([[1, 0, 30], [0, 1, 10]]),
        (240, 180), borderMode=cv2.BORDER_REFLECT,
    )
    m = spatial_metrics(base, moved)
    assert m["evidence_status"] == "SUFFICIENT_TILES"
    assert m["changed_fraction"] >= .65
    assert m["changed_quadrants"] >= 3
    probe = SpatialSceneShadow()
    for _ in range(35):
        probe.observe(base, 1/3)
    for _ in range(39):
        result = probe.observe(moved, 1/3)
    assert result["review_65"]


def test_two_foreground_pedestrians_are_not_camera_displacement():
    base = scene()
    people = base.copy()
    cv2.rectangle(people, (60, 35), (105, 160), (15, 20, 205), -1)
    cv2.rectangle(people, (130, 20), (180, 170), (15, 20, 205), -1)
    m = spatial_metrics(base, people)
    assert m["evidence_status"] == "SUFFICIENT_TILES"
    assert m["changed_fraction"] < .45
    probe = SpatialSceneShadow()
    for _ in range(35):
        probe.observe(base, 1/3)
    for _ in range(80):
        result = probe.observe(people, 1/3)
        assert not result["review_45"]


def test_global_brightness_change_does_not_move_background():
    base = scene()
    brighter = cv2.convertScaleAbs(base, alpha=1.0, beta=18)
    m = spatial_metrics(base, brighter)
    assert m["changed_fraction"] < .1
    assert m["changed_quadrants"] == 0


def test_unsupported_blank_scene_returns_unknown_not_false_negative():
    featureless = np.full((180, 240, 3), 65, dtype=np.uint8)
    metrics = spatial_metrics(featureless, featureless)
    assert metrics["evidence_status"] == "UNKNOWN_LOW_TEXTURE"
    probe = SpatialSceneShadow()
    for _ in range(80):
        observation = probe.observe(featureless, 1/3)
    assert observation["evidence_status"] == "UNKNOWN_LOW_TEXTURE"
    assert not any(observation[f"review_{n}"] for n in (45, 55, 65))


def test_short_synthetic_spatial_survey_creates_reports_only(tmp_path):
    video = tmp_path / "synthetic.avi"
    labels = tmp_path / "annotations.csv"
    writer = cv2.VideoWriter(
        str(video), cv2.VideoWriter_fourcc(*"MJPG"), 3, (240, 180)
    )
    assert writer.isOpened()
    base = scene()
    displaced = np.roll(base, 34, axis=1)
    index = 0
    kinds = [1, 2, 3] * 2
    with labels.open("w", newline="") as stream:
        csv_writer = csv.writer(stream)
        try:
            for kind in kinds:
                for cls, n in ((0, 210), (kind, 120)):
                    for _ in range(n):
                        index += 1
                        writer.write(displaced if cls == 3 else base)
                        csv_writer.writerow([index, cls, "0.5", "0.1", "0"])
        finally:
            writer.release()
    result = run(
        video, labels, tmp_path / "results", events_per_class=1,
        normal_windows=2, normal_seconds=20.0, sample_seconds=1/3,
    )
    assert result["evaluation_status"].startswith("PHASE11_SPATIAL_SHADOW")
    assert len(result["spans"]) == 3
    assert result["comparisons"]["review_45"]["moved_events_total"] == 1
    assert sorted(p.suffix for p in (tmp_path / "results").iterdir()) == [
        ".csv", ".json"
    ]
