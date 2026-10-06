import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

import app.main as app_main
from app.services.person_detector import DetectorInfo
from app.services.vision_profile import (
    build_vision_governance,
    load_vision_profile,
    validate_dataset_manifest,
    validate_vision_profile,
)


class MatchingDetector:
    confidence = 0.45
    tiled = True
    tile_overlap = 0.18
    tile_nms_iou = 0.45
    info = DetectorInfo(
        backend="openvino",
        mode="primary",
        authoritative=True,
        message="Matching test detector.",
    )


class DriftedDetector:
    confidence = 0.35
    tiled = False
    tile_overlap = 0.18
    tile_nms_iou = 0.45
    info = DetectorInfo(
        backend="openvino",
        mode="primary",
        authoritative=True,
        message="Drifted test detector.",
    )


def test_frozen_vision_profile_is_structurally_valid_and_files_exist():
    profile = load_vision_profile()

    assert profile["profile_id"] == "kaushalwatch-fixed-camera-v1"
    assert profile["status"] == "frozen_sih_candidate"
    assert validate_vision_profile(profile) == []
    assert profile["person_detection"]["confidence"] == 0.45
    assert profile["attendance"]["count_source"] == "confirmed"
    assert profile["attendance"]["smoother_window"] == 3
    assert profile["practical_activity"]["geometry_policy"] == "same_fixed_camera_view_only"
    assert profile["infrastructure"]["source_digest_required"] is True


def test_candidate_dataset_requires_calibration_and_held_out_splits():
    missing = validate_dataset_manifest({
        "dataset_id": "candidate-1",
        "status": "candidate",
        "purpose": ["attendance"],
        "camera": {"mode": "fixed_camera"},
        "splits": [
            {
                "split_id": "calibration",
                "role": "calibration",
                "annotations": {"attendance_counts_csv": "counts.csv"},
            }
        ],
    })

    assert missing["valid"] is False
    assert "candidate dataset requires a held-out split" in missing["errors"]

    valid = validate_dataset_manifest({
        "dataset_id": "candidate-2",
        "status": "candidate",
        "purpose": ["attendance"],
        "camera": {"mode": "fixed_camera"},
        "splits": [
            {
                "split_id": "calibration",
                "role": "calibration",
                "annotations": {"attendance_counts_csv": "cal.csv"},
            },
            {
                "split_id": "held-out",
                "role": "held_out",
                "annotations": {"attendance_counts_csv": "held.csv"},
            },
        ],
    })
    assert valid["valid"] is True
    assert valid["annotation_coverage"]["attendance"] is True


def test_runtime_alignment_detects_profile_match_and_drift(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE", "confirmed")
    monkeypatch.setenv("KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW", "3")

    aligned = build_vision_governance(detector=MatchingDetector())
    assert aligned["runtime_alignment"]["aligned"] is True
    assert all(aligned["runtime_alignment"]["checks"].values())
    assert aligned["engines"]["attendance"]["runtime_authoritative"] is True
    assert aligned["engines"]["infrastructure"]["reviewed_source_sha256"] == (
        "ba6ccded59533d0dbd0d21c8073d07e6dda7e7034ed85b10d0997e10ba7feb91"
    )

    drifted = build_vision_governance(detector=DriftedDetector())
    assert drifted["runtime_alignment"]["aligned"] is False
    assert drifted["runtime_alignment"]["checks"]["confidence"] is False
    assert drifted["runtime_alignment"]["checks"]["tiled"] is False


def test_governance_api_and_runtime_readiness_expose_profile(monkeypatch):
    monkeypatch.setattr(app_main.PIPELINE, "detector", MatchingDetector())
    monkeypatch.setattr(app_main.PRACTICAL_PIPELINE, "detector", MatchingDetector())
    monkeypatch.setenv("KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE", "confirmed")
    monkeypatch.setenv("KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW", "3")
    client = TestClient(app_main.app)

    governance = client.get("/api/vision/governance")
    assert governance.status_code == 200
    body = governance.json()
    assert body["profile"]["profile_id"] == "kaushalwatch-fixed-camera-v1"
    assert body["runtime_alignment"]["aligned"] is True
    assert body["engines"]["camera_trust"]["profiled"] is True
    assert any(
        row["dataset_id"] == "epfl-laboratory-camera0"
        for row in body["datasets"]
    )

    readiness = client.get("/api/runtime-readiness")
    assert readiness.status_code == 200
    assert readiness.json()["vision_profile"]["profile_id"] == "kaushalwatch-fixed-camera-v1"
    assert readiness.json()["runtime_alignment"]["aligned"] is True


def test_template_dataset_is_not_promotion_ready(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE", "confirmed")
    monkeypatch.setenv("KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW", "3")
    governance = build_vision_governance(detector=MatchingDetector())

    template = next(
        row for row in governance["datasets"]
        if row["dataset_id"] == "replace-with-dataset-id"
    )
    assert template["is_template"] is True
    assert governance["promotion_ready"]["candidate_dataset_registered"] is False
