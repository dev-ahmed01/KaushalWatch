"""No real imagery is stored by held-out qualification tests.

All media are locally constructed synthetic clips; injected inference always
returns a NON-QUALIFYING status, regardless of apparently perfect metrics.
"""
from __future__ import annotations

import copy
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
from evaluation import heldout_qualification as q


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path, manifest):
    return {"path": str(path.relative_to(manifest.parent)), "sha256": digest(path)}


@pytest.fixture
def protocol(tmp_path, monkeypatch):
    manifest = tmp_path / "holdout.json"
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({
        "status": "frozen_sih_candidate",
        "person_detection": {
            "backend": "openvino", "confidence": 0.45, "tiled": True,
            "tile_overlap": 0.18, "tile_nms_iou": 0.45,
        },
        "attendance": {
            "count_source": "confirmed", "smoother_window": 3,
            "sample_every_seconds": 0.2, "mismatch_threshold_pct": 25.0,
            "persistence_threshold": 0.7, "minimum_trusted_ratio": 0.8,
            "track_confirmation_seconds": 1.5,
            "registration_warmup_seconds": 2.0,
            "track_grace_seconds": 1.25,
        },
    }), encoding="utf-8")
    monkeypatch.setattr(q, "active_profile_path", lambda: profile.resolve())
    xml, bin_model = tmp_path / "model.xml", tmp_path / "model.bin"
    xml.write_text("test only model descriptor 010")
    bin_model.write_bytes(b"test only model data 001")
    def make_scene(i):
        video = tmp_path / f"clip_{i}.avi"
        video_writer = cv2.VideoWriter(
            str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (96, 72))
        assert video_writer.isOpened()
        for frame in range(65):
            pixels = np.full((72, 96, 3), (31 + i * 19 + frame % 3) % 255, dtype=np.uint8)
            video_writer.write(pixels)
        video_writer.release()
        assert video.stat().st_size > 0
        return video
    cal_video = make_scene(0)
    provenance = {
        "source_origin": "synthetic CI regression sequence",
        "license_basis": "generated test video; no third-party material",
        "privacy_basis": "no identifiable people present in fixture",
    }
    cal = [{
        "scene_id": "CAL-001", "recording_id": "SESSION-CAL-001",
        "site_id": "SITE-CAL", "camera_id": "CAM-CAL",
        "video": reference(cal_video, manifest), **provenance,
    }]
    held = []
    for index in range(1, 7):
        video = make_scene(index)
        labels = tmp_path / f"independent_{index}.csv"
        with labels.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["second", "true_count"])
            writer.writeheader()
            writer.writerows({"second": second, "true_count": 5} for second in (2, 3, 4, 5))
        held.append({
            "scene_id": f"HELD-{index:03d}",
            "recording_id": f"SESSION-HELD-{index:03d}",
            "site_id": "SITE-ONE" if index <= 3 else "SITE-TWO",
            "camera_id": "CAM-ONE" if index <= 3 else "CAM-TWO",
            "reviewer_id": "REVIEWER-INDEPENDENT",
            "blinded_review": True,
            "reported_attendance": 10 if index <= 3 else 5,
            "reported_record_reference": f"LOCAL-ATT-RECORD-{index:03d}",
            "true_issue": index <= 3,
            "video": reference(video, manifest), "truth": reference(labels, manifest),
            **provenance,
        })
    raw = {
        "schema_version": 1, "protocol_id": "SYNTHETIC-CI-HELDOUT",
        "status": "frozen", "fixture_only": True,
        "policy": dict(q.POLICY),
        "vision_profile": reference(profile, manifest),
        "model_artifacts": {"xml": reference(xml, manifest),
                            "bin": reference(bin_model, manifest)},
        "calibration": cal, "heldout": held,
    }
    manifest.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return manifest


def fake_inference(video, reported, camera, profile):
    # Synthetic perfect scoring is explicitly not an acceptance result.
    return {
        "backend": "openvino", "authoritative": True, "failures": 0,
        "decision": "attendance_exception" if reported == 10 else "compliant",
        "samples": [{
            "second": second, "frame_index": second * 10,
            "smoothed_count": 5, "eligible": True, "camera_trusted": True,
        } for second in (2, 3, 4, 5)],
    }


def edit(manifest, mutation):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    mutation(data)
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_input_checks_pin_independent_recordings_and_annotation_support(protocol):
    data = q.load_protocol(protocol, allow_fixture=True)
    assert len(data["scenes"]) == 6
    assert data["camera_count"] == 2
    assert data["site_count"] == 2
    assert data["annotations"] == 24
    assert data["positive_cases"] == data["negative_cases"] == 3


def test_synthetic_perfect_score_cannot_claim_real_accuracy(protocol):
    report = q.qualify(protocol, inference=fake_inference, test_fixture=True)
    assert report["status"] == "synthetic_fixture_not_qualifying"
    assert report["qualified"] is False
    assert all(report["criteria"].values())
    assert report["metrics"]["occupancy_mae"] == 0
    assert report["metrics"]["case_decisions"]["tp"] == 3
    assert report["metrics"]["case_decisions"]["tn"] == 3
    assert report["provenance"]["prediction_origin"] == "injected_synthetic_test_fn"


def test_real_qualification_refuses_fixture_and_unconfigured_detector(protocol):
    with pytest.raises(ValueError, match="Real inference"):
        q.qualify(protocol, inference=fake_inference)
    with pytest.raises(ValueError, match="OpenVINO"):
        q.qualify(protocol)


def test_missing_or_tampered_video_refused(protocol):
    original = q.load_protocol(protocol, allow_fixture=True)["scenes"][0]["video_path"]
    original.write_bytes(original.read_bytes() + b"tampering")
    with pytest.raises(ValueError, match="SHA-256"):
        q.load_protocol(protocol, allow_fixture=True)


def test_ground_truth_digest_tamper_refused(protocol):
    truth = q.load_protocol(protocol, allow_fixture=True)["scenes"][0]["truth_path"]
    truth.write_text(truth.read_text() + "5.2,0\n")
    with pytest.raises(ValueError, match="SHA-256"):
        q.load_protocol(protocol, allow_fixture=True)


def test_calibration_recording_leakage_refused(protocol):
    def change(data):
        data["heldout"][0]["recording_id"] = data["calibration"][0]["recording_id"]
    edit(protocol, change)
    with pytest.raises(ValueError, match="leakage"):
        q.load_protocol(protocol, allow_fixture=True)


def test_calibration_source_media_leakage_refused(protocol):
    def change(data):
        data["heldout"][0]["video"] = copy.deepcopy(data["calibration"][0]["video"])
    edit(protocol, change)
    with pytest.raises(ValueError, match="leakage"):
        q.load_protocol(protocol, allow_fixture=True)


def test_duplicate_heldout_scene_media_refused(protocol):
    def change(data):
        data["heldout"][1]["video"] = copy.deepcopy(data["heldout"][0]["video"])
    edit(protocol, change)
    with pytest.raises(ValueError, match="Duplicate source video"):
        q.load_protocol(protocol, allow_fixture=True)


def test_manifest_requires_true_negatives_and_blinded_review(protocol):
    edit(protocol, lambda data: [
        row.update({"true_issue": True}) for row in data["heldout"]
    ])
    with pytest.raises(ValueError, match="support insufficient"):
        q.load_protocol(protocol, allow_fixture=True)


def test_missing_blind_attestation_rejected(protocol):
    edit(protocol, lambda d: d["heldout"][0].update({"blinded_review": False}))
    with pytest.raises(ValueError, match="blinded"):
        q.load_protocol(protocol, allow_fixture=True)


def test_profile_digest_drift_refused(protocol):
    profile = q.active_profile_path()
    profile.write_text(profile.read_text() + "\n")
    with pytest.raises(ValueError, match="SHA-256"):
        q.load_protocol(protocol, allow_fixture=True)


def test_threshold_policy_cannot_be_relaxed_in_manifest(protocol):
    edit(protocol, lambda d: d["policy"].update({"max_occupancy_mae": 9999}))
    with pytest.raises(ValueError, match="thresholds drifted"):
        q.load_protocol(protocol, allow_fixture=True)


def test_warmup_count_scheduling_rejects_duplicate_truth_time(protocol):
    path = q.load_protocol(protocol, allow_fixture=True)["scenes"][0]["truth_path"]
    with path.open("a", encoding="utf-8") as f:
        f.write("2,5\n")
    edit(protocol, lambda d: d["heldout"][0]["truth"].update({"sha256": digest(path)}))
    with pytest.raises(ValueError, match="duplicated"):
        q.load_protocol(protocol, allow_fixture=True)


def test_missing_inference_sample_refused(protocol):
    def broken(*args):
        res = fake_inference(*args)
        res["samples"] = res["samples"][:2]
        return res
    with pytest.raises(ValueError, match="unique temporal sample"):
        q.qualify(protocol, inference=broken, test_fixture=True)


def test_duplicate_frame_claims_refused(protocol):
    def broken(*args):
        res = fake_inference(*args)
        res["samples"][1]["frame_index"] = res["samples"][0]["frame_index"]
        return res
    with pytest.raises(ValueError, match="unique temporal sample"):
        q.qualify(protocol, inference=broken, test_fixture=True)


def test_non_authoritative_fallback_detector_refused(protocol):
    def fallback(*args):
        res = fake_inference(*args)
        res["authoritative"] = False
        res["backend"] = "hog"
        return res
    with pytest.raises(ValueError, match="Non-authoritative"):
        q.qualify(protocol, inference=fallback, test_fixture=True)


def test_abstention_does_not_count_as_a_true_negative(protocol):
    def abstain(video, reported, camera, profile):
        res = fake_inference(video, reported, camera, profile)
        res["decision"] = "camera_integrity_exception"
        res["samples"] = [{**x, "smoothed_count": None,
                           "eligible": False, "camera_trusted": False}
                          for x in res["samples"]]
        return res
    with pytest.raises(ValueError, match="No trusted"):
        q.qualify(protocol, inference=abstain, test_fixture=True)


def test_partial_camera_failure_blocks_even_with_high_global_accuracy(protocol):
    first_video = q.load_protocol(protocol, allow_fixture=True)["scenes"][0]["video_path"]
    def partial(video, reported, camera, profile):
        result = fake_inference(video, reported, camera, profile)
        if video == first_video:
            result["samples"] = [{**x, "smoothed_count": None, "eligible": False,
                                  "camera_trusted": False} for x in result["samples"]]
            result["decision"] = "camera_integrity_exception"
        return result
    report = q.qualify(protocol, inference=partial, test_fixture=True)
    assert report["criteria"]["each_scene_count_coverage"] is False
    assert report["criteria"]["case_coverage"] is False
    assert report["qualified"] is False


def test_detector_failure_does_not_disappear_from_report(protocol):
    def unstable(*args):
        res = fake_inference(*args)
        res["failures"] = 1
        res["decision"] = "detector_unavailable"
        return res
    report = q.qualify(protocol, inference=unstable, test_fixture=True)
    assert report["criteria"]["detector_failures"] is False
    assert report["metrics"]["detector_failures"] == 6
    assert report["qualified"] is False


def test_thresholds_can_block_poor_count_and_alert_performance(protocol):
    def bad(*args):
        res = fake_inference(*args)
        res["samples"] = [{**x, "smoothed_count": 8} for x in res["samples"]]
        res["decision"] = "compliant"
        return res
    report = q.qualify(protocol, inference=bad, test_fixture=True)
    assert report["criteria"]["occupancy_mae"] is False
    assert report["criteria"]["case_recall"] is False
    assert report["qualified"] is False


def test_annotation_change_during_inference_rejected(protocol):
    truth = q.load_protocol(protocol, allow_fixture=True)["scenes"][0]["truth_path"]
    done = False
    def mutate(*args):
        nonlocal done
        if not done:
            truth.write_text(truth.read_text() + "6,5\n")
            done = True
        return fake_inference(*args)
    with pytest.raises(ValueError, match="SHA-256"):
        q.qualify(protocol, inference=mutate, test_fixture=True)


def test_non_fixture_claim_refuses_synthetic_provenance(protocol):
    edit(protocol, lambda d: d.update({"fixture_only": False}))
    with pytest.raises(ValueError, match="fixture/placeholder"):
        q.load_protocol(protocol, allow_fixture=False)


def test_runtime_options_use_entire_frozen_profile_not_pipeline_defaults(protocol, monkeypatch):
    """Mocked engine contract test only; no synthetic accuracy acceptance."""
    from types import SimpleNamespace
    from app.services import person_detector, video_pipeline

    pinned = q.load_protocol(protocol, allow_fixture=True)
    monkeypatch.setattr(
        person_detector, "_resolve_openvino_xml", lambda: pinned["xml_path"])
    detector = SimpleNamespace(
        info=SimpleNamespace(backend="openvino", authoritative=True),
        confidence=0.45, tiled=True, tile_overlap=0.18, tile_nms_iou=0.45,
    )
    monkeypatch.setattr(person_detector, "build_person_detector", lambda: detector)
    recorded = []

    class SpyPipeline:
        def __init__(self, evidence_root, index_path, detector):
            assert detector is not None

        def run(self, **kwargs):
            recorded.append(kwargs)
            kwargs["observation_sink"]({
                "second": 2.0, "frame_index": 20, "smoothed_count": 2,
                "detector_eligible": True, "camera_trusted": True,
            })
            return SimpleNamespace(
                detector_backend="openvino", detector_authoritative=True,
                detector_failures=0, decision="compliant",
            )

    monkeypatch.setattr(video_pipeline, "VideoCompliancePipeline", SpyPipeline)
    scene = pinned["scenes"][0]
    result = q.infer_scene(
        scene["video_path"], scene["reported_attendance"], scene["camera_id"], pinned)
    assert result["authoritative"] is True
    assert result["samples"][0]["smoothed_count"] == 2
    runtime = recorded[0]
    assert runtime["sample_every_seconds"] == 0.2
    assert runtime["mismatch_threshold_pct"] == 25.0
    assert runtime["persistence_threshold"] == 0.7
    assert runtime["minimum_trusted_ratio"] == 0.8
    assert runtime["track_confirmation_seconds"] == 1.5
    assert runtime["attendance_registration_seconds"] == 2.0
    assert runtime["track_grace_seconds"] == 1.25
    assert runtime["occupancy_count_source"] == "confirmed"
    assert runtime["occupancy_smoother_window"] == 3
    assert not {"xml", "model_weights", "truth_path"} & runtime.keys()


def test_missing_frozen_attendance_runtime_parameter_blocks_preflight(protocol):
    profile = q.active_profile_path()
    data = json.loads(profile.read_text(encoding="utf-8"))
    del data["attendance"]["track_grace_seconds"]
    profile.write_text(json.dumps(data), encoding="utf-8")
    edit(protocol, lambda d: d["vision_profile"].update({"sha256": digest(profile)}))
    with pytest.raises(ValueError, match="track_grace_seconds"):
        q.load_protocol(protocol, allow_fixture=True)


def test_profile_warmup_drift_from_heldout_policy_fails_closed(protocol):
    profile = q.active_profile_path()
    data = json.loads(profile.read_text(encoding="utf-8"))
    data["attendance"]["registration_warmup_seconds"] = 3.0
    profile.write_text(json.dumps(data), encoding="utf-8")
    edit(protocol, lambda d: d["vision_profile"].update({"sha256": digest(profile)}))
    with pytest.raises(ValueError, match="warmup differs"):
        q.load_protocol(protocol, allow_fixture=True)


def test_unusable_numeric_frozen_attendance_settings_fail_closed(protocol):
    profile = q.active_profile_path()
    data = json.loads(profile.read_text(encoding="utf-8"))
    data["attendance"]["minimum_trusted_ratio"] = True
    profile.write_text(json.dumps(data), encoding="utf-8")
    edit(protocol, lambda d: d["vision_profile"].update({"sha256": digest(profile)}))
    with pytest.raises(ValueError, match="finite numeric"):
        q.load_protocol(protocol, allow_fixture=True)



def test_insufficient_evidence_withheld_from_counts_and_case_scoring(protocol):
    first = q.load_protocol(protocol, allow_fixture=True)["scenes"][0]["video_path"]

    def insufficient_one(video, reported, camera, profile):
        result = fake_inference(video, reported, camera, profile)
        if video == first:
            result["decision"] = "attendance_evidence_insufficient"
            result["samples"] = [
                {**row, "eligible": False, "smoothed_count": None}
                for row in result["samples"]
            ]
        return result

    report = q.qualify(protocol, inference=insufficient_one, test_fixture=True)
    assert report["qualified"] is False
    assert report["metrics"]["case_coverage"] == pytest.approx(5 / 6, abs=1e-5)
    assert report["metrics"]["count_coverage"] == pytest.approx(20 / 24, abs=1e-5)
    assert report["criteria"]["case_coverage"] is False
    assert report["support"]["trusted_count_samples"] == 20


def test_insufficient_evidence_must_not_score_counts_as_valid(protocol):
    def improperly_eligible(*args):
        result = fake_inference(*args)
        result["decision"] = "attendance_evidence_insufficient"
        return result

    with pytest.raises(ValueError, match="must withhold scored counts"):
        q.qualify(protocol, inference=improperly_eligible, test_fixture=True)
