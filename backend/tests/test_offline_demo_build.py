"""A stale or fabricated 'offline build' cannot qualify a judge workstation."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.verify_offline_demo_build import (
    OfflineBuildError, REQUIRED, SCHEMA, MODE, verify, clean_source_commit,
)

COMMIT = "a" * 40


def fixture(tmp_path):
    root = tmp_path / "kaushalwatch"
    build = root / "web" / ".next"
    media = root / "web" / "public" / "camera-trust"
    build.mkdir(parents=True)
    media.mkdir(parents=True)
    source = media / "manifest.json"
    source.write_bytes(b'{"schema":"KW_SUBMISSION_SAMPLE_MEDIA_V1"}')
    (build / "BUILD_ID").write_text("ControlledDemoBuild_2026")
    doc = {
        "schema": SCHEMA, "mode": MODE, "commit": COMMIT,
        "api_origin": "http://127.0.0.1:8000",
        "next_build_id": "ControlledDemoBuild_2026",
        "source_manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "runtime_font_requests_external": False,
        "protected_officer_mode_enabled": False,
    }
    path = build / "kw-offline-demo-build.json"
    path.write_text(json.dumps(doc))
    return root, path, doc, source, build


def modify(path, doc, **changes):
    path.write_text(json.dumps({**doc, **changes}))


def test_source_port_build_id_verified_without_field_certification(tmp_path):
    root, path, doc, source, build = fixture(tmp_path)
    x = verify(root, COMMIT, 8000)
    assert x["status"] == "local_prebuilt_next_source_config_verified"
    assert x["procedural_manifest_bound"] is True
    assert x["field_accuracy_qualified"] is False
    assert x["browser_rehearsal_passed"] is False
    assert x["runtime_external_requests_independently_verified"] is False


@pytest.mark.parametrize(("change", "word"), [
    ({"commit": "b" * 40}, "stale"),
    ({"api_origin": "http://127.0.0.1:8001"}, "stale"),
    ({"api_origin": "https://evil.example"}, "stale"),
    ({"next_build_id": "DifferentBuild_2026"}, "stale"),
    ({"runtime_font_requests_external": True}, "stale"),
    ({"protected_officer_mode_enabled": True}, "stale"),
    ({"mode": "ACTUAL_GOVERNMENT_PILOT"}, "stale"),
])
def test_block_stale_or_misrepresented_receipt(tmp_path, change, word):
    root, path, doc, source, build = fixture(tmp_path)
    modify(path, doc, **change)
    with pytest.raises(OfflineBuildError, match=word):
        verify(root, COMMIT, 8000)


def test_block_manifest_drift_and_wrong_port_or_revision(tmp_path):
    root, path, doc, source, build = fixture(tmp_path)
    with pytest.raises(OfflineBuildError, match="stale"):
        verify(root, "b" * 40, 8000)
    with pytest.raises(OfflineBuildError, match="stale"):
        verify(root, COMMIT, 8888)
    source.write_bytes(b"changed")
    with pytest.raises(OfflineBuildError, match="stale"):
        verify(root, COMMIT, 8000)


def test_refuse_missing_symlinked_build_files_and_duplicate_members(tmp_path):
    root, path, doc, source, build = fixture(tmp_path)
    path.unlink()
    with pytest.raises(OfflineBuildError, match="missing"):
        verify(root, COMMIT, 8000)
    path.symlink_to(build / "BUILD_ID")
    with pytest.raises(OfflineBuildError, match="linked"):
        verify(root, COMMIT, 8000)
    path.unlink()
    path.write_text('{"schema":"X","schema":"Y"}')
    with pytest.raises(OfflineBuildError, match="Duplicate"):
        verify(root, COMMIT, 8000)


def test_block_dirty_git_source_even_if_head_sha_exists(monkeypatch, tmp_path):
    root, *_ = fixture(tmp_path)
    class Proc:
        def __init__(self, value):
            self.stdout = value
    def fake(cmd, **kwargs):
        return Proc(COMMIT + "\n" if "rev-parse" in cmd else " M web/app/layout.tsx\n")
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(OfflineBuildError, match="uncommitted"):
        clean_source_commit(root)


def test_reject_out_of_range_local_api_port(tmp_path):
    root, *_ = fixture(tmp_path)
    with pytest.raises(OfflineBuildError, match="port"):
        verify(root, COMMIT, 80)
