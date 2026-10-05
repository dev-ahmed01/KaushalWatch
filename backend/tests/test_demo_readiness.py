import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.check_demo_readiness import (
    check_operability_roi,
    check_operability_window,
    final_mode_checks,
    inspect_video,
    required_cache_labels,
)


def test_inspect_video_reports_readable_metadata(tmp_path):
    video = tmp_path / "demo.avi"
    writer = cv2.VideoWriter(
        str(video),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for _ in range(5):
            writer.write(np.full((48, 64, 3), 120, dtype=np.uint8))
    finally:
        writer.release()

    ok, note, metadata = inspect_video(video)
    assert ok is True
    assert note == "ok"
    assert metadata["width"] == 64
    assert metadata["height"] == 48
    assert metadata["frame_count"] == 5
    assert metadata["fps"] > 0


def test_operability_roi_must_fit_video():
    scenario = {
        "operability_roi": {"x1": 10, "y1": 10, "x2": 80, "y2": 40}
    }
    ok, note = check_operability_roi(scenario, width=64, height=48)
    assert ok is False
    assert "exceeds video dimensions" in note


def test_operability_window_must_fit_video_duration():
    scenario = {
        "operability_window": {"start_sec": 14.0, "end_sec": 33.0}
    }
    ok, note = check_operability_window(scenario, duration_seconds=32.5)
    assert ok is False
    assert "exceeds video duration" in note


def test_operability_window_accepts_stable_subclip():
    scenario = {
        "operability_window": {"start_sec": 14.0, "end_sec": 33.0}
    }
    ok, note = check_operability_window(scenario, duration_seconds=33.27)
    assert ok is True
    assert "14.000-33.000s" in note


def test_final_mode_rejects_example_assets_and_fallback_detector(tmp_path):
    scenario = {
        "status": "EXAMPLE SCENARIO",
        "events_to_record": [],
        "operability_roi": {
            "x1": 0,
            "y1": 0,
            "x2": 10,
            "y2": 10,
            "note": "Replace these coordinates after framing the final camera.",
        },
        "operability_window": {
            "start_sec": 0,
            "end_sec": 10,
            "note": "Replace these timestamps after reviewing the final clip.",
        },
    }
    checks = final_mode_checks(
        scenario,
        scenario_path=tmp_path / "final-demo.example.json",
        cache_path=tmp_path / "equipment.example.json",
        detector="hog",
    )
    by_name = {name: ok for name, ok, _ in checks}

    assert by_name["final_scenario_not_example"] is False
    assert by_name["final_equipment_cache_not_example"] is False
    assert by_name["final_detector_openvino"] is False
    assert by_name["final_scenario_event_coverage"] is False
    assert by_name["final_operability_roi_frozen"] is False
    assert by_name["final_operability_window_frozen"] is False


def test_final_mode_accepts_frozen_scenario(tmp_path):
    scenario = {
        "status": "FINAL CONTROLLED DEMO",
        "events_to_record": [
            {"event": "baseline"},
            {"event": "attendance_discrepancy"},
            {"event": "infrastructure_discrepancy"},
            {"event": "operability_proxy"},
            {"event": "camera_integrity"},
            {"event": "offline_sync"},
            {"event": "duplicate_evidence"},
        ],
        "operability_roi": {
            "x1": 10,
            "y1": 10,
            "x2": 100,
            "y2": 80,
            "note": "Frozen after final camera framing.",
        },
        "operability_window": {
            "start_sec": 14.0,
            "end_sec": 33.0,
            "note": "Frozen after reviewing the final clip.",
        },
    }
    checks = final_mode_checks(
        scenario,
        scenario_path=tmp_path / "final-demo.json",
        cache_path=tmp_path / "final-demo-equipment.json",
        detector="openvino",
    )
    assert all(ok for _, ok, _ in checks)


def test_officer_only_manifest_items_do_not_require_detector_cache_entries():
    manifest = {
        "items": [
            {"id": "training_panel", "verification_tier": "camera_verifiable"},
            {"id": "drill_machine", "verification_tier": "camera_partially_verifiable"},
            {"id": "multimeter", "verification_tier": "officer_verification_required"},
        ]
    }
    assert required_cache_labels(manifest) == {"training_panel", "drill_machine"}
