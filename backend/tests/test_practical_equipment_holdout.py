"""Phase 2B evaluation fixtures use generated frames/caches, never people."""
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
from evaluation import practical_holdout as practical
from evaluation import equipment_holdout as equipment


def digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def pin(file: Path, manifest: Path) -> dict:
    return {"path": file.relative_to(manifest.parent).as_posix(), "sha256": digest(file)}


@pytest.fixture
def practical_fixture(tmp_path, monkeypatch):
    manifest = tmp_path / "practical-manifest.json"
    profile = tmp_path / "practical-profile.json"
    profile.write_text(json.dumps({
        "status": "frozen_sih_candidate",
        "person_detection": {"backend": "openvino", "confidence": 0.45, "tiled": True,
                             "tile_overlap": 0.18, "tile_nms_iou": 0.45},
        "attendance": {"track_confirmation_seconds": 1.0,
                       "registration_warmup_seconds": 2.0,
                       "track_grace_seconds": 0.8},
        "practical_activity": {"sample_every_seconds": 0.2, "activity_window_seconds": 1.0,
                               "activity_required_ratio": 0.6,
                               "motion_threshold": 0.02, "motion_pixel_delta": 18,
                               "minimum_zone_overlap": 0.15, "minimum_trusted_ratio": 0.5},
    }))
    monkeypatch.setattr(practical, "active_profile_path", lambda: profile.resolve())
    xml, bin_file = tmp_path/"detector.xml", tmp_path/"detector.bin"
    xml.write_text("synthetic descriptor")
    bin_file.write_bytes(b"synthetic bin file")

    def media(i):
        video = tmp_path / f"practical_{i}.avi"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (96, 72))
        assert writer.isOpened()
        for index in range(32):
            frame = np.full((72, 96, 3), 20 + i * 19 + index % 7, dtype=np.uint8)
            cv2.rectangle(frame, (10 + index % 7, 15), (30 + index % 7, 40),
                          (220, 220, 220), 1)
            writer.write(frame)
        writer.release()
        return video

    zones = tmp_path / "work-zones.json"
    zones.write_text(json.dumps({
        "reference_size": [96, 72],
        "zones": [{"zone_id": "training-cell", "x": 8, "y": 10, "w": 50, "h": 50}],
    }))
    provenance = {
        "source_origin": "synthetic generated CI evaluation frame",
        "license_basis": "test generated footage with no humans",
        "privacy_basis": "no identifiable people occur in fixture",
    }
    calibration = [{
        "recording_id": "CAL-RECORDING-001", "scene_id": "CAL-SCENE-001",
        "site_id": "CAL-SITE", "camera_id": "CAL-CAMERA",
        "video": pin(media(0), manifest), **provenance,
    }]
    cases = [(True, "absent"), (True, "valid"), (True, "unknown"),
             (False, "absent"), (False, "valid"), (False, "valid")]
    held = []
    for i, (activity, authorization) in enumerate(cases, 1):
        held.append({
            "recording_id": f"RECORDING-{i:03d}",
            "scene_id": f"SCENE-{i:03d}",
            "site_id": "SITE-A" if i <= 3 else "SITE-B",
            "camera_id": "CAM-A" if i <= 3 else "CAM-B",
            "video": pin(media(i), manifest), "work_zones": pin(zones, manifest),
            "reviewer_id": "INDEPENDENT-REVIEWER-001", "blinded_review": True,
            "previously_inspected": False,
            "true_activity": activity, "authorization": authorization,
            "external_record_reference": f"EXTERNAL-SCHEDULE-RECORD-{i:03d}",
            **provenance,
        })
    manifest.write_text(json.dumps({
        "schema_version": 1, "protocol_id": "SYNTHETIC-PRACTICAL-CI",
        "fixture_only": True, "status": "frozen",
        "policy": practical.POLICY, "vision_profile": pin(profile, manifest),
        "model_artifacts": {"xml": pin(xml, manifest), "bin": pin(bin_file, manifest)},
        "calibration": calibration, "heldout": held,
    }))
    return manifest


def fake_practical(scene, protocol):
    # No truth key leaks into this injected run: forced fixture mode.
    assert "truth" not in scene
    i = int(scene["scene_id"].split("-")[1])
    decision = ("unauthorized_practical_activity" if i == 1 else
                "authorized_practical_activity" if i == 2 else
                "authorization_review_required" if i == 3 else
                "no_persistent_practical_activity")
    return {"backend": "openvino", "authoritative": True, "failures": 0,
            "decision": decision}


def mutate(file, action):
    doc = json.loads(file.read_text())
    action(doc)
    file.write_text(json.dumps(doc))


def test_practical_synthetic_perfect_predictions_never_qualify(practical_fixture):
    r = practical.qualify(practical_fixture, inference=fake_practical, test_fixture=True)
    assert r["qualified"] is False
    assert r["status"] == "synthetic_fixture_not_qualifying"
    assert all(r["criteria"].values())
    assert r["metrics"]["confusion"] == {"tp": 3, "fp": 0, "fn": 0, "tn": 3}
    assert r["metrics"]["unauthorized_false_positive_rate"] == 0
    assert r["support"]["sites"] == r["support"]["cameras"] == 2


def test_practical_real_inference_must_run_actual_pipeline(practical_fixture):
    with pytest.raises(ValueError, match="Injected"):
        practical.qualify(practical_fixture, inference=fake_practical)
    with pytest.raises(ValueError, match="Synthetic"):
        practical.qualify(practical_fixture)


def test_practical_frozen_profile_and_video_hashes_required(practical_fixture):
    doc = json.loads(practical_fixture.read_text())
    video = practical_fixture.parent / doc["heldout"][0]["video"]["path"]
    video.write_bytes(video.read_bytes() + b"x")
    with pytest.raises(ValueError, match="SHA-256"):
        practical.load(practical_fixture, test_fixture=True)


def test_practical_calibration_recording_leakage_denied(practical_fixture):
    mutate(practical_fixture, lambda x: x["heldout"][0].update({
        "recording_id": x["calibration"][0]["recording_id"]
    }))
    with pytest.raises(ValueError, match="leakage"):
        practical.load(practical_fixture, test_fixture=True)


def test_practical_missing_unknown_authorization_support_denied(practical_fixture):
    mutate(practical_fixture, lambda x: x["heldout"][2].update({"authorization": "valid"}))
    with pytest.raises(ValueError, match="authorization coverage"):
        practical.load(practical_fixture, test_fixture=True)


def test_practical_bogus_unauthorized_from_unknown_is_blocked(practical_fixture):
    def lying(scene, frozen):
        result = fake_practical(scene, frozen)
        if scene["scene_id"] == "SCENE-003":
            result["decision"] = "unauthorized_practical_activity"
        return result
    r = practical.qualify(practical_fixture, inference=lying, test_fixture=True)
    assert r["criteria"]["authorization_decision_consistency"] is False


def test_practical_failing_open_on_camera_abstentions_is_denied(practical_fixture):
    def cannot_read(scene, frozen):
        response = fake_practical(scene, frozen)
        if scene["scene_id"] in {"SCENE-001", "SCENE-002"}:
            response["decision"] = "camera_evidence_insufficient"
        return response
    r = practical.qualify(practical_fixture, inference=cannot_read, test_fixture=True)
    assert r["criteria"]["decision_coverage"] is False
    assert r["support"]["abstentions"] == 2


def test_practical_unreviewed_work_zone_and_label_not_valid(practical_fixture):
    mutate(practical_fixture, lambda x: x["heldout"][0].update({
        "blinded_review": False
    }))
    with pytest.raises(ValueError, match="blinded"):
        practical.load(practical_fixture, test_fixture=True)


@pytest.fixture
def equipment_fixture(tmp_path):
    manifest = tmp_path / "equipment-shadow.json"
    scenes = []
    provenance = {
        "source_origin": "synthetic equipment footage generated in unit tests",
        "license_basis": "synthetic generated test objects without people",
        "privacy_basis": "no identifiable video data generated",
        "independent_label_reviewer": "separate test annotator",
        "reviewed_independently": True,
    }
    for i in range(2):
        video = tmp_path / f"equip_{i}.avi"
        video.write_bytes((f"synthetic camera frame sequence {i}").encode())
        truth = tmp_path / f"equip_{i}.csv"
        proposals = tmp_path / f"proposal_{i}.json"
        reviewed = tmp_path / f"reviewed_{i}.json"
        with truth.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["second", "item_id", "true_count"])
            writer.writerows([(0, "drill", 1), (0, "chair", 0), (1, "drill", 0),
                              (1, "chair", 1)])
        proposals.write_text(json.dumps([
            {"second": 0, "items": {"drill": 1, "chair": 1}},
            {"second": 1, "items": {"drill": 0, "chair": 0}},
        ]))
        reviewed.write_text(json.dumps([
            {"second": 0, "items": {"drill": 1, "chair": 0}},
            {"second": 1, "items": {"drill": 0, "chair": 1}},
        ]))
        scenes.append({
            "scene_id": f"SCENE-{i:03d}", "camera_id": f"CAMERA-{i:03d}",
            "video": pin(video, manifest), "truth": pin(truth, manifest),
            "proposal_cache": pin(proposals, manifest),
            "human_reviewed_cache": pin(reviewed, manifest), **provenance,
        })
    manifest.write_text(json.dumps({
        "schema_version": 1, "status": "frozen", "fixture_only": True,
        "policy": equipment.POLICY, "scenes": scenes,
    }))
    return manifest


def test_equipment_shadow_separates_raw_and_reviewed_counts(equipment_fixture):
    report = equipment.analyze(equipment_fixture)
    assert report["qualified"] is False and not report["live_model_executed"]
    assert report["status"] == "synthetic_shadow_diagnostic"
    assert report["metrics"]["proposal"]["count_mae"] == 0.5
    assert report["metrics"]["reviewed"]["count_mae"] == 0.0
    assert report["support"]["independent_truth_opportunities"] == 8


def test_equipment_missing_predictions_are_abstentions_not_zeros(equipment_fixture):
    doc = json.loads(equipment_fixture.read_text())
    proposal = equipment_fixture.parent / doc["scenes"][0]["proposal_cache"]["path"]
    rows = json.loads(proposal.read_text())
    del rows[0]["items"]["chair"]
    proposal.write_text(json.dumps(rows))
    doc["scenes"][0]["proposal_cache"]["sha256"] = digest(proposal)
    equipment_fixture.write_text(json.dumps(doc))
    report = equipment.analyze(equipment_fixture)
    assert report["metrics"]["proposal"]["missing_predictions"] == 1
    assert report["metrics"]["proposal"]["coverage"] == 7 / 8
    assert report["qualified"] is False


def test_equipment_duplicate_opportunity_or_tampered_cache_denied(equipment_fixture):
    doc = json.loads(equipment_fixture.read_text())
    truth = equipment_fixture.parent / doc["scenes"][0]["truth"]["path"]
    with truth.open("a") as f:
        f.write("0,chair,0\n")
    doc["scenes"][0]["truth"]["sha256"] = digest(truth)
    equipment_fixture.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="duplicated"):
        equipment.load(equipment_fixture)


def test_equipment_sha_tamper_refused(equipment_fixture):
    doc = json.loads(equipment_fixture.read_text())
    truth = equipment_fixture.parent / doc["scenes"][0]["truth"]["path"]
    with truth.open("a") as f:
        f.write("1,drill,999\n")
    with pytest.raises(ValueError, match="SHA-256"):
        equipment.load(equipment_fixture)


def test_equipment_never_qualifies_even_nonfixture_label(equipment_fixture):
    mutate(equipment_fixture, lambda x: x.update({"fixture_only": False}))
    r = equipment.analyze(equipment_fixture)
    assert r["qualified"] is False
    assert r["status"] == "reviewed_cache_shadow_not_live_model"
