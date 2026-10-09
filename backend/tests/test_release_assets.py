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
    meta.write_text(json.dumps({"source_video": {"sha256": _hash(clip)}}))
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
    meta.write_text(json.dumps({"source_video": {"sha256": "abcdef12" * 8}}))
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
