"""Manifest validator works with an API-only checkout (no workstation import)."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.camera_source_manifest import load_manifest

def manifest():
    return {"version":"KWTRUST_DRIVE_ASSETS_V1",
            "files":[{"id":"A"*25,"name":"source.avi","sha256":"b"*64,"group":"full-videos"}]}

def read(tmp_path,record):
    p=tmp_path/"approved.json"
    p.write_text(json.dumps(record),encoding="utf-8")
    return load_manifest(p)

def test_manifest_loaded_without_workstation_dependency(tmp_path):
    approved=read(tmp_path,manifest())
    assert approved[0]["name"]=="source.avi"
    import inspect
    source=inspect.getsource(load_manifest)
    assert "camera_trust_workstation" not in source

@pytest.mark.parametrize("bad",[
    {"files":[],"version":"KWTRUST_DRIVE_ASSETS_V1"},
    {"files":[{"id":"z","name":"source.avi"}],"version":"KWTRUST_DRIVE_ASSETS_V1"},
    {"files":[{"id":"A"*25,"name":"../source.avi"}],"version":"KWTRUST_DRIVE_ASSETS_V1"},
    {"files":[{"id":"A"*25,"name":".hidden.avi"}],"version":"KWTRUST_DRIVE_ASSETS_V1"},
    {"files":[{"id":"A"*25,"name":"source.avi","sha256":"bad"}],"version":"KWTRUST_DRIVE_ASSETS_V1"},
    {"version":"KWTRUST_DRIVE_ASSETS_V1","files":[3]},
    {"version":"invalid","files":[]},
])
def test_invalid_private_manifest_is_rejected(tmp_path,bad):
    with pytest.raises(ValueError):read(tmp_path,bad)

def test_duplicate_source_rejected(tmp_path):
    x=manifest()
    x["files"].append(dict(x["files"][0]))
    with pytest.raises(ValueError):read(tmp_path,x)

def test_malformed_json_rejected(tmp_path):
    p=tmp_path/"bad.json";p.write_text("{")
    with pytest.raises(ValueError):load_manifest(p)
