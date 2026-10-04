import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as app_main


def _upload(name: str, payload: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(payload))


def test_video_upload_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as exc:
        app_main._materialize_video_upload(_upload("notes.txt", b"not-a-video"))
    assert exc.value.status_code == 415
    assert "unsupported video format" in str(exc.value.detail).lower()


def test_video_upload_rejects_empty_file():
    with pytest.raises(HTTPException) as exc:
        app_main._materialize_video_upload(_upload("empty.mp4", b""))
    assert exc.value.status_code == 400
    assert "empty" in str(exc.value.detail).lower()


def test_video_upload_enforces_configured_size_limit(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_MAX_UPLOAD_MB", "1")
    payload = b"x" * (1024 * 1024 + 1)
    with pytest.raises(HTTPException) as exc:
        app_main._materialize_video_upload(_upload("too-large.mp4", payload))
    assert exc.value.status_code == 413
    assert "trim the clip" in str(exc.value.detail).lower()


def test_video_upload_materializes_supported_clip(tmp_path, monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_MAX_UPLOAD_MB", "1")
    path = app_main._materialize_video_upload(_upload("demo-attendance-clean.avi", b"abc"))
    try:
        assert path.suffix == ".avi"
        assert path.read_bytes() == b"abc"
    finally:
        path.unlink(missing_ok=True)
