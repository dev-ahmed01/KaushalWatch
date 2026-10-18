"""Synthetic decoded-video runtime regression: not an accuracy benchmark."""
from __future__ import annotations
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.run_camera_trust_worker import analyze_video, authorized_sources

def make_video(path:Path, frames:int=30)->None:
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),6,(128,96))
    if not writer.isOpened():
        pytest.skip("MJPG decoder/encoder not present in this environment")
    for index in range(frames):
        image=np.full((96,128,3),30+(index%8)*20,dtype=np.uint8)
        cv2.putText(image,str(index),(15,50),cv2.FONT_HERSHEY_SIMPLEX,.75,(220,220,220),2)
        writer.write(image)
    writer.release()

def test_sparse_frames_use_actual_decode_positions_and_no_media_export(tmp_path):
    video=tmp_path/"synthetic.avi"
    make_video(video)
    sha=hashlib.sha256(video.read_bytes()).hexdigest()
    job={"sample_limit":12,"source_sha256":sha}
    report=analyze_video(video,job,None)
    assert report["schema"]=="CAMERA_TRUST_SHADOW_SAMPLE_V1"
    assert report["sampled_frames"]==12
    assert report["requested_samples"]==12
    assert report["failed_positions"]==[]
    assert report["production_qualified"] is False
    assert report["auto_incident_mutations"]==0
    assert report["frame_images_or_video_exported"] is False
    assert report["possible_review_samples"] <= 12
    assert all(row["physical_camera_health"]=="UNKNOWN" for row in report["samples"])
    assert all(row["geometry"]["state"]=="UNKNOWN_NO_APPROVED_REFERENCE" for row in report["samples"])
    assert all(abs(row["decoded_frame0"]-row["requested_frame0"])<=1 for row in report["samples"])
    assert all("frame_pixels" not in row for row in report["samples"])

def test_cancelled_heartbeat_does_not_persist_stale_decode(tmp_path):
    video=tmp_path/"synthetic.avi"
    make_video(video)
    with pytest.raises(RuntimeError, match="lease was lost"):
        analyze_video(video,{"sample_limit":12,"source_sha256":"a"*64},None,
                      heartbeat=lambda:False)

def test_worker_refuses_centre_grant_mismatch_without_downloading(tmp_path,monkeypatch):
    from fastapi import HTTPException
    manifest=tmp_path/"source.json"
    manifest.write_text(json.dumps({"version":"KWTRUST_DRIVE_ASSETS_V1",
        "files":[{"id":"A"*25,"name":"synthetic.avi","sha256":"a"*64}]}))
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON",
                       json.dumps({"DEMO-KA-112":["synthetic.avi"]}))
    with pytest.raises(HTTPException) as denied:
        authorized_sources(manifest,"DEMO-KA-104","synthetic.avi","a"*64)
    assert denied.value.status_code==404
    allowed=authorized_sources(manifest,"DEMO-KA-112","synthetic.avi","a"*64)
    assert allowed["name"]=="synthetic.avi"
    with pytest.raises(ValueError, match="Frozen source hash"):
        authorized_sources(manifest,"DEMO-KA-112","synthetic.avi","b"*64)
