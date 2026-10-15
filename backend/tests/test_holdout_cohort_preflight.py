"""Synthetic metadata fixtures: never represent institutional accuracy evidence."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation import holdout_cohort_preflight as cohort


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path) -> dict:
    return {"path": path.name, "sha256": digest(path)}


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    # The intentionally non-video bytes must NEVER enter a real pillar scorer.
    cal = tmp_path / "calibration.raw"
    held = tmp_path / "untouched.raw"
    cal.write_bytes(b"SYNTHETIC CALIBRATION BYTES, NOT A VIDEO")
    held.write_bytes(b"SYNTHETIC HOLDOUT BYTES, NOT A VIDEO")
    meta = {
        "source_origin": "nonperson synthetic CI data bytes",
        "license_basis": "synthetic CI fixture usage only",
        "privacy_basis": "synthetic files without any people",
    }
    top = {"schema_version": 1, "status": "frozen", "fixture_only": True,
           "pillars": {}}
    for pillar in cohort.PILLARS:
        data = {
            "schema_version": 1, "status": "frozen", "fixture_only": True,
            "protocol_id": f"TEST-{pillar.upper()}",
            "calibration": [{
                "recording_id": "REC-CAL-001", "scene_id": f"CAL-{pillar}",
                "site_id": "SITE-CAL", "camera_id": "CAM-CAL",
                "video": ref(cal), **meta,
            }],
            "heldout": [{
                "recording_id": "REC-HOLD-001", "scene_id": f"HOLD-{pillar}",
                "site_id": "SITE-HOLD", "camera_id": "CAM-HOLD",
                "video": ref(held), "blinded_review": True,
                "reviewer_id": "REVIEWER-INDEPENDENT",
                "previously_inspected": False, **meta,
            }],
        }
        filename = tmp_path / f"{pillar}.json"
        filename.write_text(json.dumps(data, indent=2))
        top["pillars"][pillar] = ref(filename)
    path = tmp_path / "frozen-cohort.json"
    path.write_text(json.dumps(top, indent=2))
    return path


def change_pillar(bundle: Path, pillar: str, fn) -> None:
    root = json.loads(bundle.read_text())
    link = root["pillars"][pillar]
    path = bundle.parent / link["path"]
    doc = json.loads(path.read_text())
    fn(doc)
    path.write_text(json.dumps(doc))
    link["sha256"] = digest(path)
    bundle.write_text(json.dumps(root))


def change_cohort(bundle: Path, fn) -> None:
    raw = json.loads(bundle.read_text())
    fn(raw)
    bundle.write_text(json.dumps(raw))


def test_valid_fixture_preflight_never_qualifies_accuracy(bundle):
    result = cohort.check_cohort(bundle, test_fixture=True)
    assert result["qualified"] is False
    assert result["cohort_inputs_admissible_for_individual_validation"] is False
    assert result["status"] == "metadata_preflight_passed_not_accuracy_qualified"
    assert result["support"]["heldout_recordings"] == 1
    assert set(result["pillars"]) == set(cohort.PILLARS)
    assert all(v["heldout_scenes"] == 1 for v in result["pillars"].values())
    assert str(bundle.parent) not in json.dumps(result)
    assert "REVIEWER-INDEPENDENT" not in json.dumps(result)


def test_synthetic_fixture_cannot_claim_real_metadata_admission(bundle):
    with pytest.raises(cohort.PreflightError, match="fixture_mode_mismatch"):
        cohort.check_cohort(bundle)


def test_missing_fifth_pillar_is_blocking(bundle):
    change_cohort(bundle, lambda d: d["pillars"].pop("roi_motion"))
    with pytest.raises(cohort.PreflightError, match="five_pillar_manifest_set_incomplete"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_shared_calibration_heldout_recording_rejected_across_pillars(bundle):
    # This scene is not reused within its own pillar; only the global
    # comparison catches calibration footage dressed as holdout elsewhere.
    change_pillar(bundle, "equipment", lambda d: d["heldout"][0].update({
        "recording_id": "REC-CAL-001",
        "site_id": "SITE-CAL", "camera_id": "CAM-CAL",
        "video": ref(bundle.parent / "calibration.raw"),
    }))
    with pytest.raises(cohort.PreflightError, match="global_calibration_holdout_recordings_leakage"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_cross_partition_camera_overlap_blocked_even_if_media_different(bundle):
    def change(d):
        for record in d["calibration"]:
            record["site_id"] = "SITE-HOLD"
            record["camera_id"] = "CAM-HOLD"
    for name in cohort.PILLARS:
        change_pillar(bundle, name, change)
    with pytest.raises(cohort.PreflightError, match="global_calibration_holdout_cameras_leakage"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_identical_media_with_different_recording_ids_is_not_independent(bundle):
    change_pillar(bundle, "equipment", lambda d: d["heldout"][0].update({
        "recording_id": "REC-HOLD-FAKE-ALIAS",
    }))
    with pytest.raises(cohort.PreflightError, match="video_relabelled_with_different_recording_id"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_same_recording_id_cannot_name_two_distinct_videos(bundle):
    different = bundle.parent / "other.raw"
    different.write_bytes(b"distinct synthetic media identity")
    change_pillar(bundle, "practical_activity", lambda d: d["heldout"][0].update({
        "video": ref(different),
    }))
    with pytest.raises(cohort.PreflightError, match="recording_id_aliases_different_video"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_reviewer_attestation_and_prior_inspection_fail_closed(bundle):
    change_pillar(bundle, "attendance", lambda d: d["heldout"][0].pop("previously_inspected"))
    with pytest.raises(cohort.PreflightError, match="independent_untouched_blind_review_not_attested"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_modified_pillar_manifest_digest_cannot_be_silently_reused(bundle):
    doc = bundle.parent / "attendance.json"
    doc.write_text(doc.read_text() + "\n ")
    with pytest.raises(cohort.PreflightError, match="manifest_digest_mismatch"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_modified_footage_digest_cannot_be_silently_reused(bundle):
    video = bundle.parent / "untouched.raw"
    video.write_bytes(video.read_bytes() + b"changed")
    with pytest.raises(cohort.PreflightError, match="video_digest_mismatch"):
        cohort.check_cohort(bundle, test_fixture=True)


def test_known_dev_marker_blocks_claimed_real_holdout(bundle):
    def change_real(data):
        data["fixture_only"] = False
    change_cohort(bundle, change_real)
    for name in cohort.PILLARS:
        def update(data):
            data["fixture_only"] = False
            for row in data["calibration"] + data["heldout"]:
                row.update({
                    "source_origin": "authorized institution research recording",
                    "license_basis": "documented limited evaluation permission",
                    "privacy_basis": "restricted and consent-governed local source",
                })
        change_pillar(bundle, name, update)
    change_pillar(bundle, "attendance", lambda d: d["heldout"][0].update({
        "recording_id": "EPFL-CAM0-PREVIOUSLY-USED",
    }))
    with pytest.raises(cohort.PreflightError, match="known_inspected_development_source"):
        cohort.check_cohort(bundle)


def test_cli_output_never_exposes_private_local_paths(bundle, tmp_path, monkeypatch, capsys):
    output = tmp_path / "preflight-result.json"
    monkeypatch.setattr(sys, "argv", [
        "holdout_cohort_preflight.py", "--manifest", str(bundle),
        "--out", str(output),
    ])
    with pytest.raises(SystemExit) as exc:
        cohort.main()
    assert exc.value.code == 2
    data = json.loads(output.read_text())
    assert data["qualified"] is False
    assert data["status"] == "metadata_preflight_blocked"
    assert data["reason_code"] == "cohort_fixture_mode_mismatch"
    assert str(bundle.parent) not in output.read_text()
    assert str(bundle.parent) not in capsys.readouterr().out
