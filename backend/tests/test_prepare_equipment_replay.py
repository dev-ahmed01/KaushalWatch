"""Synthetic video fixtures for private model replay admission; no real footage."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.prepare_equipment_replay import build,main

def sha(file:Path)->str:
    return hashlib.sha256(file.read_bytes()).hexdigest()

@pytest.fixture
def local(tmp_path):
    video=tmp_path/"equipment.mp4"
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"mp4v"),10,(96,72))
    assert writer.isOpened()
    for i in range(20):
        frame=np.full((72,96,3),i*9,dtype=np.uint8)
        cv2.rectangle(frame,(12,8),(45,49),(255,255,255),1)
        writer.write(frame)
    writer.release()
    receipt={
        "status":"live_unreviewed_equipment_proposals",
        "qualified":False,"model_inference_executed":True,
        "source_video_sha256":sha(video),
        "proposal_rows":[
            {"second":0,"source":"groundingdino_local_pinned_unreviewed","detections":[]},
            {"second":1,"source":"groundingdino_local_pinned_unreviewed","detections":[]}
        ]
    }
    saved=tmp_path/"live-proposals.json"
    saved.write_text(json.dumps(receipt))
    return tmp_path

def call(folder):
    return build(folder,"Controlled synthetic research source",
                 "CI test data authored inside test suite",
                 "No human identity in synthetic frame data",
                 [0.05,0.05,0.9,0.9],
                 "Reviewed for this test camera geometry")

def test_preloaded_clip_and_receipt_match_without_copies(local):
    result=call(local)
    assert result["schema"]=="KW_EQUIPMENT_REPLAY_ADMISSION_V1"
    assert result["video_sha256"]==sha(local/"equipment.mp4")
    assert result["receipt_sha256"]==sha(local/"live-proposals.json")
    assert result["width"]==96
    assert result["height"]==72
    assert 1.9<result["duration_seconds"]<2.1
    assert not (local/"equipment-replay.local.json").exists()

def test_changed_video_or_saved_receipt_cannot_be_admitted(local):
    video=local/"equipment.mp4"
    video.write_bytes(video.read_bytes()+b"changed")
    with pytest.raises(ValueError,match="source/proposal"):
        call(local)

def test_bad_camera_region_or_unlicensed_source_rejected(local):
    with pytest.raises(ValueError):
        build(local,"unlicensed","yes","private","roi", "basis")
    with pytest.raises(ValueError,match="Camera-specific"):
        build(local,"Controlled synthetic research source",
             "CI test data authored inside test suite",
             "No human identity in synthetic frame data",
             [0.8,0.8,0.4,0.4],"Reviewed for this test camera geometry")

def test_cli_refuses_overwrite_and_reports_no_source_paths(local,monkeypatch,capsys):
    args=["prepare","--dir",str(local),"--source-origin","Controlled synthetic research source",
          "--license-basis","CI test data authored inside test suite",
          "--privacy-basis","No human identity in synthetic frame data",
          "--roi","0.05","0.05","0.90","0.90",
          "--roi-basis","Reviewed for this test camera geometry"]
    monkeypatch.setattr(sys,"argv",args)
    assert main()==0
    output=json.loads(capsys.readouterr().out)
    assert output["copy_count"]==0
    assert output["upload_count"]==0
    assert output["equipment_model_accuracy_qualified"] is False
    assert str(local) not in json.dumps(output)
    assert (local/"equipment-replay.local.json").is_file()
    assert main()==2
