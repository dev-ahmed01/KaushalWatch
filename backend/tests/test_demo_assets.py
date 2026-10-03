import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.demo_assets import load_demo_manifest_and_cache


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
