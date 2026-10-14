"""Synthetic camera-usability replay tests — never real-world accuracy evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation import camera_evidence_holdout as c


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(path, manifest):
    return {"path": str(path.relative_to(manifest.parent)), "sha256": _digest(path)}


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    manifest = tmp_path / "camera.json"
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({
        "status": "frozen_sih_candidate",
        "camera_trust": {
            "blur_threshold": 45.0, "dark_threshold": 28.0,
            "frozen_similarity": 0.9995, "scene_shift_threshold": 0.88,
            "trusted_score_threshold": 65.0,
        },
    }))
    monkeypatch.setattr(c, "active_profile_path", lambda: profile.resolve())

    def clip(n):
        path = tmp_path / f"cam_{n}.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (96, 72))
        assert writer.isOpened()
        labels = tmp_path / f"labels_{n}.csv"
        rng = np.random.default_rng(n + 41)
        with labels.open("w", newline="") as stream:
            rows = csv.writer(stream)
            try:
                for i in range(180):
                    category = (
                        1 if 30 <= i < 50 else
                        2 if 80 <= i < 100 else
                        3 if 130 <= i < 150 else 0
                    )
                    frame = rng.integers(35, 220, (72, 96, 3), dtype=np.uint8)
                    if category == 1:
                        frame[:] = 10
                    elif category == 2:
                        frame = cv2.GaussianBlur(frame, (9, 9), 4)
                    elif category == 3:
                        frame = np.roll(frame, 15, axis=1)
                    writer.write(frame)
                    rows.writerow([i + 1, category, 0, 0, 0])
            finally:
                writer.release()
        return path, labels

    provenance = {
        "source_origin": "synthetic unit test camera frames",
        "license_basis": "test-generated video with no human participants",
        "privacy_basis": "no identifiable persons in synthetic frames",
    }
    calibration_video, _ = clip(0)
    calibration = [{
        "scene_id": "CAL-001", "recording_id": "SESSION-CAL-001",
        "site_id": "SITE-CAL", "camera_id": "CAM-CAL",
        "video": _ref(calibration_video, manifest), **provenance,
    }]
    heldout = []
    for n in (1, 2):
        video, labels = clip(n)
        heldout.append({
            "scene_id": f"HOLD-{n:03d}",
            "recording_id": f"SESSION-HOLD-{n:03d}",
            "site_id": f"SITE-{n:03d}",
            "camera_id": f"CAM-{n:03d}",
            "video": _ref(video, manifest),
            "annotations": _ref(labels, manifest),
            "reviewer_id": f"REVIEWER-{n:03d}",
            "blinded_review": True,
            "previously_inspected": False,
            **provenance,
        })
    manifest.write_text(json.dumps({
        "schema_version": 1, "protocol_id": "CAMERA-CI-TEST-001",
        "status": "frozen", "fixture_only": True,
        "policy": dict(c.POLICY),
        "vision_profile": _ref(profile, manifest),
        "calibration": calibration, "heldout": heldout,
    }, indent=2))
    return manifest


def _edit(manifest, operation):
    d = json.loads(manifest.read_text())
    operation(d)
    manifest.write_text(json.dumps(d, indent=2))


def test_dataset_has_annotated_normal_and_three_event_types(frozen):
    data = c.load_protocol(frozen, allow_fixture=True)
    assert data["cameras"] == 2
    assert data["normal_seconds"] >= 15
    assert data["events"] == {1: 2, 2: 2, 3: 2}


def test_synthetic_replay_measures_release_camera_gate_without_qualifying(frozen):
    report = c.evaluate(frozen, test_fixture=True)
    assert report["status"] == "synthetic_fixture_not_qualifying"
    assert report["qualified"] is False
    assert report["support"]["recordings"] == 2
    assert report["support"]["independent_events"] == 6
    assert report["metrics"]["fresh_event_detection_recall"] <= 1
    assert report["metrics"]["normal_false_alarm_episodes_per_hour"] >= 0
    assert report["provenance"]["prediction_source"] == "released_assess_camera_pipeline"
    assert "tampering" in " ".join(report["limitations"])


def test_synthetic_video_is_never_accepted_as_real_heldout(frozen):
    with pytest.raises(ValueError, match="Fixtures"):
        c.evaluate(frozen)


def test_manifest_and_annotations_must_be_immutable(frozen):
    contents = c.load_protocol(frozen, allow_fixture=True)
    target = contents["heldout"][0]["annotations"]
    with target.open("a") as stream:
        stream.write("181,0,0,0,0\n")
    with pytest.raises(ValueError, match="SHA-256"):
        c.load_protocol(frozen, allow_fixture=True)


def test_calibration_video_or_recording_leakage_refused(frozen):
    _edit(frozen, lambda d: d["heldout"][0].update({
        "recording_id": d["calibration"][0]["recording_id"],
    }))
    with pytest.raises(ValueError, match="leakage"):
        c.load_protocol(frozen, allow_fixture=True)


def test_source_video_reused_across_scenes_refused(frozen):
    _edit(frozen, lambda d: d["heldout"][1].update({
        "video": d["heldout"][0]["video"],
    }))
    with pytest.raises(ValueError, match="leakage"):
        c.load_protocol(frozen, allow_fixture=True)


def test_each_frame_must_have_exact_ordered_annotation(frozen):
    raw = json.loads(frozen.read_text())
    labels = frozen.parent / raw["heldout"][0]["annotations"]["path"]
    lines = labels.read_text().splitlines()
    lines[12] = "15,0,0,0,0"
    labels.write_text("\n".join(lines) + "\n")
    raw["heldout"][0]["annotations"]["sha256"] = _digest(labels)
    frozen.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="in 1-based order"):
        c.load_protocol(frozen, allow_fixture=True)


def test_unblinded_inspected_and_policy_drift_refused(frozen):
    _edit(frozen, lambda d: d["heldout"][0].update({"previously_inspected": True}))
    with pytest.raises(ValueError, match="untouched"):
        c.load_protocol(frozen, allow_fixture=True)


def test_threshold_loosening_is_refused(frozen):
    _edit(frozen, lambda d: d["policy"].update({"max_normal_false_untrusted_rate": 1.0}))
    with pytest.raises(ValueError, match="review-locked"):
        c.load_protocol(frozen, allow_fixture=True)


def test_missing_event_support_is_refused_even_with_normal_frames(frozen):
    raw = json.loads(frozen.read_text())
    for scene in raw["heldout"]:
        labels = frozen.parent / scene["annotations"]["path"]
        contents = labels.read_text().replace(",3,0,0,0", ",0,0,0,0")
        labels.write_text(contents)
        scene["annotations"]["sha256"] = _digest(labels)
    frozen.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="event support"):
        c.load_protocol(frozen, allow_fixture=True)


def test_full_camera_manifest_blocks_prior_inspected_day4(frozen):
    raw = json.loads(frozen.read_text())
    raw["fixture_only"] = False
    raw["heldout"][0]["recording_id"] = "UHCTD_DAY4_CAM_B"
    for scene in raw["calibration"] + raw["heldout"]:
        scene.update({
            "source_origin": "independently collected indoor camera sequence",
            "license_basis": "written research evaluation permission recorded",
            "privacy_basis": "restricted lawful footage held locally for scoring",
        })
    frozen.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Previously inspected UHCTD Day 3/Day 4"):
        c.load_protocol(frozen)


def test_cli_missing_inputs_fails_closed(tmp_path, monkeypatch):
    import argparse
    assert not (tmp_path / "never-created.json").exists()
    with pytest.raises(ValueError, match="missing"):
        c.load_protocol(tmp_path / "never-created.json")
