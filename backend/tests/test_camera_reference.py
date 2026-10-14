"""No reviewed image data is committed; use synthetic reference JPEG/PNG."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.camera_reference import load_reviewed_reference
from app.services.camera_trust import assess_camera


def _manifest(tmp_path: Path):
    scene = np.full((120, 160, 3), 125, dtype=np.uint8)
    cv2.rectangle(scene, (20, 20), (105, 95), (220, 220, 220), 3)
    night = cv2.convertScaleAbs(scene, alpha=0.45)
    rows = []
    for ident, mode, image in (
        ("CAM1-DAY-R1", "day", scene), ("CAM1-NIGHT-R1", "night", night)
    ):
        path = tmp_path / (mode + ".png")
        assert cv2.imwrite(str(path), image)
        rows.append({
            "id": ident,
            "mode": mode,
            "image_path": path.name,
            "approved": True,
            "reviewed_by": "synthetic-test-reviewer",
            "reviewed_at": "2026-10-09",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    manifest = tmp_path / "manifest.json"
    doc = {"version": 1, "camera_id": "CAM1", "references": rows}
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    return manifest, doc, scene, night


def test_selects_only_explicit_matching_approved_reference(tmp_path):
    manifest, _doc, day, night = _manifest(tmp_path)
    day_state = load_reviewed_reference(manifest, camera_id="CAM1", mode="day")
    night_state = load_reviewed_reference(manifest, camera_id="CAM1", mode="night")
    assert day_state.reference_id == "CAM1-DAY-R1"
    assert night_state.reference_id == "CAM1-NIGHT-R1"
    assert not np.array_equal(day_state.reference_frame, night_state.reference_frame)
    result = assess_camera(night, state=night_state)
    assert result.reference_status == "REVIEWED_REFERENCE"
    assert result.reference_id == "CAM1-NIGHT-R1"
    assert result.camera_status == "USABLE"
    # Running a day image does not silently switch the manually selected mode.
    assert night_state.reference_mode == "night"


def test_rejects_reference_integrity_violation(tmp_path):
    manifest, _doc, *_ = _manifest(tmp_path)
    (tmp_path / "night.png").write_bytes(b"tampered image")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_reviewed_reference(manifest, camera_id="CAM1", mode="night")


def test_rejects_unknown_mode_and_wrong_camera(tmp_path):
    manifest, doc, *_ = _manifest(tmp_path)
    with pytest.raises(ValueError, match="Exactly one"):
        load_reviewed_reference(manifest, camera_id="CAM1", mode="infrared")
    with pytest.raises(ValueError, match="camera mismatch"):
        load_reviewed_reference(manifest, camera_id="CAM2", mode="day")
    doc["references"][0]["approved"] = False
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="approval"):
        load_reviewed_reference(manifest, camera_id="CAM1", mode="day")


def test_no_auto_enrollment_without_manifest():
    frame = np.full((90, 120, 3), 120, dtype=np.uint8)
    from app.services.camera_trust import CameraTrustState
    result = assess_camera(frame, state=CameraTrustState())
    assert result.reference_status == "UNVERIFIED_INITIAL_FRAME"


def test_different_camera_resolution_cannot_use_unrelated_reference(tmp_path):
    manifest, doc, *_ = _manifest(tmp_path)
    state = load_reviewed_reference(manifest, camera_id="CAM1", mode="day")
    with pytest.raises(ValueError, match="resolution"):
        assess_camera(np.zeros((60, 80, 3), dtype=np.uint8), state=state)
