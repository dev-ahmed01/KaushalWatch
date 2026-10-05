import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.demo_assets import (
    load_demo_manifest_and_cache,
    require_equipment_profile_source,
    verify_equipment_profile_source,
)


def test_load_demo_assets_from_overrides(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    cache = tmp_path / "cache.json"
    manifest.write_text(json.dumps({"job_role": "Demo Role", "items": []}))
    cache.write_text(json.dumps([{"second": 0, "detections": []}]))

    monkeypatch.setenv("KAUSHALWATCH_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("KAUSHALWATCH_EQUIPMENT_CACHE", str(cache))

    loaded_manifest, rows = load_demo_manifest_and_cache()
    assert loaded_manifest["job_role"] == "Demo Role"
    assert rows[0]["second"] == 0



def test_reviewed_equipment_profile_prefers_sha256(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"exact-reviewed-video")
    metadata = {
        "source_video": {
            "filename": "clip.mp4",
            "sha1": "intentionally-wrong",
            "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        }
    }
    assert verify_equipment_profile_source(video, metadata) is True
    assert require_equipment_profile_source(video, metadata) is True


def test_reviewed_equipment_profile_rejects_different_video(tmp_path):
    video = tmp_path / "other.mp4"
    video.write_bytes(b"different-video")
    metadata = {
        "source_video": {
            "filename": "reviewed.mp4",
            "sha256": hashlib.sha256(b"reviewed-video").hexdigest(),
        }
    }
    assert verify_equipment_profile_source(video, metadata) is False
    try:
        require_equipment_profile_source(video, metadata)
    except ValueError as exc:
        assert "frozen to reviewed.mp4" in str(exc)
    else:
        raise AssertionError("mismatched reviewed source should be rejected")


def test_synthetic_equipment_profile_has_no_source_lock(tmp_path):
    video = tmp_path / "synthetic.avi"
    video.write_bytes(b"synthetic")
    assert verify_equipment_profile_source(video, {}) is None
    assert require_equipment_profile_source(video, {}) is None
