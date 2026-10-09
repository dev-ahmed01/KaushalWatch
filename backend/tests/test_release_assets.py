"""Strict release-media qualification with synthetic, temporary fixtures.

The fixture intentionally contains no real people or identifiable footage.
The source data are neither checked in nor treated as model accuracy evidence.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.release_assets import qualify_release_assets


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_video(path: Path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (96, 72))
    assert writer.isOpened()
    for frame_no in range(30):
        image = np.full((72, 96, 3), 140 + frame_no % 5, dtype=np.uint8)
        writer.write(image)
    writer.release()
    assert path.stat().st_size > 0


def _write_csv(path: Path, columns: list[str], rows: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _build_manifest(tmp_path: Path) -> Path:
    clip = tmp_path / "synthetic.avi"
    _write_video(clip)
    scenario = tmp_path / "frozen-scenario.json"
    scenario.write_text(json.dumps({
        "status": "FINAL CONTROLLED DEMO",
        "scenario_id": "SYNTH-01",
        "centre_id": "DEMO-KA-104",
        "batch_id": "TEST-BATCH",
    }))
    files = {
        "attendance": (
            ["sample_id", "true_count", "pred_count", "true_issue", "pred_issue"],
            [{"sample_id": "A1", "true_count": "2", "pred_count": "2",
              "true_issue": "false", "pred_issue": "false"}],
        ),
        "equipment": (
            ["sample_id", "item_id", "true_count", "pred_count"],
            [{"sample_id": "E1", "item_id": "training_panel",
              "true_count": "1", "pred_count": "1"}],
        ),
        "operability": (
            ["sample_id", "item_id", "true_state", "pred_state"],
            [{"sample_id": "O1", "item_id": "training_panel",
              "true_state": "APPARENTLY_ACTIVE", "pred_state": "UNCERTAIN"}],
        ),
        "cases": (
            ["sample_id", "case_type", "true_issue", "pred_issue"],
            [{"sample_id": "C1", "case_type": "attendance_discrepancy",
              "true_issue": "true", "pred_issue": "false"},
             {"sample_id": "C2", "case_type": "attendance_discrepancy",
              "true_issue": "false", "pred_issue": "false"}],
        ),
    }
    annotations = []
    for kind, (cols, rows) in files.items():
        path = tmp_path / f"{kind}.csv"
        _write_csv(path, cols, rows)
        annotations.append({
            "kind": kind, "path": path.name, "sha256": _hash(path),
            "reviewer_id": f"independent-reviewer-{kind}",
            "independent_of_predictions": True,
        })
    cache = tmp_path / "reviewed-cache.json"
    cache.write_text(json.dumps([{
        "second": 0.0, "detections": [{
            "label": "training_panel", "count": 1,
            "review_status": "accepted",
        }],
    }]))
    meta = tmp_path / "reviewed-cache.meta.json"
    meta.write_text(json.dumps({"source_video": {"sha256": _hash(clip)}, "review": {"training_panel": "accepted by human"}}))
    assets = []
    for role in ("attendance", "practical", "infrastructure", "operability", "camera_degraded"):
        assets.append({
            "id": role, "role": role,
            "path": clip.name, "sha256": _hash(clip),
            "origin": "generated independently for isolated CI integration verification",
            "license": "CI synthetic testing",
            "privacy_basis": "no identifiable human subjects",
            "centre_id": "DEMO-KA-104",
            "batch_id": "TEST-BATCH",
        })
    manifest = tmp_path / "frozen-release-assets.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "status": "frozen",
        "scenario": {
            "path": scenario.name, "sha256": _hash(scenario),
            "primary_asset_id": "infrastructure",
        },
        "assets": assets,
        "annotations": annotations,
        "equipment_cache": {
            "path": cache.name, "sha256": _hash(cache),
            "metadata": {"path": meta.name, "sha256": _hash(meta)},
            "asset_id": "infrastructure",
        },
        "operability": {
            "asset_id": "operability",
            "roi": {"x1": 10, "y1": 10, "x2": 60, "y2": 50},
            "window": {"start_sec": 1.5, "end_sec": 2.5},
            "camera_cuts": [{"start_sec": 0.3, "end_sec": 0.6}],
        },
        "practical": {
            "asset_id": "practical", "authorization": "absent",
            "zone_profile": "authorized",
        },
    }))
    return manifest


def _codes(report):
    return {row["check"]: row["ok"] for row in report["checks"]}


def test_qualifies_exact_local_clip_label_cache_and_scenario(tmp_path):
    manifest = _build_manifest(tmp_path)
    result = qualify_release_assets(manifest)
    assert result["ready"] is True, result
    assert set(result["asset_roles_seen"]) == {
        "attendance", "practical", "infrastructure", "operability", "camera_degraded"
    }
    assert result["manifest_sha256"] == _hash(manifest)
    assert all(_codes(result).values())


def test_fails_closed_if_video_changes_after_annotation_freeze(tmp_path):
    manifest = _build_manifest(tmp_path)
    with (tmp_path / "synthetic.avi").open("ab") as handle:
        handle.write(b"post-freeze alteration")
    report = qualify_release_assets(manifest)
    assert report["ready"] is False
    assert _codes(report)["asset_0_sha256_video"] is False
    assert _codes(report)["equipment_cache_bound_to_source"] is False


def test_fails_closed_if_ground_truth_has_only_positive_cases(tmp_path):
    manifest = _build_manifest(tmp_path)
    cases = tmp_path / "cases.csv"
    _write_csv(
        cases, ["sample_id", "case_type", "true_issue", "pred_issue"],
        [{"sample_id": "C1", "case_type": "attendance_discrepancy",
          "true_issue": "true", "pred_issue": "true"}],
    )
    data = json.loads(manifest.read_text())
    item = next(i for i in data["annotations"] if i["kind"] == "cases")
    item["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["annotation_3_schema"] is False


def test_rejects_placeholder_provenance_even_with_valid_clip_digest(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text())
    data["assets"][0]["license"] = "TBD"
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["asset_0_provenance"] is False


def test_rejects_operability_measurement_across_documented_camera_cut(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text())
    data["operability"]["camera_cuts"] = [{"start_sec": 2.0, "end_sec": 2.3}]
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["operability_stable_roi_window"] is False


def test_rejects_wrong_equipment_source_even_when_cache_files_are_intact(tmp_path):
    manifest = _build_manifest(tmp_path)
    meta = tmp_path / "reviewed-cache.meta.json"
    meta.write_text(json.dumps({"source_video": {"sha256": "abcdef12" * 8}, "review": {"training_panel": "accepted by human"}}))
    data = json.loads(manifest.read_text())
    data["equipment_cache"]["metadata"]["sha256"] = _hash(meta)
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["equipment_cache_metadata_digest"] is True
    assert _codes(result)["equipment_cache_bound_to_source"] is False


def test_requires_real_roles_and_independent_annotation_attestation(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text())
    data["assets"] = [a for a in data["assets"] if a["role"] != "camera_degraded"]
    data["annotations"][0]["independent_of_predictions"] = False
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["required_video_roles"] is False
    assert _codes(result)["annotation_0_independence"] is False


def test_final_freeze_refuses_rebranded_example_cache_and_labels(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text())
    example_csv = tmp_path / "cases.example.csv"
    original_cases = tmp_path / "cases.csv"
    example_csv.write_bytes(original_cases.read_bytes())
    cases = next(a for a in data["annotations"] if a["kind"] == "cases")
    cases["path"] = example_csv.name
    data["equipment_cache"]["path"] = "reviewed-cache.example.json"
    (tmp_path / "reviewed-cache.example.json").write_bytes(
        (tmp_path / "reviewed-cache.json").read_bytes()
    )
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["annotation_3_sha256"] is True
    assert _codes(result)["annotation_3_not_example"] is False
    assert _codes(result)["equipment_cache_not_example"] is False


def test_rejects_two_different_assets_assigned_to_the_same_role(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text())
    extra = dict(data["assets"][0])
    extra["id"] = "another-attendance-video"
    data["assets"].append(extra)
    manifest.write_text(json.dumps(data))
    result = qualify_release_assets(manifest)
    assert result["ready"] is False
    assert _codes(result)["asset_5_unique_role"] is False


def test_malformed_manifest_values_are_reported_as_failures_not_exceptions(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text())
    data["assets"][0]["role"] = {"untrusted": "object"}
    data["annotations"][0]["kind"] = ["unexpected"]
    data["equipment_cache"]["asset_id"] = ["invalid"]
    data["operability"]["asset_id"] = ["invalid"]
    data["practical"]["authorization"] = ["invalid"]
    data["scenario"]["primary_asset_id"] = ["invalid"]
    manifest.write_text(json.dumps(data))
    report = qualify_release_assets(manifest)
    assert report["ready"] is False
    assert _codes(report)["asset_0_role"] is False
    assert _codes(report)["annotation_0_kind"] is False
    assert _codes(report)["equipment_cache_bound_to_source"] is False
    assert _codes(report)["operability_stable_roi_window"] is False


def _scorecard_sources(tmp_path):
    return {kind: tmp_path / f"{kind}.csv"
            for kind in ("attendance", "equipment", "operability", "cases")}


def test_final_scorecard_provenance_is_sha_bound_and_disclaims_prediction_origin(tmp_path):
    from evaluation.final_scorecard_guard import verify_frozen_scorecard_inputs

    manifest = _build_manifest(tmp_path)
    provenance = verify_frozen_scorecard_inputs(manifest, _scorecard_sources(tmp_path))
    assert provenance["manifest_sha256"] == _hash(manifest)
    assert provenance["annotation_inputs"]["cases"]["sample_rows"] == 2
    assert provenance["annotation_inputs"]["cases"]["ground_truth_positive"] == 1
    assert provenance["annotation_inputs"]["cases"]["ground_truth_negative"] == 1
    assert provenance["source_video_sha256_by_role"]["infrastructure"] == _hash(tmp_path / "synthetic.avi")
    assert "NOT" in provenance["prediction_provenance"]


def test_final_scorecard_rejects_replaced_csv_even_if_contents_match(tmp_path):
    import pytest
    from evaluation.final_scorecard_guard import verify_frozen_scorecard_inputs

    manifest = _build_manifest(tmp_path)
    alternate = tmp_path / "alternate_attendance.csv"
    alternate.write_bytes((tmp_path / "attendance.csv").read_bytes())
    sources = _scorecard_sources(tmp_path)
    sources["attendance"] = alternate
    with pytest.raises(ValueError, match="attendance: provided CSV"):
        verify_frozen_scorecard_inputs(manifest, sources)


def test_final_scorecard_rejects_duplicate_case_opportunities(tmp_path):
    import pytest
    from evaluation.final_scorecard_guard import verify_frozen_scorecard_inputs

    manifest = _build_manifest(tmp_path)
    cases = tmp_path / "cases.csv"
    with cases.open("a", encoding="utf-8") as handle:
        handle.write("C1,attendance_discrepancy,true,true\n")
    data = json.loads(manifest.read_text())
    next(row for row in data["annotations"] if row["kind"] == "cases")["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="duplicated scoring opportunity"):
        verify_frozen_scorecard_inputs(manifest, _scorecard_sources(tmp_path))


def test_final_scorecard_rejects_malformed_truth_labels_even_if_sha_matches(tmp_path):
    import pytest
    from evaluation.final_scorecard_guard import verify_frozen_scorecard_inputs

    manifest = _build_manifest(tmp_path)
    cases = tmp_path / "cases.csv"
    cases.write_text(cases.read_text().replace(",false,false", ",false,maybe"))
    data = json.loads(manifest.read_text())
    next(row for row in data["annotations"] if row["kind"] == "cases")["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="expected a true/false label"):
        verify_frozen_scorecard_inputs(manifest, _scorecard_sources(tmp_path))


def test_final_scorecard_rejects_negative_counts_and_invalid_operability_state(tmp_path):
    import pytest
    from evaluation.final_scorecard_guard import verify_frozen_scorecard_inputs

    manifest = _build_manifest(tmp_path)
    attendance = tmp_path / "attendance.csv"
    attendance.write_text(attendance.read_text().replace("A1,2,2,", "A1,-2,2,"))
    data = json.loads(manifest.read_text())
    next(row for row in data["annotations"] if row["kind"] == "attendance")["sha256"] = _hash(attendance)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="count cannot be negative"):
        verify_frozen_scorecard_inputs(manifest, _scorecard_sources(tmp_path))

    attendance.write_text(attendance.read_text().replace("A1,-2,2,", "A1,2,2,"))
    op = tmp_path / "operability.csv"
    op.write_text(op.read_text().replace("UNCERTAIN", "WORKING_PERFECTLY"))
    data = json.loads(manifest.read_text())
    next(row for row in data["annotations"] if row["kind"] == "attendance")["sha256"] = _hash(attendance)
    next(row for row in data["annotations"] if row["kind"] == "operability")["sha256"] = _hash(op)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="invalid predicted state"):
        verify_frozen_scorecard_inputs(manifest, _scorecard_sources(tmp_path))


def test_final_evaluator_does_not_write_report_before_manifest_qualification(
    tmp_path, monkeypatch
):
    import pytest
    from evaluation import evaluate_final_demo

    manifest = _build_manifest(tmp_path)
    report_dir = tmp_path / "blocked-output"
    wrong = tmp_path / "alternate.csv"
    wrong.write_bytes((tmp_path / "attendance.csv").read_bytes())
    argv = [
        "evaluate_final_demo.py", "--final", "--asset-manifest", str(manifest),
        "--attendance", str(wrong),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(tmp_path / "cases.csv"),
        "--out-dir", str(report_dir),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError, match="attendance: provided CSV"):
        evaluate_final_demo.main()
    assert not report_dir.exists()


def test_final_evaluator_output_contains_frozen_provenance_and_no_model_claim(
    tmp_path, monkeypatch
):
    from evaluation import evaluate_final_demo

    manifest = _build_manifest(tmp_path)
    report_dir = tmp_path / "final-output"
    argv = [
        "evaluate_final_demo.py", "--final", "--asset-manifest", str(manifest),
        "--attendance", str(tmp_path / "attendance.csv"),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(tmp_path / "cases.csv"),
        "--out-dir", str(report_dir),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    evaluate_final_demo.main()
    report = json.loads((report_dir / "final_demo_report.json").read_text())
    assert report["evaluation_mode"] == "frozen_input_scorecard"
    assert report["input_provenance"]["manifest_sha256"] == _hash(manifest)
    assert report["prediction_source_verified"] is False
    assert report["apparent_operability"]["coverage"] == 0.0
    assert report["apparent_operability"]["accuracy_when_decided"] is None


def test_unqualified_example_mode_is_explicitly_marked(tmp_path, monkeypatch):
    from evaluation import evaluate_final_demo

    _build_manifest(tmp_path)
    report_dir = tmp_path / "dev-report"
    argv = [
        "evaluate_final_demo.py",
        "--attendance", str(tmp_path / "attendance.csv"),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(tmp_path / "cases.csv"),
        "--out-dir", str(report_dir),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    evaluate_final_demo.main()
    report = json.loads((report_dir / "final_demo_report.json").read_text())
    assert report["evaluation_mode"] == "development_inputs_not_release_qualified"
    assert report["input_provenance"] is None


def _with_attendance_frame_indices(manifest: Path, tmp_path: Path, predicted_count: int = 2) -> None:
    data = json.loads(manifest.read_text())
    attendance = tmp_path / "attendance.csv"
    _write_csv(
        attendance,
        ["sample_id", "frame_index", "true_count", "pred_count", "true_issue", "pred_issue"],
        [
            {"sample_id": "A1", "frame_index": "0", "true_count": "2",
             "pred_count": str(predicted_count), "true_issue": "false", "pred_issue": "false"},
            {"sample_id": "A2", "frame_index": "10", "true_count": "2",
             "pred_count": str(predicted_count), "true_issue": "false", "pred_issue": "false"},
        ],
    )
    next(item for item in data["annotations"] if item["kind"] == "attendance")["sha256"] = _hash(attendance)
    manifest.write_text(json.dumps(data))


def test_frame_capture_uses_frozen_frame_indices_and_does_not_store_identifying_boxes(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from evaluation import capture_attendance_inference as capture

    manifest = _build_manifest(tmp_path)
    _with_attendance_frame_indices(manifest, tmp_path)
    monkeypatch.setattr(
        capture, "assess_camera",
        lambda frame, previous_frame, reference_frame: SimpleNamespace(
            trusted=True, reasons=[],
        ),
    )

    class FakeDetector:
        info = SimpleNamespace(backend="synthetic", message="CI fixture", authoritative=False)

        def detect(self, frame):
            return [object(), object()]

    receipt = capture.capture_attendance_trace(
        manifest, tmp_path / "attendance.csv", detector=FakeDetector(), test_fixture=True
    )
    assert receipt["mode"] == "synthetic_test_only"
    assert receipt["trusted_samples"] == 2
    assert receipt["withheld_samples"] == 0
    assert [item["frame_index"] for item in receipt["samples"]] == [0, 10]
    assert [item["raw_person_detection_count"] for item in receipt["samples"]] == [2, 2]
    assert all(len(item["decoded_frame_sha256"]) == 64 for item in receipt["samples"])
    assert all("boxes" not in item and "identity" not in item for item in receipt["samples"])


def test_frame_capture_rejects_untrusted_camera_without_inventing_zero_count(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from evaluation import capture_attendance_inference as capture

    manifest = _build_manifest(tmp_path)
    _with_attendance_frame_indices(manifest, tmp_path)
    monkeypatch.setattr(
        capture, "assess_camera",
        lambda frame, previous_frame, reference_frame: SimpleNamespace(
            trusted=False, reasons=["camera_visibility_untrusted"],
        ),
    )

    class FakeDetector:
        info = SimpleNamespace(backend="synthetic", message="CI fixture", authoritative=False)

        def detect(self, frame):
            raise AssertionError("Detection on untrusted camera should not run")

    receipt = capture.capture_attendance_trace(
        manifest, tmp_path / "attendance.csv", detector=FakeDetector(), test_fixture=True
    )
    assert receipt["trusted_samples"] == 0
    assert receipt["withheld_samples"] == 2
    assert all(item["raw_person_detection_count"] is None for item in receipt["samples"])


def test_final_scorecard_rejects_unsigned_synthetic_attendance_receipt(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from evaluation import capture_attendance_inference as capture
    from evaluation.attendance_inference_verification import verify_attendance_receipt

    manifest = _build_manifest(tmp_path)
    _with_attendance_frame_indices(manifest, tmp_path)
    monkeypatch.setattr(
        capture, "assess_camera",
        lambda frame, previous_frame, reference_frame: SimpleNamespace(
            trusted=True, reasons=[],
        ),
    )

    class FakeDetector:
        info = SimpleNamespace(backend="synthetic", message="CI fixture", authoritative=False)

        def detect(self, frame):
            return [object(), object()]

    record = capture.capture_attendance_trace(
        manifest, tmp_path / "attendance.csv", detector=FakeDetector(), test_fixture=True
    )
    path = tmp_path / "synthetic-attendance-receipt.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="not from the explicit OpenVINO"):
        verify_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))


def test_receipt_matching_requires_exact_model_files_and_predicted_count(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from evaluation import capture_attendance_inference as capture
    from evaluation.attendance_inference_verification import verify_attendance_receipt

    manifest = _build_manifest(tmp_path)
    _with_attendance_frame_indices(manifest, tmp_path, predicted_count=1)
    monkeypatch.setattr(
        capture, "assess_camera",
        lambda frame, previous_frame, reference_frame: SimpleNamespace(
            trusted=True, reasons=[],
        ),
    )

    class FakeDetector:
        info = SimpleNamespace(backend="synthetic", message="CI fixture", authoritative=False)

        def detect(self, frame):
            return [object(), object()]

    record = capture.capture_attendance_trace(
        manifest, tmp_path / "attendance.csv", detector=FakeDetector(), test_fixture=True
    )
    # Fabricated fields here are TEST FIXTURES for receipt-validation behavior;
    # they deliberately do not establish real model provenance.
    xml = tmp_path / "model.xml"
    weights = tmp_path / "model.bin"
    profile = tmp_path / "frozen-profile.json"
    for path, contents in ((xml, "fake-xml"), (weights, "fake-weights"),
                           (profile, '{"profile_id":"CI-only"}')):
        path.write_text(contents)
    record["mode"] = "authoritative_openvino"
    record["detector_backend"] = "openvino"
    record["model_artifacts"] = {
        "xml_path": str(xml), "xml_sha256": _hash(xml),
        "bin_path": str(weights), "bin_sha256": _hash(weights),
    }
    record["vision_profile"] = {"path": str(profile), "sha256": _hash(profile)}
    path = tmp_path / "attendance-receipt.json"
    path.write_text(json.dumps(record))

    with pytest.raises(ValueError, match="differs from recorded OpenVINO output"):
        verify_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))

    _with_attendance_frame_indices(manifest, tmp_path, predicted_count=2)
    with pytest.raises(ValueError, match="different frozen manifest"):
        verify_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))

    # A new internally consistent synthetic test record tests the verifier
    # independently of live OpenVINO hardware/runtime availability.
    record["manifest_sha256"] = _hash(manifest)
    record["attendance_csv_sha256"] = _hash(tmp_path / "attendance.csv")
    path.write_text(json.dumps(record))
    matched_frame_hash = record["samples"][0]["decoded_frame_sha256"]
    matched = verify_attendance_receipt(
        manifest, tmp_path / "attendance.csv", path, _hash(manifest),
    )
    assert matched["sample_count"] == 2
    assert matched["scope"] == "raw_frame_detector_counts_only"
    assert "not_cryptographically_authenticated" in matched["authenticity"]

    # End-to-end scorer integration accepts the exact matched local trace,
    # but does not upgrade unsupported global model-provenance claims.
    from evaluation import evaluate_final_demo
    report_dir = tmp_path / "matched-report"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_final_demo.py", "--final", "--asset-manifest", str(manifest),
        "--attendance-receipt", str(path),
        "--attendance", str(tmp_path / "attendance.csv"),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(tmp_path / "cases.csv"),
        "--out-dir", str(report_dir),
    ])
    evaluate_final_demo.main()
    report = json.loads((report_dir / "final_demo_report.json").read_text())
    assert report["attendance_raw_frame_trace"]["sample_count"] == 2
    assert report["attendance_raw_frame_trace"]["status"] == "local_openvino_raw_count_receipt_matched"
    assert report["prediction_source_verified"] is False

    record["samples"][0]["decoded_frame_sha256"] = "a" * 64
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Decoded video frame differs"):
        verify_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))
    record["samples"][0]["decoded_frame_sha256"] = matched_frame_hash
    path.write_text(json.dumps(record))

    weights.write_text("model weights changed after evaluation")
    with pytest.raises(ValueError, match="model weights no longer matches"):
        verify_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))


def test_final_evaluator_rejects_missing_attendance_receipt_before_writing(tmp_path, monkeypatch):
    import pytest
    from evaluation import evaluate_final_demo

    manifest = _build_manifest(tmp_path)
    report_dir = tmp_path / "missing-receipt-output"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_final_demo.py", "--final", "--asset-manifest", str(manifest),
        "--attendance-receipt", str(tmp_path / "absent.json"),
        "--attendance", str(tmp_path / "attendance.csv"),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(tmp_path / "cases.csv"), "--out-dir", str(report_dir),
    ])
    with pytest.raises(FileNotFoundError):
        evaluate_final_demo.main()
    assert not report_dir.exists()


def _operational_fixture(tmp_path, monkeypatch, *, reported_attendance=0):
    from types import SimpleNamespace
    from app.services import video_pipeline
    from app.services.person_detector import DetectorInfo
    from evaluation.capture_operational_attendance import capture_operational_attendance

    manifest = _build_manifest(tmp_path)
    attendance = tmp_path / "attendance.csv"
    issue = "true" if reported_attendance else "false"
    _write_csv(
        attendance,
        ["sample_id", "frame_index", "true_count", "pred_count", "true_issue", "pred_issue"],
        [
            {"sample_id": "OP-20", "frame_index": "20", "true_count": "0",
             "pred_count": "0", "true_issue": "false", "pred_issue": issue},
            {"sample_id": "OP-24", "frame_index": "24", "true_count": "0",
             "pred_count": "0", "true_issue": "false", "pred_issue": issue},
        ],
    )
    frozen = json.loads(manifest.read_text())
    next(x for x in frozen["annotations"] if x["kind"] == "attendance")["sha256"] = _hash(attendance)
    manifest.write_text(json.dumps(frozen))
    monkeypatch.setattr(
        video_pipeline, "assess_camera",
        lambda frame, previous_frame, reference_frame: SimpleNamespace(
            trusted=True, score=100.0, reasons=[],
        ),
    )

    class SyntheticDetector:
        info = DetectorInfo(
            backend="synthetic-integration-only", mode="primary", authoritative=True,
            message="Non-real detector for deterministic operational test",
        )

        def detect(self, frame):
            return []

    receipt = capture_operational_attendance(
        manifest, attendance,
        reported_attendance=reported_attendance,
        sample_every_seconds=0.2,
        count_source="registered",
        smoother_window=5,
        detector=SyntheticDetector(),
        test_fixture=True,
    )
    return manifest, receipt


def _local_test_model_artifacts(tmp_path, receipt):
    """Only for unit-testing validation; fake artifacts never establish model validity."""
    xml = tmp_path / "simulated-detector.xml"
    weights = tmp_path / "simulated-detector.bin"
    profile = tmp_path / "simulated-profile.json"
    for path, text in ((xml, "CI Fake XML"), (weights, "CI Fake BIN"),
                       (profile, '{"status":"synthetic_ci"}')):
        path.write_text(text)
    receipt["mode"] = "authoritative_openvino_pipeline"
    receipt["detector_backend"] = "openvino"
    receipt["model_artifacts"] = {
        "xml_path": str(xml), "xml_sha256": _hash(xml),
        "bin_path": str(weights), "bin_sha256": _hash(weights),
    }
    receipt["vision_profile"] = {
        "path": str(profile), "sha256": _hash(profile),
    }
    return weights


def test_operational_capture_contains_real_pipeline_temporal_fields(tmp_path, monkeypatch):
    manifest, receipt = _operational_fixture(tmp_path, monkeypatch)
    assert receipt["mode"] == "synthetic_test_only"
    assert receipt["receipt_type"] == "operational_attendance_pipeline"
    assert receipt["eligible_samples"] == 2
    assert receipt["withheld_samples"] == 0
    assert [s["frame_index"] for s in receipt["samples"]] == [20, 24]
    assert all(s["smoothed_count"] == 0 and s["sample_mismatch"] is False
               for s in receipt["samples"])
    assert all(s["candidate_count"] == s["confirmed_count"] == s["registered_count"] == 0
               for s in receipt["samples"])
    assert all("boxes" not in s and "track_id" not in s and "image" not in s
               for s in receipt["samples"])
    assert receipt["pipeline_result"]["decision"] == "compliant"
    assert receipt["pipeline_result"]["detector_authoritative"] is True


def test_operational_capture_withholds_cameras_and_synthetic_receipts_fail_final(
    tmp_path, monkeypatch
):
    import pytest
    from types import SimpleNamespace
    from app.services import video_pipeline
    from evaluation.capture_operational_attendance import capture_operational_attendance
    from evaluation.operational_attendance_verification import verify_operational_attendance_receipt

    manifest, valid = _operational_fixture(tmp_path, monkeypatch)
    path = tmp_path / "synthetic-operational.json"
    path.write_text(json.dumps(valid))
    with pytest.raises(ValueError, match="Synthetic/fallback"):
        verify_operational_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))

    monkeypatch.setattr(
        video_pipeline, "assess_camera",
        lambda frame, previous_frame, reference_frame: SimpleNamespace(
            trusted=False, score=0.0, reasons=["insufficient light"],
        ),
    )
    from app.services.person_detector import DetectorInfo

    class DetectorThatMustNotBeCalled:
        info = DetectorInfo(backend="ci", mode="primary", authoritative=True,
                            message="CI no-detection on untrusted view")

        def detect(self, frame):
            raise AssertionError("Detector must not run on untrusted video")

    withheld = capture_operational_attendance(
        manifest, tmp_path / "attendance.csv", reported_attendance=0,
        detector=DetectorThatMustNotBeCalled(), test_fixture=True,
    )
    assert withheld["eligible_samples"] == 0
    assert withheld["withheld_samples"] == 2
    assert all(row["smoothed_count"] is None and row["sample_mismatch"] is None
               for row in withheld["samples"])


def test_operational_receipt_attests_count_flag_frames_and_model_file_digests(
    tmp_path, monkeypatch
):
    import pytest
    from evaluation.operational_attendance_verification import verify_operational_attendance_receipt
    from evaluation import evaluate_final_demo

    manifest, receipt = _operational_fixture(tmp_path, monkeypatch)
    weights = _local_test_model_artifacts(tmp_path, receipt)
    path = tmp_path / "operational-receipt.json"
    path.write_text(json.dumps(receipt))
    checked = verify_operational_attendance_receipt(
        manifest, tmp_path / "attendance.csv", path, _hash(manifest),
    )
    assert checked["sample_count"] == 2
    assert checked["status"] == "local_openvino_operational_attendance_receipt_matched"
    assert checked["authenticity"].startswith("unsigned_local_")

    # Integration: a correctly matched *test* trace reaches the scorecard.
    # Never cite synthetic stand-in models as actual field validation.
    out = tmp_path / "matched-operational-output"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_final_demo.py", "--final", "--asset-manifest", str(manifest),
        "--operational-attendance-receipt", str(path),
        "--attendance", str(tmp_path / "attendance.csv"),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(tmp_path / "cases.csv"), "--out-dir", str(out),
    ])
    evaluate_final_demo.main()
    report = json.loads((out / "final_demo_report.json").read_text())
    assert report["attendance_pipeline_trace"]["sample_count"] == 2
    assert report["attendance_raw_frame_trace"] is None
    assert report["prediction_source_verified"] is False

    receipt["samples"][0]["smoothed_count"] = 4
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="pred_count differs"):
        verify_operational_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))
    receipt["samples"][0]["smoothed_count"] = 0

    receipt["samples"][0]["sample_mismatch"] = True
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="pred_issue differs"):
        verify_operational_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))
    receipt["samples"][0]["sample_mismatch"] = False

    receipt["samples"][0]["decoded_frame_sha256"] = "0" * 64
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="decoded-frame SHA"):
        verify_operational_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))
    receipt["samples"][0]["decoded_frame_sha256"] = checked_frame_sha = (
        receipt["samples"][1]["decoded_frame_sha256"]
    )
    path.write_text(json.dumps(receipt))
    # Even reusing a valid hash from a different source frame must fail.
    with pytest.raises(ValueError, match="decoded-frame SHA"):
        verify_operational_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))

    # Restore using a new deterministic isolated pipeline run.
    _, fresh = _operational_fixture(tmp_path, monkeypatch)
    _local_test_model_artifacts(tmp_path, fresh)
    path.write_text(json.dumps(fresh))
    weights.write_text("changed after scoring")
    with pytest.raises(ValueError, match="model weights no longer matches"):
        verify_operational_attendance_receipt(manifest, tmp_path / "attendance.csv", path, _hash(manifest))


def test_operational_receipt_blocks_warmup_and_unsampled_annotation(tmp_path, monkeypatch):
    import pytest
    from evaluation.capture_operational_attendance import capture_operational_attendance
    from app.services.person_detector import DetectorInfo

    manifest, receipt = _operational_fixture(tmp_path, monkeypatch)
    data = json.loads(manifest.read_text())
    attendance = tmp_path / "attendance.csv"
    _write_csv(
        attendance,
        ["sample_id", "frame_index", "true_count", "pred_count", "true_issue", "pred_issue"],
        [{"sample_id": "UNSAMPLED", "frame_index": "21", "true_count": "0",
          "pred_count": "0", "true_issue": "false", "pred_issue": "false"}],
    )
    next(x for x in data["annotations"] if x["kind"] == "attendance")["sha256"] = _hash(attendance)
    manifest.write_text(json.dumps(data))

    class Fake:
        info = DetectorInfo(backend="ci", mode="primary", authoritative=True, message="CI")

        def detect(self, frame):
            return []

    with pytest.raises(ValueError, match="does not coincide"):
        capture_operational_attendance(
            manifest, attendance, reported_attendance=0, test_fixture=True, detector=Fake(),
        )

    # Frame zero is sampled, but its registration warmup is incomplete.
    _write_csv(
        attendance,
        ["sample_id", "frame_index", "true_count", "pred_count", "true_issue", "pred_issue"],
        [{"sample_id": "WARMUP", "frame_index": "0", "true_count": "0",
          "pred_count": "0", "true_issue": "false", "pred_issue": "false"}],
    )
    data = json.loads(manifest.read_text())
    next(x for x in data["annotations"] if x["kind"] == "attendance")["sha256"] = _hash(attendance)
    manifest.write_text(json.dumps(data))
    warmup = capture_operational_attendance(
        manifest, attendance, reported_attendance=0, test_fixture=True, detector=Fake(),
    )
    assert warmup["samples"][0]["detector_eligible"] is False
    assert warmup["samples"][0]["smoothed_count"] is None


def _case_attendance_fixture(tmp_path, monkeypatch, *, reported_attendance=0):
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, record = _operational_fixture(
        tmp_path, monkeypatch, reported_attendance=reported_attendance
    )
    positive = "true" if reported_attendance else "false"
    opposite = "false" if reported_attendance else "true"
    _local_test_model_artifacts(tmp_path, record)
    cases = tmp_path / "cases.csv"
    _write_csv(
        cases,
        ["sample_id", "case_type", "true_issue", "pred_issue",
         "source_asset_id", "centre_id", "batch_id", "reported_attendance"],
        [
            {"sample_id": "C1", "case_type": "camera_integrity",
             "true_issue": opposite, "pred_issue": "false",
             "source_asset_id": "camera_degraded", "centre_id": "DEMO-KA-104",
             "batch_id": "TEST-BATCH", "reported_attendance": "0"},
            {"sample_id": "C2", "case_type": "attendance_discrepancy",
             "true_issue": positive, "pred_issue": positive,
             "source_asset_id": "attendance", "centre_id": "DEMO-KA-104",
             "batch_id": "TEST-BATCH", "reported_attendance": str(reported_attendance)},
        ],
    )
    frozen = json.loads(manifest.read_text())
    next(x for x in frozen["annotations"] if x["kind"] == "cases")["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(frozen))
    record["manifest_sha256"] = _hash(manifest)
    receipt = tmp_path / "case-attendance-receipt.json"
    receipt.write_text(json.dumps(record))
    return manifest, cases, receipt, record


def test_full_video_case_verifier_matches_only_explicit_attendance_opportunity(
    tmp_path, monkeypatch
):
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity
    from evaluation import evaluate_final_demo

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)
    result = verify_attendance_case_opportunity(
        manifest, tmp_path / "attendance.csv", cases, receipt, _hash(manifest), "C2"
    )
    assert result["status"] == "one_attendance_case_opportunity_matched_to_operational_timeline"
    assert result["predicted_issue"] is False
    assert result["independent_label_in_csv"] is False
    assert result["timeline_frames"] == record["pipeline_result"]["frames_sampled"]
    assert result["decision"] == "compliant"
    assert result["trusted_frame_ratio"] == 1.0

    out = tmp_path / "scored-case"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_final_demo.py", "--final", "--asset-manifest", str(manifest),
        "--operational-attendance-receipt", str(receipt),
        "--attendance-case-sample-id", "C2",
        "--attendance", str(tmp_path / "attendance.csv"),
        "--equipment", str(tmp_path / "equipment.csv"),
        "--operability", str(tmp_path / "operability.csv"),
        "--cases", str(cases), "--out-dir", str(out),
    ])
    evaluate_final_demo.main()
    report = json.loads((out / "final_demo_report.json").read_text())
    assert report["attendance_case_trace"]["case_sample_id"] == "C2"
    assert report["attendance_case_trace"]["predicted_issue"] is False
    assert report["prediction_source_verified"] is False


def test_case_verifier_blocks_incorrect_reported_count_or_source_mapping(tmp_path, monkeypatch):
    import pytest
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)
    rows = list(csv.DictReader(cases.open(newline="")))
    rows[-1]["reported_attendance"] = "5"
    _write_csv(cases, list(rows[0]), rows)
    frozen = json.loads(manifest.read_text())
    next(x for x in frozen["annotations"] if x["kind"] == "cases")["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(frozen))
    record["manifest_sha256"] = _hash(manifest)
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="reported count"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")

    rows[-1]["reported_attendance"] = "0"
    rows[-1]["source_asset_id"] = "infrastructure"
    _write_csv(cases, list(rows[0]), rows)
    frozen = json.loads(manifest.read_text())
    next(x for x in frozen["annotations"] if x["kind"] == "cases")["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(frozen))
    record["manifest_sha256"] = _hash(manifest)
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="source asset"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")


def test_case_verifier_rejects_tampered_whole_video_decision_or_missing_timeline(
    tmp_path, monkeypatch
):
    import pytest
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)

    record["pipeline_result"]["decision"] = "attendance_exception"
    record["pipeline_result"]["case_type"] = "attendance_discrepancy"
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Final attendance case decision disagrees"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")

    record["pipeline_result"]["decision"] = "compliant"
    record["pipeline_result"]["case_type"] = None
    record["decision_timeline"] = record["decision_timeline"][:-1]
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="missing sampled frames"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")


def test_case_verifier_rejects_tampered_persistence_and_insufficient_camera(
    tmp_path, monkeypatch
):
    import pytest
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)

    record["pipeline_result"]["mismatch_persistence_ratio"] = 0.8
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="mismatch persistence"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")

    record["pipeline_result"]["mismatch_persistence_ratio"] = 0.0
    record["pipeline_parameters"]["minimum_trusted_ratio"] = 1.1
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Invalid recorded decision thresholds"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")


def test_case_verifier_refuses_unqualified_or_ambiguous_case_rows(tmp_path, monkeypatch):
    import pytest
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)
    rows = list(csv.DictReader(cases.open(newline="")))
    # Deliberately create two rows with the same case ID and case type.
    # The global frozen scorecard gate also rejects this; this direct
    # verification must fail rather than silently take the first row.
    rows[0]["sample_id"] = "C2"
    rows[0]["case_type"] = "attendance_discrepancy"
    rows[0]["source_asset_id"] = "attendance"
    _write_csv(cases, list(rows[0]), rows)
    frozen = json.loads(manifest.read_text())
    next(x for x in frozen["annotations"] if x["kind"] == "cases")["sha256"] = _hash(cases)
    manifest.write_text(json.dumps(frozen))
    record["manifest_sha256"] = _hash(manifest)
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="One attendance video"):
        verify_attendance_case_opportunity(manifest, tmp_path / "attendance.csv",
                                           cases, receipt, _hash(manifest), "C2")


def test_whole_video_positive_attendance_exception_matches_frozen_case_row(
    tmp_path, monkeypatch
):
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(
        tmp_path, monkeypatch, reported_attendance=5
    )
    assert record["pipeline_result"]["decision"] == "attendance_exception"
    assert record["pipeline_result"]["case_type"] == "attendance_discrepancy"
    assert record["pipeline_result"]["mismatch_persistence_ratio"] > 0.6
    checked = verify_attendance_case_opportunity(
        manifest, tmp_path / "attendance.csv", cases, receipt, _hash(manifest), "C2"
    )
    assert checked["predicted_issue"] is True
    assert checked["independent_label_in_csv"] is True
    assert checked["decision"] == "attendance_exception"


def test_attendance_case_negative_cannot_represent_insufficient_camera_trust(
    tmp_path, monkeypatch
):
    import pytest
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)
    selected_frames = {item["frame_index"] for item in record["samples"]}
    for point in record["decision_timeline"]:
        if point["frame_index"] in selected_frames:
            continue
        point["camera_trusted"] = False
        point["detector_eligible"] = False
        point["smoothed_count"] = None
        point["raw_count"] = None
        point["candidate_count"] = None
        point["confirmed_count"] = None
        point["registered_count"] = None
        point["sample_mismatch"] = None
        point["mismatch_for_persistence"] = False
    record["pipeline_result"]["trusted_sample_ratio"] = round(
        len(selected_frames) / len(record["decision_timeline"]), 4
    )
    record["pipeline_result"]["decision"] = "camera_integrity_exception"
    record["pipeline_result"]["case_type"] = "camera_integrity"
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Insufficient trusted video"):
        verify_attendance_case_opportunity(
            manifest, tmp_path / "attendance.csv", cases, receipt, _hash(manifest), "C2"
        )


def test_case_selected_sample_must_match_whole_video_timeline(tmp_path, monkeypatch):
    import pytest
    from evaluation.attendance_case_decision_verification import verify_attendance_case_opportunity

    manifest, cases, receipt, record = _case_attendance_fixture(tmp_path, monkeypatch)
    selected_frame = record["samples"][0]["frame_index"]
    full = next(row for row in record["decision_timeline"] if row["frame_index"] == selected_frame)
    full["confirmed_count"] = 10
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Selected sample conflicts"):
        verify_attendance_case_opportunity(
            manifest, tmp_path / "attendance.csv", cases, receipt, _hash(manifest), "C2"
        )
