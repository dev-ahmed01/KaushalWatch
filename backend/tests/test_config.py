import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import PROJECT_ROOT, demo_manifest_path, equipment_cache_path, project_path


def test_default_demo_assets_resolve_from_repo_root(monkeypatch):
    monkeypatch.delenv("KAUSHALWATCH_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("KAUSHALWATCH_EQUIPMENT_CACHE", raising=False)
    assert demo_manifest_path() == (
        PROJECT_ROOT / "configs/job_roles/construction_electrician.demo.json"
    ).resolve()
    assert equipment_cache_path() == (
        PROJECT_ROOT / "demo/cached_detections/construction_electrician.example.json"
    ).resolve()


def test_relative_override_is_repo_relative(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_MANIFEST_PATH", "data/final/manifest.json")
    assert project_path(
        "KAUSHALWATCH_MANIFEST_PATH",
        "unused.json",
    ) == (PROJECT_ROOT / "data/final/manifest.json").resolve()


def test_absolute_override_stays_absolute(monkeypatch, tmp_path):
    target = tmp_path / "cache.json"
    monkeypatch.setenv("KAUSHALWATCH_EQUIPMENT_CACHE", str(target))
    assert equipment_cache_path() == target
